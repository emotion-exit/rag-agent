# frontend-nextjs

当前前端使用 Next.js，并通过 Bun 运行。

## 开发

安装依赖：

```bash
bun install
```

启动开发服务器：

```bash
bun run dev
```

默认访问地址：

- http://localhost:3001

## 后端联调

- 前端当前通过 Next Route Handler 访问同源 /api/chat
- 后端推理逻辑位于 frontend-nextjs/backend 目录，由 Next 服务直接调用
- 从根目录单独启动前端时，使用 cd frontend-nextjs && bun run dev

## 相关命令

```bash
bun run dev
bun run build
bun run start
bun run lint
```
