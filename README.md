# RAG.Agent

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 20.19+ 或 22.12+
  cd backend
  cp .env.example .env
  uv venv
  source .venv/bin/activate
  uv pip install -e .
  uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

```
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Windows PowerShell：

```powershell
cd backend
Copy-Item .env.example .env
uv venv
.\.venv\Scripts\Activate.ps1
```

uv pip install -e .
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

````

后端启动后可访问：

- API 文档：http://localhost:8000/docs

```bash
cd frontend
pnpm install
pnpm dev
````

```bash
cd frontend
pnpm install
pnpm dev
```

开发地址默认是：http://localhost:5173
Web 开发态默认通过 Vite 代理将 /api 请求转发到 http://localhost:8000

````
### 3. 构建前端生产包

```bash
cd frontend
pnpm install
## 配置说明

后端配置优先级如下：

1. APP_CONFIG_PATH 指向的 JSON 配置文件
2. 环境变量
3. 代码默认值
4. 少量旧版环境变量别名兜底

常用配置分为三组：

- Embedding：EMBEDDING_API_KEY、EMBEDDING_BASE_URL、EMBEDDING_MODEL 等
- Reranker：RERANKER_API_KEY、RERANKER_BASE_URL、RERANKER_MODEL 等
- Chat：CHAT_API_KEY、CHAT_BASE_URL、CHAT_MODEL、CHAT_TEMPERATURE 等

另外还支持：

- RETRIEVAL_CANDIDATE_LIMIT
- RETRIEVAL_FINAL_CONTEXT_LIMIT
- RETRIEVAL_SOURCE_LIMIT
- RETRIEVAL_QUERY_EXPANSION_COUNT
- CHROMA_PERSIST_DIR
- UPLOAD_DIR
- CORS_ORIGINS

输出目录：

- frontend/dist/
- 可配置的 Embedding Provider
- 可配置的 Reranker Provider
- Token 级二次切分与 metadata 前缀增强


- PyMuPDF / pypdf 处理 PDF
- python-docx 处理 Word
- Markdown / 文本解析器处理纯文本类文档

## 核心设计

### 1. 模型能力解耦

项目没有把对话、Embedding、Reranker 绑定到单一供应商，而是拆成三类独立配置项：

- CHAT\_\*
- EMBEDDING\_\*
- RERANKER\_\*

这样做的意义是：可以根据成本、稳定性和效果，单独替换任意一条能力链路，而不需要改动整体架构。

### 2. 双层文档切分

文档在入库前会经历两次处理：

1. 按文档结构提取章节和文本块
2. 按 embedding token 预算做二次切分

二次切分时会拼接知识库名称、标签、章节路径和来源位置等 metadata 前缀，以提升召回质量。

### 3. 可追溯问答

系统不仅返回答案，还返回：

- 来源文档名
- 摘要片段
- chunk 编号
- 来源页码和章节
- 关联图片

这让问答结果可核对、可追溯，而不是一个黑盒输出。

### 4. Web 优先交付

当前分支聚焦浏览器端交付：前端负责展示、请求级公开配置和健康探测，后端负责统一装配运行参数、检索链路和文档资产。项目目标不是演示页，而是可持续联调、可直接部署的知识助手。

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 20.19+ 或 22.12+
- 推荐使用 uv 管理后端依赖
- 推荐使用 pnpm 管理前端依赖

### 1. 启动后端

Linux / macOS：

```bash
cd backend
cp .env.example .env
uv venv
source .venv/bin/activate
uv pip install -e .
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
````

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

### 2. 启动前端

```bash
cd frontend
pnpm install
pnpm dev
```

开发地址默认是：http://localhost:5173
Web 开发态默认通过 Vite 代理将 /api 请求转发到 http://localhost:8000

### 3. 构建前端生产包

```bash
cd frontend
pnpm install
pnpm build
```

输出目录：

- frontend/dist/

## 配置说明

后端配置优先级如下：

1. APP_CONFIG_PATH 指向的 JSON 配置文件
2. 环境变量
3. 代码默认值
4. 少量旧版环境变量别名兜底

常用配置分为三组：

- Embedding：EMBEDDING_API_KEY、EMBEDDING_BASE_URL、EMBEDDING_MODEL 等
- Reranker：RERANKER_API_KEY、RERANKER_BASE_URL、RERANKER_MODEL 等
- Chat：CHAT_API_KEY、CHAT_BASE_URL、CHAT_MODEL、CHAT_TEMPERATURE 等

另外还支持：

- RETRIEVAL_CANDIDATE_LIMIT
- RETRIEVAL_FINAL_CONTEXT_LIMIT
- RETRIEVAL_SOURCE_LIMIT
- RETRIEVAL_QUERY_EXPANSION_COUNT
- CHROMA_PERSIST_DIR
- UPLOAD_DIR
- CORS_ORIGINS

运行配置可通过环境变量或 APP_CONFIG_PATH 指向的 JSON 文件统一装配；Web 端公开高级设置则通过请求头临时附带。

## 主要接口

### 聊天

- POST /api/chat/stream：流式问答
- POST /api/chat/：非流式问答
- GET /api/chat/sources/{doc_id}/{chunk_index}：来源详情
- GET /api/chat/documents/{doc_id}/images/{image_id}：来源图片

### 知识库

- GET /api/knowledge-base/spaces：知识库列表
- POST /api/knowledge-base/spaces：创建知识库
- PUT /api/knowledge-base/spaces/{space_id}：更新知识库
- POST /api/knowledge-base/upload：同步上传
- POST /api/knowledge-base/upload-jobs：后台上传任务
- GET /api/knowledge-base/jobs/{job_id}：查询任务进度
- GET /api/knowledge-base/documents：文档列表
- DELETE /api/knowledge-base/documents/{doc_id}：删除文档
- DELETE /api/knowledge-base/spaces/{space_id}：删除知识库
- GET /api/knowledge-base/stats：统计信息

### 健康检查

- GET /health：基础健康状态
- GET /health/public：Web 公开健康状态
- GET /health/providers：Provider 连通性探测
- GET /health/providers/public：Web 公开 Provider 探测

## 项目结构

```text
rag-agent/
├── backend/
│   ├── app/
│   │   ├── agent/               # RAG 检索与 Agent 逻辑
│   │   ├── routers/             # chat / knowledge-base API
│   │   ├── services/            # embedding、vector_store、document_processor 等
│   │   ├── config.py            # 运行时配置与请求级覆盖
│   │   └── main.py              # FastAPI 入口与健康检查
│   └── pyproject.toml           # 后端依赖与项目配置
├── docs/
│   ├── 项目执行流程分析.md
│   └── 项目功能解析与实践总结.md
└── frontend/
    └── src/
        ├── views/               # Chat / KnowledgeBase / Settings
        ├── components/          # AnswerCard / 来源弹窗 / 知识库弹窗
        ├── services/            # runtime / publicConfig
        └── orange-ui/           # 自定义 UI 组件
```

## 推荐阅读

- [docs/项目执行流程分析.md](docs/项目执行流程分析.md)
- [docs/项目功能解析与实践总结.md](docs/项目功能解析与实践总结.md)
