# RAG Agent Backend

FastAPI backend for the RAG Agent system.

## OCR

- 上传 `.docx` 或 `.pdf` 时，会额外对内嵌截图做 OCR。
- OCR 不依赖 LLM，识别结果会作为独立文本块进入向量库。
- 聊天来源命中 OCR 片段时，会显示“截图识别”和来源位置。
