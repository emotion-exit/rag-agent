import { spawnSync } from 'node:child_process';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const frontendRoot = resolve(__dirname, '..');
const backendRoot = resolve(frontendRoot, '../backend');
const target = process.argv[2] || 'current';

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
  run('pnpm', ['exec', 'electron-builder', '--win', 'portable'], frontendRoot);
}
