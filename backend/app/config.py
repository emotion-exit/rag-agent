"""应用配置加载。

这份配置模块承担三件事：
1. 定义后端运行时需要的所有配置项。
2. 统一配置优先级：APP_CONFIG_PATH 指向的 JSON > 环境变量 > 默认值。
3. 将相对路径的本地存储目录解析为绝对路径，避免桌面版切换工作目录后找不到数据。
"""

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
import httpx
from pydantic import BaseModel, ConfigDict, Field


BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = BACKEND_ROOT / "config.json"
LEGACY_ENV_FALLBACKS: dict[str, tuple[str, ...]] = {
    "EMBEDDING_API_KEY": ("SILICONFLOW_API_KEY",),
    "EMBEDDING_BASE_URL": ("SILICONFLOW_BASE_URL",),
    "RERANKER_API_KEY": ("SILICONFLOW_API_KEY",),
    "RERANKER_BASE_URL": ("SILICONFLOW_BASE_URL",),
    "CHAT_API_KEY": ("OPENROUTER_API_KEY",),
    "CHAT_BASE_URL": ("OPENROUTER_BASE_URL",),
}


class Settings(BaseModel):
    """后端统一配置对象。

    这里使用 Pydantic 的 alias 能力，让字段既支持 Python 风格命名，
    也支持环境变量 / JSON 配置里的全大写键名。
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    app_config_path: str = Field(default="", alias="APP_CONFIG_PATH")

    # Model endpoints
    embedding_api_key: str = Field(default="", alias="EMBEDDING_API_KEY")
    embedding_base_url: str = Field(default="", alias="EMBEDDING_BASE_URL")
    embedding_model: str = Field(default="", alias="EMBEDDING_MODEL")
    embedding_provider: str = Field(default="openai", alias="EMBEDDING_PROVIDER")
    embedding_max_input_tokens: int = Field(default=512, alias="EMBEDDING_MAX_INPUT_TOKENS")
    embedding_target_chunk_tokens: int = Field(default=384, alias="EMBEDDING_TARGET_CHUNK_TOKENS")
    embedding_chunk_overlap_tokens: int = Field(default=48, alias="EMBEDDING_CHUNK_OVERLAP_TOKENS")
    embedding_tokenizer_model: str = Field(default="", alias="EMBEDDING_TOKENIZER_MODEL")
    embedding_tokenizer_encoding: str = Field(default="cl100k_base", alias="EMBEDDING_TOKENIZER_ENCODING")
    embedding_request_timeout: float = Field(default=120.0, alias="EMBEDDING_REQUEST_TIMEOUT")
    embedding_connect_timeout: float = Field(default=20.0, alias="EMBEDDING_CONNECT_TIMEOUT")
    reranker_api_key: str = Field(default="", alias="RERANKER_API_KEY")
    reranker_base_url: str = Field(default="", alias="RERANKER_BASE_URL")
    reranker_model: str = Field(default="", alias="RERANKER_MODEL")
    reranker_request_timeout: float = Field(default=20.0, alias="RERANKER_REQUEST_TIMEOUT")
    retrieval_candidate_limit: int = Field(default=18, alias="RETRIEVAL_CANDIDATE_LIMIT")
    retrieval_final_context_limit: int = Field(default=5, alias="RETRIEVAL_FINAL_CONTEXT_LIMIT")
    retrieval_source_limit: int = Field(default=5, alias="RETRIEVAL_SOURCE_LIMIT")
    retrieval_query_expansion_count: int = Field(default=3, alias="RETRIEVAL_QUERY_EXPANSION_COUNT")

    chat_api_key: str = Field(default="", alias="CHAT_API_KEY")
    chat_base_url: str = Field(default="", alias="CHAT_BASE_URL")
    chat_model: str = Field(default="", alias="CHAT_MODEL")
    chat_temperature: float = Field(default=0.0, alias="CHAT_TEMPERATURE")
    openrouter_site_url: str = Field(default="https://localhost.invalid", alias="OPENROUTER_SITE_URL")
    openrouter_app_title: str = Field(default="RAG.Agent Desktop", alias="OPENROUTER_APP_TITLE")
    openrouter_categories: str = Field(default="general-chat", alias="OPENROUTER_CATEGORIES")

    # Storage
    chroma_persist_dir: str = Field(default="./data/chroma", alias="CHROMA_PERSIST_DIR")
    upload_dir: str = Field(default="./data/uploads", alias="UPLOAD_DIR")

    # CORS
    cors_origins: str = Field(
        default="http://localhost:5173,http://localhost:3000,null",
        alias="CORS_ORIGINS",
    )

    def get_cors_origins(self) -> list[str]:
        """把逗号分隔的 CORS 配置转成去重后的列表。"""
        values = [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
        return list(dict.fromkeys(values))

    def get_chat_headers(self) -> dict[str, str]:
        """构建对话请求头。

        当前只有当对话 endpoint 指向 OpenRouter 时，才下发这些可选请求头。
        只有在值非空时才下发，避免产生无意义的空头。
        """
        if "openrouter.ai" not in self.chat_base_url.lower():
            return {}

        headers: dict[str, str] = {}

        if self.openrouter_site_url.strip():
            headers["HTTP-Referer"] = self.openrouter_site_url.strip()
        if self.openrouter_app_title.strip():
            headers["X-OpenRouter-Title"] = self.openrouter_app_title.strip()
        if self.openrouter_categories.strip():
            headers["X-OpenRouter-Categories"] = self.openrouter_categories.strip()

        return headers

    def get_embedding_timeout(self) -> httpx.Timeout:
        """构建 embedding 请求的细粒度超时配置。"""
        total_timeout = max(float(self.embedding_request_timeout), 1.0)
        connect_timeout = max(float(self.embedding_connect_timeout), 1.0)
        return httpx.Timeout(total_timeout, connect=connect_timeout)

    def get_embedding_tokenizer_model(self) -> str:
        """返回 embedding 使用的 tokenizer model 标识。"""
        return self.embedding_tokenizer_model.strip() or self.embedding_model.strip()

    def get_reranker_timeout(self) -> float:
        """返回 reranker 请求超时时间。"""
        return max(float(self.reranker_request_timeout), 1.0)

    def get_embedding_litellm_kwargs(self) -> dict[str, Any]:
        """构建 embedding 的 LiteLLM 调用参数。"""
        return {
            "model": self.embedding_model,
            "custom_llm_provider": self.embedding_provider.strip() or "openai",
            "api_key": self.embedding_api_key,
            "api_base": self.embedding_base_url,
            "timeout": self.get_embedding_timeout(),
        }

    def get_provider_status_summary(self) -> dict[str, dict[str, Any]]:
        """返回轻量 provider 状态，不发起外网请求。"""
        return {
            "embedding": {
                "status": "ok" if self.embedding_api_key.strip() else "missing_config",
                "configured": bool(self.embedding_api_key.strip()),
                "base_url": self.embedding_base_url,
                "model": self.embedding_model,
                "provider": self.embedding_provider.strip() or "openai",
                "tokenizer_model": self.get_embedding_tokenizer_model(),
                "tokenizer_encoding": self.embedding_tokenizer_encoding,
            },
            "reranker": {
                "status": "ok" if self.reranker_api_key.strip() else "missing_config",
                "configured": bool(self.reranker_api_key.strip()),
                "base_url": self.reranker_base_url,
                "model": self.reranker_model,
                "provider": "siliconflow-rerank-http",
            },
            "chat": {
                "status": "ok" if self.chat_api_key.strip() else "missing_config",
                "configured": bool(self.chat_api_key.strip()),
                "base_url": self.chat_base_url,
                "model": self.chat_model,
                "provider": "openai-compatible",
            },
        }


def _resolve_config_path() -> Path:
    """确定最终配置文件路径。

    桌面版会通过 APP_CONFIG_PATH 指向用户目录中的 config.json；
    开发态如果没有显式指定，就回落到 backend/config.json。
    """
    configured = os.getenv("APP_CONFIG_PATH", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return DEFAULT_CONFIG_PATH.resolve()


def _load_json_config(config_path: Path) -> dict[str, Any]:
    """从 JSON 文件读取配置。

    这里故意做得比较宽松：
    - 文件不存在时返回空字典，方便首次启动。
    - 顶层不是对象时也返回空字典，避免异常格式直接打崩服务。
    """
    if not config_path.exists():
        return {}

    with config_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, dict):
        return {}

    return {str(key): value for key, value in payload.items()}


def _pick_config_value(
    field_name: str,
    alias: str,
    json_config: dict[str, Any],
    default: Any,
) -> Any:
    """按统一优先级挑选单个配置值。

    查找顺序：
    1. JSON 中的 alias 键，例如 CHAT_MODEL。
    2. JSON 中的字段名键，例如 chat_model。
    3. 环境变量。
    4. Pydantic 字段默认值。

    对字符串会额外做 strip，避免把纯空白字符串当成有效配置。
    """
    for key in (alias, field_name):
        if key not in json_config:
            continue

        value = json_config.get(key)
        if isinstance(value, str):
            if value.strip():
                return value.strip()
            continue
        if value is not None:
            return value

    env_value = os.getenv(alias, "").strip()
    if env_value:
        return env_value

    for legacy_alias in LEGACY_ENV_FALLBACKS.get(alias, ()): 
        legacy_value = os.getenv(legacy_alias, "").strip()
        if legacy_value:
            return legacy_value

    return default


def _resolve_storage_path(path_value: str, config_path: Path) -> str:
    """把存储目录规范化为绝对路径。

    绝对路径保持不变；相对路径以 config.json 所在目录为基准。
    这样桌面版把配置文件放在用户目录时，数据目录也会稳定地跟着配置文件走。
    """
    path = Path(path_value).expanduser()
    if path.is_absolute():
        return str(path)

    return str((config_path.parent / path).resolve())


def load_settings() -> Settings:
    """加载并组装最终 Settings 对象。"""
    load_dotenv(BACKEND_ROOT / ".env", override=False)

    config_path = _resolve_config_path()
    json_config = _load_json_config(config_path)
    values: dict[str, Any] = {"APP_CONFIG_PATH": str(config_path)}

    for field_name, model_field in Settings.model_fields.items():
        if field_name == "app_config_path":
            continue

        alias = model_field.alias or field_name.upper()
        default = model_field.default
        values[alias] = _pick_config_value(field_name, alias, json_config, default)

    # 只有本地存储目录需要做路径归一化；其余字段直接按原值交给 Pydantic 校验。
    values["CHROMA_PERSIST_DIR"] = _resolve_storage_path(values["CHROMA_PERSIST_DIR"], config_path)
    values["UPLOAD_DIR"] = _resolve_storage_path(values["UPLOAD_DIR"], config_path)

    return Settings.model_validate(values)


# 模块导入时就完成一次配置加载，方便其他模块直接使用 settings。
settings = load_settings()
