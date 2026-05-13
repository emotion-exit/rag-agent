# RAG.Agent

当前根目录的开发工作流基于 Bun，默认启动集成了聊天 API 的 Next.js 前端。

## 当前运行栈

- 运行入口：frontend-nextjs
- 聊天 API：frontend-nextjs/app/api/chat
- 推理逻辑：frontend-nextjs/backend
- 包管理与脚本入口：Bun

仓库里仍保留了旧的 Python 后端、Vue 前端和独立 TypeScript 后端实现，它们不属于根目录 package.json 当前默认启动链路。

## 快速开始

### 环境要求

- Bun 1.1+
- Node.js 20+

### 安装依赖

```bash
bun install
cd frontend-nextjs && bun install
```

### 启动开发环境

默认启动 Next.js 应用：

```bash
bun run dev
```

使用不同 Provider 启动内置聊天后端：

```bash
bun run dev:ollama
bun run dev:google
```

默认端口：

- 应用：http://localhost:3001

### 兼容启动方式

只启动前端：

```bash
bun run dev:frontend-nextjs
```

如果你仍需运行旧的独立 TypeScript 后端：

```bash
bun run dev:backend-ts
bun run dev:backend-ts:ollama
bun run dev:backend-ts:google
```

## 运行说明

- 应用运行在 3001 端口
- 聊天接口为同源 /api/chat
- 默认 Provider 为 openrouter
- 可选 Provider 为 ollama 和 google

## 常用脚本

```bash
bun run dev
bun run dev:ollama
bun run dev:google
bun run dev:frontend-nextjs
```

## 项目结构

```text
rag-agent/
├── frontend-nextjs/        # 当前使用的 Next.js 应用与内置聊天 API
├── backend-langchain-ts/   # 旧的独立 TypeScript 后端
├── backend/                # 旧版 Python 后端
├── frontend/               # 旧版 Vue 前端
├── docs/
└── package.json
```

## 推荐阅读

- [docs/项目执行流程分析.md](docs/项目执行流程分析.md)
- [docs/项目功能解析与实践总结.md](docs/项目功能解析与实践总结.md)
