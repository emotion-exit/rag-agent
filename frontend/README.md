# Frontend

Vue 3 + Vite web frontend for RAG.Agent.

## Ports

- Web frontend dev server: http://localhost:5173
- Web backend API target: http://localhost:8000

In web development, Vite proxies `/api` to port 8000.

## Knowledge Base UI

- 当前前端知识库页采用扁平列表，不再展示树形层级。
- 每个知识库只维护名称、标签、说明。
- 上传文档时只需要选择一个知识库并补充附加标签。

## Development

```sh
pnpm install
pnpm dev
```

## Build

```sh
pnpm build
```
