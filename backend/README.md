# RAG Agent Backend

FastAPI backend for the RAG Agent system.

## OCR

- 上传 `.docx` 或 `.pdf` 时，会额外对内嵌截图做 OCR。
- OCR 不依赖 LLM，识别结果会作为独立文本块进入向量库。
- 聊天来源命中 OCR 片段时，会显示“截图识别”和来源位置。
- 对较大的 `.pdf` 文件，后端会跳过图片提取以缩短同步上传耗时；正文文本检索不受影响。

## Knowledge Base Tasks

- 知识库上传和未归类迁移会以后台任务形式执行。
- `KNOWLEDGE_BASE_JOB_RETENTION_HOURS` 用于控制已完成/失败任务在内存中保留多久，默认 `2` 小时。
- `KNOWLEDGE_BASE_JOB_HISTORY_LIMIT` 用于控制最多保留多少条任务快照，默认 `200`。
