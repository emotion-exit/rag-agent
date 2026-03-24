# RAG Agent Backend

FastAPI backend for the RAG Agent system.

## Development Port

- Default backend port: 8000
- API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

In the current web workflow, the backend starts from port 8000 by default. If you need another port, override it with `BACKEND_PORT` or your uvicorn startup command.

## 图片处理

- 当前上传 `.docx` 或 `.pdf` 时，会提取内嵌图片并保存到本地资源目录。
- 这些图片主要用于聊天来源详情展示，不会直接参与文本检索。
- 对较大的 `.pdf` 文件，后端会跳过图片提取以缩短同步上传耗时；正文文本检索不受影响。
- 真正的 OCR 识别与 OCR 文本入库链路目前尚未接入。

当前不接 OCR，主要有三个原因：

- 这一版优先保证正文解析、向量入库和问答主链路稳定，正文已经是当前最主要的信息来源。
- OCR 会额外引入模型或本地依赖、更多处理耗时，以及误识别带来的噪声，尤其会拉长多文件上传和大 PDF 的处理时间。
- 在还没有针对 OCR 结果做单独评估、清洗和去噪策略之前，先把图片链路收敛在“提取与来源展示”这一层会更稳妥。

## Knowledge Base Tasks

- 知识库上传会以后台任务形式执行。
- `KNOWLEDGE_BASE_JOB_RETENTION_HOURS` 用于控制已完成/失败任务在内存中保留多久，默认 `2` 小时。
- `KNOWLEDGE_BASE_JOB_HISTORY_LIMIT` 用于控制最多保留多少条任务快照，默认 `200`。

## Knowledge Base Model

- 当前知识库为扁平结构，不再维护父子层级。
- 每个知识库只维护三类可编辑信息：名称、标签、说明。
- 文档上传时只需要选择目标知识库，后端会把知识库名称和标签写入检索元数据。
