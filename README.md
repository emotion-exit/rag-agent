# RAG Agent 知识库问答系统

基于 ADK（Google Agent Development Kit）构建的 RAG 知识库问答 Agent 系统。

- **Embedding**：[硅基流动（SiliconFlow）](https://siliconflow.cn)
- **问答 LLM**：[OpenRouter](https://openrouter.ai)
- **向量数据库**：ChromaDB
- **后端**：Python FastAPI + uv
- **前端**：Vue3 + A2UI（回答卡片）+ Ant Design Vue（页面框架）

---

## 功能

1. 📚 **知识库管理**：上传 PDF、Word、TXT、Markdown、CSV 等文档
2. 💬 **智能问答**：Agent 从知识库中检索答案，不自由发挥
3. 🎴 **美化回答**：使用 A2UI Answer Card 展示回答（支持 Markdown 渲染）
4. ⚠️ **找不到就说找不到**：知识库中无相关内容时，明确告知用户

---

## 快速开始

### 1. 环境要求

后端：Python 3.11+

前端：Node.js 20.19+ 或 22.12+

推荐工具：

- 后端依赖管理：`uv`
- 前端包管理：`pnpm`

### 2. 配置环境变量

先进入后端目录，并根据操作系统复制环境变量模板。

Linux / macOS:

```bash
cd backend
cp .env.example .env
# 编辑 .env，填写您的 API Key
```

Windows PowerShell:

```powershell
cd backend
Copy-Item .env.example .env
# 编辑 .env，填写您的 API Key
```

`.env` 需要填写：

| 变量名                | 说明                                        |
| --------------------- | ------------------------------------------- |
| `SILICONFLOW_API_KEY` | 硅基流动 API Key                            |
| `OPENROUTER_API_KEY`  | OpenRouter API Key                          |
| `EMBEDDING_MODEL`     | 嵌入模型（默认 `BAAI/bge-large-zh-v1.5`）   |
| `RERANKER_MODEL`      | 重排模型（默认 `BAAI/bge-reranker-v2-m3`）  |
| `CHAT_MODEL`          | 对话模型（默认 `anthropic/claude-3-haiku`） |

### 3. 安装与启动后端

#### Linux

```bash
cd backend

# 如未安装 uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 创建虚拟环境并安装依赖
uv venv
source .venv/bin/activate
uv pip install -e .

# 如尚未创建 .env
cp .env.example .env

# 启动服务
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### macOS

```bash
cd backend

# 如未安装 uv
brew install uv

# 创建虚拟环境并安装依赖
uv venv
source .venv/bin/activate
uv pip install -e .

# 如尚未创建 .env
cp .env.example .env

# 启动服务
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### Windows PowerShell

```powershell
cd backend

# 如未安装 uv
winget install --id Astral-sh.uv

# 创建虚拟环境并安装依赖
uv venv
.\.venv\Scripts\Activate.ps1
uv pip install -e .

# 如尚未创建 .env
Copy-Item .env.example .env

# 启动服务
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

如果 PowerShell 阻止脚本执行，可先运行：

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

API 文档：http://localhost:8000/docs

### 4. 安装与启动前端

#### Linux

```bash
cd frontend

# 如未安装 pnpm
npm install -g pnpm

pnpm install
pnpm dev
```

#### macOS

```bash
cd frontend

# 如未安装 pnpm
npm install -g pnpm

pnpm install
pnpm dev
```

#### Windows PowerShell

```powershell
cd frontend

# 如未安装 pnpm
npm install -g pnpm

pnpm install
pnpm dev
```

如果你更习惯 npm，也可以使用：

```bash
cd frontend
npm install
npm run dev
```

前端地址：http://localhost:5173

### 5. 一次性启动顺序

1. 先启动后端服务，确认 http://localhost:8000/docs 可以打开。
2. 再启动前端开发服务，打开 http://localhost:5173。
3. 首次进入后，先去知识库页面上传文档，再回到问答页面提问。

---

## 项目结构

```
rag-agent/
├── backend/                  # Python FastAPI 后端
│   ├── pyproject.toml        # uv 项目配置
│   ├── .env.example          # 环境变量模板
│   └── app/
│       ├── main.py           # FastAPI 应用入口
│       ├── config.py         # 配置管理（读取 .env）
│       ├── agent/
│       │   └── rag_agent.py  # ADK RAG Agent（OpenRouter LLM）
│       ├── services/
│       │   ├── embedding.py  # 硅基流动 Embedding
│       │   ├── vector_store.py  # ChromaDB 向量存储
│       │   └── document_processor.py  # 文档解析 & 分块
│       └── routers/
│           ├── chat.py       # 聊天 API（SSE 流式）
│           └── knowledge_base.py  # 知识库管理 API
└── frontend/                 # Vue3 前端
    └── src/
        ├── views/
        │   ├── ChatView.vue          # 聊天界面
        │   └── KnowledgeBaseView.vue # 知识库管理
        └── components/
            └── AnswerCard.vue        # 美化回答卡片
```

---

## API 接口

### 知识库管理

| 方法     | 路径                                     | 说明         |
| -------- | ---------------------------------------- | ------------ |
| `POST`   | `/api/knowledge-base/upload`             | 上传文档     |
| `GET`    | `/api/knowledge-base/documents`          | 获取文档列表 |
| `DELETE` | `/api/knowledge-base/documents/{doc_id}` | 删除文档     |
| `GET`    | `/api/knowledge-base/stats`              | 获取统计信息 |

### 聊天

| 方法   | 路径               | 说明            |
| ------ | ------------------ | --------------- |
| `POST` | `/api/chat/stream` | 流式问答（SSE） |
| `POST` | `/api/chat/`       | 非流式问答      |
