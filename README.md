# RAG.Agent

面向 Web 交付的本地 RAG 知识助手。当前实现已经覆盖多用户鉴权、公私有知识库、可追溯问答、公开高级设置、异步文档上传，以及 Notebook 风格的笔记归档与更新。

## 当前能力

- 多用户登录与基于角色的管理能力
- 默认关闭开放注册，仅管理员可创建账号
- 公有知识库共享 + 私有知识库隔离
- 文档上传、后台任务、向量入库、来源追踪
- 流式聊天、来源摘要、图片来源查看
- 管理员默认值 + 用户个人覆盖的双层高级设置
- 反思策略配置，支持通过 Reflection Tokens 控制答案二次审查
- 笔记归档：手动保存单条回答、AI 生成短标题、按知识库分组浏览
- 笔记更新：基于最新公开设置重新生成候选答案，确认后覆盖当前笔记内容

## 技术栈

- 前端：Vue 3 + TypeScript + Vite
- 后端：FastAPI
- 向量库：ChromaDB
- 业务存储：SQLite

## 存储说明

默认情况下有三类本地数据：

- 向量数据：`CHROMA_PERSIST_DIR`，默认是 `backend/data/chroma`
- 上传与来源资源：`UPLOAD_DIR`，默认是 `backend/data/uploads`
- 业务数据库：`APP_DB_PATH`，默认是 `backend/data/app.db`

业务数据库中保存：

- 用户与登录令牌
- 知识库空间信息
- 笔记、笔记来源、笔记保存任务

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 20.19+ 或 22.12+
- 推荐使用 uv 管理后端依赖
- 推荐使用 pnpm 管理前端依赖

### 启动后端

Linux / macOS：

```bash
cd backend
cp .env.example .env
uv venv
source .venv/bin/activate
uv pip install -e .
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Windows PowerShell：

```powershell
cd backend
Copy-Item .env.example .env
uv venv
.\.venv\Scripts\Activate.ps1
uv pip install -e .
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

后端启动后可访问：

- API 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

### 启动前端

```bash
cd frontend
pnpm install
pnpm dev
```

开发地址默认是：http://localhost:5173

Vite 开发态会将 `/api` 请求代理到 http://localhost:8000

### 构建前端

```bash
cd frontend
pnpm install
pnpm build
```

输出目录：

- `frontend/dist`

## 鉴权与默认账号

默认鉴权策略：

- `OPEN_REGISTRATION_ENABLED=false`
- 首次启动会自动初始化管理员账号
- 默认管理员账号来自后端配置

默认值为：

- 用户名：`admin`
- 密码：`admin123456`

建议在开发以外环境通过环境变量覆盖：

- `DEFAULT_ADMIN_USERNAME`
- `DEFAULT_ADMIN_PASSWORD`

## 配置说明

后端基础配置优先级：

1. 环境变量
2. 代码默认值
3. 少量旧版环境变量别名兜底

常用基础配置分类：

- Chat：`CHAT_API_KEY`、`CHAT_BASE_URL`、`CHAT_MODEL`
- Embedding：`EMBEDDING_API_KEY`、`EMBEDDING_BASE_URL`、`EMBEDDING_MODEL`
- Reranker：`RERANKER_API_KEY`、`RERANKER_BASE_URL`、`RERANKER_MODEL`

常用系统高级参数：

- `RETRIEVAL_CANDIDATE_LIMIT`
- `RETRIEVAL_FINAL_CONTEXT_LIMIT`
- `RETRIEVAL_SOURCE_LIMIT`
- `RETRIEVAL_QUERY_EXPANSION_COUNT`
- `REFLECTION_TOKENS`
- `OPENROUTER_SITE_URL`
- `OPENROUTER_APP_TITLE`
- `OPENROUTER_CATEGORIES`
- `CHROMA_PERSIST_DIR`
- `UPLOAD_DIR`
- `APP_DB_PATH`
- `CORS_ORIGINS`
- `PRIVATE_KNOWLEDGE_BASE_ENABLED`
- `OPEN_REGISTRATION_ENABLED`

其中高级设置分成两层：

- 管理员默认配置：写入数据库，由管理员统一维护，作为系统统一默认值
- 用户个人配置：写入数据库，仅当前用户可修改；请求生效时优先于管理员默认配置

普通用户执行重置时，会删除个人覆盖项并重新继承管理员默认值。管理员重置时，则回到数据库初始化默认值。`X-Rag-Public-Config` 用于当前登录用户的临时预览覆盖，不会暴露 API Key 或模型密钥。

## 主要接口

### 鉴权

- `POST /api/auth/login`：登录
- `POST /api/auth/register`：开放注册开启时可用
- `POST /api/auth/logout`：退出登录
- `GET /api/auth/me`：当前用户信息
- `GET /api/auth/bootstrap`：鉴权与功能开关初始化信息
- `GET /api/auth/users`：管理员查看用户列表
- `POST /api/auth/users`：管理员创建用户
- `PATCH /api/auth/users/{user_id}`：管理员更新角色或启用状态
- `POST /api/auth/users/{user_id}/reset-password`：管理员重置密码

### 聊天

- `POST /api/chat/stream`：流式问答
- `POST /api/chat/`：非流式问答
- `GET /api/chat/sources/{doc_id}/{chunk_index}`：来源详情
- `GET /api/chat/documents/{doc_id}/images/{image_id}`：来源图片

### 知识库

- `GET /api/knowledge-base/spaces`：知识库列表
- `POST /api/knowledge-base/spaces`：创建知识库
- `PUT /api/knowledge-base/spaces/{space_id}`：更新知识库
- `POST /api/knowledge-base/upload`：同步上传
- `POST /api/knowledge-base/upload-jobs`：后台上传任务
- `GET /api/knowledge-base/jobs/{job_id}`：查询任务进度
- `GET /api/knowledge-base/documents`：文档列表
- `DELETE /api/knowledge-base/documents/{doc_id}`：删除文档
- `DELETE /api/knowledge-base/spaces/{space_id}`：删除知识库
- `POST /api/knowledge-base/spaces/{space_id}/delete`：兼容删除入口
- `GET /api/knowledge-base/stats`：统计信息

### 笔记

- `POST /api/notes/save-jobs`：异步保存笔记
- `GET /api/notes/save-jobs/{job_id}`：查询笔记保存状态
- `GET /api/notes`：获取笔记列表
- `GET /api/notes/{note_id}`：获取笔记详情
- `POST /api/notes/{note_id}/revision-save-jobs`：异步覆盖当前笔记内容

### 健康检查

- `GET /health`
- `GET /health/public`
- `GET /health/providers`
- `GET /health/providers/public`

## 核心设计

### 模型能力解耦

项目将 Chat、Embedding、Reranker 拆成独立配置链路，便于分别替换和调试。

### 双层文档切分

文档入库前先做结构化抽取，再按 embedding token 预算做二次切分，并拼接知识库与来源 metadata 提升召回质量。

### 可追溯问答

回答会携带来源文档、摘要、chunk、页码、章节和关联图片，便于核查答案依据。

### 分层请求配置

前端设置页保存数据库中的高级设置。后端会在每个请求中按“用户个人配置 > 管理员默认配置”的顺序合并，并通过 ContextVar 应用到当前请求，不污染全局进程配置。

### 笔记归档与更新

用户可以将单条回答归档为笔记，系统会结合问题、回答和来源线索生成简短标题；后续可重新生成候选答案，并在确认后覆盖当前笔记内容。

## 项目结构

```text
rag-agent/
├── backend/
│   ├── app/
│   │   ├── agent/               # RAG 检索、反思与生成逻辑
│   │   ├── routers/             # auth / chat / knowledge-base / notes API
│   │   ├── services/            # auth、notes、knowledge_spaces、vector_store 等
│   │   ├── config.py            # 运行时配置与请求级覆盖
│   │   └── main.py              # FastAPI 入口与健康检查
│   ├── run_desktop.py           # 本地启动入口（兼容保留）
│   └── rag_agent_backend.spec   # 打包配置（兼容保留）
├── docs/
│   ├── 项目执行流程分析.md
│   └── 项目功能解析与实践总结.md
└── frontend/
    └── src/
        ├── views/               # Chat / KnowledgeBase / Settings
        ├── components/          # AnswerCard / NotesModal / 来源弹窗 / 知识库组件
        ├── composables/         # useNotesCenter 等状态组合逻辑
        ├── services/            # runtime / publicConfig / notes
        └── orange-ui/           # 自定义 UI 组件
```

## 推荐阅读

- [docs/项目执行流程分析.md](docs/项目执行流程分析.md)
- [docs/项目功能解析与实践总结.md](docs/项目功能解析与实践总结.md)
