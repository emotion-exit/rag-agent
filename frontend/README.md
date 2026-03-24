# Frontend

Vue 3 + Vite frontend for RAG.Agent, with an Electron shell for desktop development and packaging.

## Ports

- Web frontend dev server: http://localhost:5173
- Web backend API target: http://localhost:8000
- Desktop dev frontend: http://localhost:5173
- Desktop embedded backend: starts from http://127.0.0.1:8000

In web development, Vite proxies `/api` to port 8000.
In desktop development, Electron launches the backend and passes `BACKEND_PORT=8000` by default. If 8000 is occupied, it probes upward for the next available port.

## Knowledge Base UI

- 当前前端知识库页采用扁平列表，不再展示树形层级。
- 每个知识库只维护名称、标签、说明。
- 上传文档时只需要选择一个知识库并补充附加标签。

## Development

```sh
pnpm install
pnpm dev
```

## Desktop Development

```sh
pnpm install
pnpm desktop:dev
```

## Build

```sh
pnpm build
```

## Desktop Package

```sh
pnpm desktop:build
```
