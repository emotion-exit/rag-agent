import { spawnSync } from 'node:child_process';
import {
  copyFileSync,
  existsSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  rmSync
} from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const frontendRoot = resolve(__dirname, '..');
const backendRoot = resolve(frontendRoot, '../backend');
const frontendPackageJsonPath = resolve(frontendRoot, 'package.json');
const target = process.argv[2] || 'current';

const frontendPackageJson = JSON.parse(
  readFileSync(frontendPackageJsonPath, 'utf-8')
);
const releaseRoot = resolve(
  frontendRoot,
  frontendPackageJson.build?.directories?.output || 'release'
);
const windowsFallbackOutputRoot = resolve(releaseRoot, '.builder-tmp');
const winUnpackedDir = resolve(releaseRoot, 'win-unpacked');

function resolveTarget() {
  if (target === 'current') {
    if (process.platform === 'darwin') return 'mac';
    if (process.platform === 'win32') return 'win';
    throw new Error('当前仅支持在 macOS 或 Windows 上构建桌面产物。');
  }

  if (target === 'mac' || target === 'win') {
    return target;
  }

  throw new Error(`不支持的构建目标：${target}`);
}

function ensureHostMatchesTarget(resolvedTarget) {
  const hostMatches =
    (resolvedTarget === 'mac' && process.platform === 'darwin') ||
    (resolvedTarget === 'win' && process.platform === 'win32');

  if (!hostMatches) {
    throw new Error(
      '内置 Python 后端会通过 PyInstaller 生成原生二进制，因此必须在目标系统上构建对应桌面包。请在 macOS 构建 dmg，在 Windows 构建 portable exe。'
    );
  }
}

function run(command, args, cwd) {
  const result = spawnSync(command, args, {
    cwd,
    stdio: 'inherit',
    shell: process.platform === 'win32'
  });

  if (result.status !== 0) {
    throw new Error(`${command} ${args.join(' ')} 执行失败`);
  }
}

function escapePowerShellString(value) {
  return value.replace(/'/g, "''");
}

function parseCommandOutput(stdout) {
  if (!stdout) {
    return [];
  }

  const trimmed = stdout.trim();
  if (!trimmed) {
    return [];
  }

  const parsed = JSON.parse(trimmed);
  return Array.isArray(parsed) ? parsed : [parsed];
}

function findProcessesWithinDirectory(directoryPath) {
  if (process.platform !== 'win32') {
    return [];
  }

  const normalizedPath = directoryPath.replace(/\\/g, '\\\\').toLowerCase();
  const query = [
    `$target = '${escapePowerShellString(normalizedPath)}'`,
    'Get-CimInstance Win32_Process |',
    '  Where-Object { $_.ExecutablePath -and $_.ExecutablePath.ToLower().StartsWith($target) } |',
    '  Select-Object ProcessId, Name, ExecutablePath |',
    '  ConvertTo-Json -Compress'
  ].join('\n');

  const result = spawnSync(
    'powershell.exe',
    ['-NoProfile', '-Command', query],
    {
      cwd: frontendRoot,
      encoding: 'utf-8',
      shell: false
    }
  );

  if (result.status !== 0) {
    return [];
  }

  return parseCommandOutput(result.stdout);
}

function stopProcessTree(processId) {
  const result = spawnSync(
    'taskkill.exe',
    ['/PID', String(processId), '/T', '/F'],
    {
      cwd: frontendRoot,
      stdio: 'inherit',
      shell: false
    }
  );

  return result.status === 0;
}

function removeDirectory(directoryPath) {
  rmSync(directoryPath, {
    recursive: true,
    force: true,
    maxRetries: 5,
    retryDelay: 300
  });
}

function isWindowsLockError(error) {
  return (
    process.platform === 'win32' &&
    ['EPERM', 'EBUSY', 'ENOTEMPTY'].includes(error?.code)
  );
}

function createWindowsFallbackOutputDir() {
  const fallbackOutputDir = resolve(
    windowsFallbackOutputRoot,
    `win-${Date.now()}`
  );
  mkdirSync(fallbackOutputDir, { recursive: true });
  return fallbackOutputDir;
}

function syncWindowsArtifactsToDefaultRelease(buildOutputDir) {
  if (buildOutputDir === releaseRoot || !existsSync(buildOutputDir)) {
    return;
  }

  mkdirSync(releaseRoot, { recursive: true });

  for (const entry of readdirSync(buildOutputDir, { withFileTypes: true })) {
    if (!entry.isFile()) {
      continue;
    }

    copyFileSync(
      resolve(buildOutputDir, entry.name),
      resolve(releaseRoot, entry.name)
    );
  }

  console.warn(`已将 Windows 打包产物复制回默认目录：${releaseRoot}`);
}

function ensureWindowsBuildOutputUnlocked() {
  if (process.platform !== 'win32' || !existsSync(winUnpackedDir)) {
    return releaseRoot;
  }

  try {
    removeDirectory(winUnpackedDir);
    return releaseRoot;
  } catch (error) {
    console.warn(`检测到旧的 Windows 打包目录可能被占用：${winUnpackedDir}`);
  }

  const lockedProcesses = findProcessesWithinDirectory(winUnpackedDir);

  if (lockedProcesses.length === 0) {
    try {
      removeDirectory(winUnpackedDir);
      return releaseRoot;
    } catch (error) {
      if (!isWindowsLockError(error)) {
        throw error;
      }

      const fallbackOutputDir = createWindowsFallbackOutputDir();
      console.warn(
        `旧目录仍被占用，改用新的临时输出目录继续构建：${fallbackOutputDir}`
      );
      return fallbackOutputDir;
    }
  }

  console.warn('发现仍在使用旧打包目录的进程，正在结束：');
  for (const processInfo of lockedProcesses) {
    console.warn(
      `- PID ${processInfo.ProcessId}: ${processInfo.Name} (${processInfo.ExecutablePath})`
    );
    stopProcessTree(processInfo.ProcessId);
  }

  try {
    removeDirectory(winUnpackedDir);
    return releaseRoot;
  } catch (error) {
    if (!isWindowsLockError(error)) {
      throw error;
    }

    const fallbackOutputDir = createWindowsFallbackOutputDir();
    console.warn(
      `结束旧进程后目录仍不可删除，改用新的临时输出目录继续构建：${fallbackOutputDir}`
    );
    return fallbackOutputDir;
  }
}

const resolvedTarget = resolveTarget();
ensureHostMatchesTarget(resolvedTarget);

run('pnpm', ['build'], frontendRoot);
run(
  'uv',
  [
    'run',
    '--with',
    'pyinstaller',
    'pyinstaller',
    'rag_agent_backend.spec',
    '--noconfirm'
  ],
  backendRoot
);

if (resolvedTarget === 'mac') {
  run('pnpm', ['exec', 'electron-builder', '--mac', 'dmg'], frontendRoot);
} else {
  const windowsBuildOutputDir = ensureWindowsBuildOutputUnlocked();
  const buildArgs = ['exec', 'electron-builder', '--win', 'portable'];

  if (windowsBuildOutputDir !== releaseRoot) {
    buildArgs.push(`-c.directories.output=${windowsBuildOutputDir}`);
  }

  run('pnpm', buildArgs, frontendRoot);
  syncWindowsArtifactsToDefaultRelease(windowsBuildOutputDir);
}
