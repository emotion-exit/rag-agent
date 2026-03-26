# RAG Agent Backend

RAG.Agent 的 FastAPI 后端，负责鉴权、知识库管理、RAG 检索链路、公开高级设置应用、笔记保存与健康检查。

## 运行端口

- 默认端口：8000
- API 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

## 当前后端职责

- 用户、角色、令牌鉴权
- 公有知识库共享与私有知识库隔离
- 文档解析、图片提取、向量入库
- 流式和非流式问答
- 请求级公开高级设置覆盖
- 反思策略与答案拦截控制
- 笔记异步保存、详情查询、候选更新覆盖

## 关键存储

- `APP_DB_PATH`：业务 SQLite，默认 `backend/data/app.db`
- `CHROMA_PERSIST_DIR`：Chroma 持久化目录，默认 `backend/data/chroma`
- `UPLOAD_DIR`：上传文件与来源图片目录，默认 `backend/data/uploads`

SQLite 当前保存：

- `users`
- `auth_tokens`
- `knowledge_spaces`
- `notes`
- `note_revisions`
- `note_sources`
- `note_save_jobs`

## 鉴权与用户管理

- 默认关闭开放注册，`OPEN_REGISTRATION_ENABLED=false`
- 启动时若不存在管理员，则使用 `DEFAULT_ADMIN_USERNAME` 和 `DEFAULT_ADMIN_PASSWORD` 初始化默认管理员
- 管理员可创建用户、改角色、停用用户、重置密码

## 知识库模型

- 当前知识库为扁平结构
- 每个知识库包含：名称、标签、说明、可见性、所属人
- 可见性分为 `public` 和 `private`
- 公有知识库仅管理员可管理，私有知识库由管理员或所有者管理

## 文档处理与图片

- 支持 `.pdf`、`.docx`、`.md`、`.markdown`、`.txt`、`.rst`、`.csv`
- 上传 `.docx` 或 `.pdf` 时会提取内嵌图片并保存到本地资源目录
- 图片主要用于来源详情展示，不直接参与文本检索
- 对较大的 `.pdf` 文件会跳过图片提取以降低耗时
- 当前未接入 OCR 文本入库链路

## 上传任务

- 知识库上传支持同步和后台任务两种入口
- 主界面默认走后台任务
- `KNOWLEDGE_BASE_JOB_RETENTION_HOURS`：已完成或失败任务在内存中的保留时间，默认 `2`
- `KNOWLEDGE_BASE_JOB_HISTORY_LIMIT`：任务历史快照数量上限，默认 `200`

## 笔记系统

- 笔记保存是异步任务，不阻塞主聊天流程
- 标题由辅助模型基于问题、回答和来源线索生成
- 笔记会保存所属知识库、原始问题、正文、来源摘要和保存任务状态
- 重新生成候选答案时会复用最新公开设置
- 用户点击确认后，会覆盖当前笔记内容，而不是新增一条独立笔记

## 主要接口

### 鉴权

- `POST /api/auth/login`
- `POST /api/auth/register`
- `POST /api/auth/logout`
- `GET /api/auth/me`
- `GET /api/auth/bootstrap`
- `GET /api/auth/users`
- `POST /api/auth/users`
- `PATCH /api/auth/users/{user_id}`
- `POST /api/auth/users/{user_id}/reset-password`

### 知识库

- `GET /api/knowledge-base/spaces`
- `POST /api/knowledge-base/spaces`
- `PUT /api/knowledge-base/spaces/{space_id}`
- `POST /api/knowledge-base/upload`
- `POST /api/knowledge-base/upload-jobs`
- `GET /api/knowledge-base/jobs/{job_id}`
- `GET /api/knowledge-base/documents`
- `DELETE /api/knowledge-base/documents/{doc_id}`
- `DELETE /api/knowledge-base/spaces/{space_id}`
- `POST /api/knowledge-base/spaces/{space_id}/delete`
- `GET /api/knowledge-base/stats`

### 聊天

- `POST /api/chat/stream`
- `POST /api/chat/`
- `GET /api/chat/sources/{doc_id}/{chunk_index}`
- `GET /api/chat/documents/{doc_id}/images/{image_id}`

### 笔记

- `POST /api/notes/save-jobs`
- `GET /api/notes/save-jobs/{job_id}`
- `GET /api/notes`
- `GET /api/notes/{note_id}`
- `POST /api/notes/{note_id}/revision-save-jobs`
