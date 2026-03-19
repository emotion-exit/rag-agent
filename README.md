# RAG.Agent

一个面向本地知识库场景的 RAG 桌面应用与 Web 应用。

当前仓库已经具备完整的知识库问答链路：文档解析、知识空间管理、向量入库、检索增强、来源追踪、设置页配置、桌面端封装与分发。

## 项目定位

RAG.Agent 解决的不是泛化聊天问题，而是受约束的知识库问答问题。

- 文档先被解析、分块并写入 ChromaDB
- 用户提问时先检索知识库证据，再生成答案
- 无法命中充分证据时，系统明确返回“无法回答”
- 回答结果附带来源摘要，支持回看原始片段和关联图片

它同时支持两种运行形态：

- Web / 开发态：前端直接请求后端 API
- 桌面态：Electron 承载前端，并自动拉起内置 Python 后端

## 当前能力

### 1. 智能问答

- 基于知识库的流式问答
- SSE 实时返回检索进度、答案片段和来源
- 自动识别知识空间，必要时触发澄清式交互
- 对模型输出做清洗，移除思维链、内部标签和实现细节
- 无命中或证据不足时直接拒答

### 2. 知识库管理

- 支持知识空间树形组织
- 支持 PDF、DOCX、MD、MARKDOWN、TXT、RST、CSV 文档上传
- 支持同步上传和后台任务式上传
- 支持未归类文档迁移，并在迁移时重建索引
- 支持查看文档统计、分块数量和图片数量

### 3. 来源追踪

- 返回命中文档、chunk、页码、章节和摘要
- 支持来源详情弹窗
- 支持查看 PDF / Word 关联图片
- 支持基于文档锚点展示关联图片来源
- 当前图片链路以提取与展示为主，尚未接入 OCR 文本入库

### 4. 配置与运维

- 桌面端提供完整运行配置页
- Web 端提供公开高级设置，按请求附带到后端
- 支持 Embedding、Reranker、Chat 三类能力独立配置
- 支持服务健康检查和 Provider 连通性探测
- 桌面端保存配置后自动重启内置服务

### 5. 桌面分发

- macOS 生成 dmg
- Windows 生成 portable exe
- 内置 Python 后端与本地存储目录
- 终端用户无需自行安装 Python、uv 或数据库

## 技术栈

### 前端

- Vue 3
- TypeScript
- Vite
- Vue Router
- Tailwind CSS 4
- Electron
- 自定义 Orange UI 组件库

### 后端

- Python 3.11+
- FastAPI
- Uvicorn
- Pydantic 2
- Google ADK
- LiteLLM
- OpenAI Python SDK

### 检索与存储

- ChromaDB 作为向量数据库
- 可配置的 Embedding Provider
- 可配置的 Reranker Provider
- Token 级二次切分与 metadata 前缀增强

### 文档处理

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

二次切分时会拼接知识空间、分类、主题、标签、版本、章节路径和来源位置等 metadata 前缀，以提升召回质量。

### 3. 可追溯问答

系统不仅返回答案，还返回：

- 来源文档名
- 摘要片段
- chunk 编号
- 来源页码和章节
- 关联图片

这让问答结果可核对、可追溯，而不是一个黑盒输出。

### 4. 桌面端优先交付

Electron 主进程会维护本地 config.json，拉起 Python 后端，轮询健康状态，并在保存配置后自动重启服务。项目的交付目标不是演示页，而是可安装、可使用的本地知识助手。

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

### 2. 启动前端

```bash
cd frontend
pnpm install
pnpm dev
```

开发地址默认是：http://localhost:5173

### 3. 启动桌面开发态

```bash
cd frontend
pnpm install
pnpm desktop:dev
```

桌面开发态会先启动 Vite，再由 Electron 打开窗口并连接内置后端。

### 4. 构建桌面包

```bash
cd frontend

# 当前宿主系统构建本机桌面包
pnpm desktop:build

# 在 macOS 上构建 dmg
pnpm desktop:build:mac

# 在 Windows 上构建 portable exe
pnpm desktop:build:win
```

输出目录：

- frontend/release/\*.dmg
- frontend/release/\*.exe

注意：

- macOS 的 dmg 必须在 macOS 上构建
- Windows 的 portable exe 必须在 Windows 上构建

这是因为内置 Python 后端通过 PyInstaller 生成目标平台原生二进制。

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

桌面端完整配置保存在用户目录下的 config.json；Web 模式下则通过请求头临时附带公开高级设置。

## 主要接口

### 聊天

- POST /api/chat/stream：流式问答
- POST /api/chat/：非流式问答
- GET /api/chat/sources/{doc_id}/{chunk_index}：来源详情
- GET /api/chat/documents/{doc_id}/images/{image_id}：来源图片

### 知识库

- GET /api/knowledge-base/spaces：知识空间树
- POST /api/knowledge-base/spaces：创建知识空间
- POST /api/knowledge-base/upload：同步上传
- POST /api/knowledge-base/upload-jobs：后台上传任务
- POST /api/knowledge-base/documents/migrate-ungrouped：同步迁移未归类文档
- POST /api/knowledge-base/documents/migrate-ungrouped/jobs：后台迁移任务
- GET /api/knowledge-base/jobs/{job_id}：查询任务进度
- GET /api/knowledge-base/documents：文档列表
- DELETE /api/knowledge-base/documents/{doc_id}：删除文档
- DELETE /api/knowledge-base/spaces/{space_id}：删除知识空间
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
│   ├── run_desktop.py           # 桌面端后端启动入口
│   └── rag_agent_backend.spec   # PyInstaller 配置
├── docs/
│   ├── 项目执行流程分析.md
│   └── 项目功能解析与实践总结.md
└── frontend/
    ├── electron/                # Electron 主进程与 preload
    ├── scripts/                 # 桌面打包脚本
    └── src/
        ├── views/               # Chat / KnowledgeBase / Settings
        ├── components/          # AnswerCard / 来源弹窗 / 知识库弹窗
        ├── services/            # runtime / publicConfig
        └── orange-ui/           # 自定义 UI 组件
```

## 推荐阅读

- [docs/项目执行流程分析.md](docs/项目执行流程分析.md)
- [docs/项目功能解析与实践总结.md](docs/项目功能解析与实践总结.md)
