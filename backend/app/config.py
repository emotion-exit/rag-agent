"""应用配置加载。

这份配置模块承担三件事：
1. 定义后端运行时需要的所有配置项。
2. 统一配置优先级：环境变量 > 代码默认值。
3. 将相对路径的本地存储目录解析为绝对路径，避免工作目录变化后找不到数据。
"""

import os
from contextvars import ContextVar, Token
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
import httpx
from pydantic import BaseModel, ConfigDict, Field
from pydantic.fields import PydanticUndefined

from app.system_public_config_defaults import get_default_system_public_config


BACKEND_ROOT = Path(__file__).resolve().parents[1]
LEGACY_ENV_FALLBACKS: dict[str, tuple[str, ...]] = {
    "EMBEDDING_API_KEY": ("SILICONFLOW_API_KEY",),
    "EMBEDDING_BASE_URL": ("SILICONFLOW_BASE_URL",),
    "RERANKER_API_KEY": ("SILICONFLOW_API_KEY",),
    "RERANKER_BASE_URL": ("SILICONFLOW_BASE_URL",),
    "CHAT_API_KEY": ("OPENROUTER_API_KEY",),
    "CHAT_BASE_URL": ("OPENROUTER_BASE_URL",),
}
PUBLIC_FRONTEND_CONFIG_FIELDS = {
    "EMBEDDING_PROVIDER",
    "EMBEDDING_MAX_INPUT_TOKENS",
    "EMBEDDING_TARGET_CHUNK_TOKENS",
    "EMBEDDING_CHUNK_OVERLAP_TOKENS",
    "EMBEDDING_TOKENIZER_MODEL",
    "EMBEDDING_TOKENIZER_ENCODING",
    "RERANKER_REQUEST_TIMEOUT",
    "RETRIEVAL_CANDIDATE_LIMIT",
    "RETRIEVAL_FINAL_CONTEXT_LIMIT",
    "RETRIEVAL_SOURCE_LIMIT",
    "RETRIEVAL_QUERY_EXPANSION_COUNT",
    "REFLECTION_TOKENS",
    "CHAT_TEMPERATURE",
    "OPENROUTER_SITE_URL",
    "OPENROUTER_APP_TITLE",
    "OPENROUTER_CATEGORIES",
}
USER_EDITABLE_PUBLIC_FRONTEND_CONFIG_FIELDS = {
    "RERANKER_REQUEST_TIMEOUT",
    "RETRIEVAL_CANDIDATE_LIMIT",
    "RETRIEVAL_FINAL_CONTEXT_LIMIT",
    "RETRIEVAL_SOURCE_LIMIT",
    "RETRIEVAL_QUERY_EXPANSION_COUNT",
    "REFLECTION_TOKENS",
    "CHAT_TEMPERATURE",
}
_request_settings_overrides: ContextVar[dict[str, Any]] = ContextVar(
    "request_settings_overrides",
    default={},
)


class Settings(BaseModel):
    """后端统一配置对象。

    这里使用 Pydantic 的 alias 能力，让字段既支持 Python 风格命名，
    也支持环境变量 / JSON 配置里的全大写键名。
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    # Model endpoints
    embedding_api_key: str = Field(default="", alias="EMBEDDING_API_KEY")
    embedding_base_url: str = Field(default="", alias="EMBEDDING_BASE_URL")
    embedding_model: str = Field(default="", alias="EMBEDDING_MODEL")
    embedding_provider: str = Field(alias="EMBEDDING_PROVIDER")
    embedding_max_input_tokens: int = Field(alias="EMBEDDING_MAX_INPUT_TOKENS")
    embedding_target_chunk_tokens: int = Field(alias="EMBEDDING_TARGET_CHUNK_TOKENS")
    embedding_chunk_overlap_tokens: int = Field(alias="EMBEDDING_CHUNK_OVERLAP_TOKENS")
    embedding_tokenizer_model: str = Field(alias="EMBEDDING_TOKENIZER_MODEL")
    embedding_tokenizer_encoding: str = Field(alias="EMBEDDING_TOKENIZER_ENCODING")
    embedding_request_timeout: float = Field(default=120.0, alias="EMBEDDING_REQUEST_TIMEOUT")
    embedding_connect_timeout: float = Field(default=20.0, alias="EMBEDDING_CONNECT_TIMEOUT")
    reranker_api_key: str = Field(default="", alias="RERANKER_API_KEY")
    reranker_base_url: str = Field(default="", alias="RERANKER_BASE_URL")
    reranker_model: str = Field(default="", alias="RERANKER_MODEL")
    reranker_request_timeout: float = Field(alias="RERANKER_REQUEST_TIMEOUT")
    retrieval_candidate_limit: int = Field(alias="RETRIEVAL_CANDIDATE_LIMIT")
    retrieval_final_context_limit: int = Field(alias="RETRIEVAL_FINAL_CONTEXT_LIMIT")
    retrieval_source_limit: int = Field(alias="RETRIEVAL_SOURCE_LIMIT")
    retrieval_query_expansion_count: int = Field(alias="RETRIEVAL_QUERY_EXPANSION_COUNT")
    reflection_tokens: int = Field(alias="REFLECTION_TOKENS")

    chat_api_key: str = Field(default="", alias="CHAT_API_KEY")
    chat_base_url: str = Field(default="", alias="CHAT_BASE_URL")
    chat_model: str = Field(default="", alias="CHAT_MODEL")
    chat_temperature: float = Field(alias="CHAT_TEMPERATURE")
    openrouter_site_url: str = Field(alias="OPENROUTER_SITE_URL")
    openrouter_app_title: str = Field(alias="OPENROUTER_APP_TITLE")
    openrouter_categories: str = Field(alias="OPENROUTER_CATEGORIES")

    # Storage
    chroma_persist_dir: str = Field(default="./data/chroma", alias="CHROMA_PERSIST_DIR")
    upload_dir: str = Field(default="./data/uploads", alias="UPLOAD_DIR")
    app_db_path: str = Field(default="./data/app.db", alias="APP_DB_PATH")
    knowledge_base_job_retention_hours: int = Field(
        default=2,
        alias="KNOWLEDGE_BASE_JOB_RETENTION_HOURS",
    )
    knowledge_base_job_history_limit: int = Field(
        default=200,
        alias="KNOWLEDGE_BASE_JOB_HISTORY_LIMIT",
    )

    # CORS
    cors_origins: str = Field(
        default="http://localhost:5173,http://localhost:3000,null",
        alias="CORS_ORIGINS",
    )
    private_knowledge_base_enabled: bool = Field(
        default=True,
        alias="PRIVATE_KNOWLEDGE_BASE_ENABLED",
    )
    open_registration_enabled: bool = Field(
        default=False,
        alias="OPEN_REGISTRATION_ENABLED",
    )
    auth_token_ttl_hours: int = Field(default=168, alias="AUTH_TOKEN_TTL_HOURS")
    default_admin_username: str = Field(default="admin", alias="DEFAULT_ADMIN_USERNAME")
    default_admin_password: str = Field(default="admin123456", alias="DEFAULT_ADMIN_PASSWORD")

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


def _pick_config_value(
    field_name: str,
    alias: str,
    default: Any,
) -> Any:
    """按统一优先级挑选单个配置值。"""

    if alias in PUBLIC_FRONTEND_CONFIG_FIELDS:
        defaults = get_default_system_public_config()
        if alias in defaults:
            return defaults[alias]

    env_value = os.getenv(alias, "").strip()
    if env_value:
        return env_value

    for legacy_alias in LEGACY_ENV_FALLBACKS.get(alias, ()): 
        legacy_value = os.getenv(legacy_alias, "").strip()
        if legacy_value:
            return legacy_value

    if default is PydanticUndefined:
        raise RuntimeError(f"缺少必需环境变量：{alias}")

    return default


def _resolve_storage_path(path_value: str, base_dir: Path = BACKEND_ROOT) -> str:
    """把存储目录规范化为绝对路径。"""
    path = Path(path_value).expanduser()
    if path.is_absolute():
        return str(path)

    return str((base_dir / path).resolve())


def _extract_public_frontend_config(values: dict[str, Any]) -> dict[str, Any]:
    return {
        key: values[key]
        for key in PUBLIC_FRONTEND_CONFIG_FIELDS
        if key in values
    }


def load_settings() -> Settings:
    """加载并组装最终 Settings 对象。"""
    load_dotenv(BACKEND_ROOT / ".env", override=False)

    values: dict[str, Any] = {}

    for field_name, model_field in Settings.model_fields.items():
        alias = model_field.alias or field_name.upper()
        default = model_field.default
        values[alias] = _pick_config_value(field_name, alias, default)

    values["CHROMA_PERSIST_DIR"] = _resolve_storage_path(values["CHROMA_PERSIST_DIR"])
    values["UPLOAD_DIR"] = _resolve_storage_path(values["UPLOAD_DIR"])
    values["APP_DB_PATH"] = _resolve_storage_path(values["APP_DB_PATH"])

    return Settings.model_validate(values)


def get_public_frontend_config_seed() -> dict[str, Any]:
    """返回用于初始化数据库系统配置的默认值。"""
    return dict(_public_frontend_config_seed)


def _get_public_frontend_config_fallback(
    fallback: dict[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(fallback, dict):
        return get_public_frontend_config_seed()

    filtered: dict[str, Any] = {}
    for key in PUBLIC_FRONTEND_CONFIG_FIELDS:
        if key in fallback:
            filtered[key] = fallback[key]

    if not filtered:
        return get_public_frontend_config_seed()

    merged_values = _base_settings.model_dump(by_alias=True)
    merged_values.update(_public_frontend_config_seed)
    merged_values.update(filtered)
    validated = Settings.model_validate(merged_values)
    normalized = validated.model_dump(by_alias=True)
    return {
        key: normalized[key]
        for key in PUBLIC_FRONTEND_CONFIG_FIELDS
        if key in normalized
    }


def merge_public_frontend_config(
    base_config: dict[str, Any] | None,
    override_config: dict[str, Any] | None,
) -> dict[str, Any]:
    merged_values = normalize_public_frontend_config(base_config)
    if not override_config:
        return merged_values

    return normalize_public_frontend_config(override_config, fallback=merged_values)


def diff_public_frontend_config(
    source_config: dict[str, Any] | None,
    fallback_config: dict[str, Any] | None,
) -> dict[str, Any]:
    normalized_source = normalize_public_frontend_config(source_config, fallback=fallback_config)
    normalized_fallback = normalize_public_frontend_config(fallback_config)
    return {
        key: value
        for key, value in normalized_source.items()
        if normalized_fallback.get(key) != value
    }


def _normalize_public_frontend_overrides(
    overrides: dict[str, Any] | None,
    fallback: dict[str, Any] | None = None,
    allowed_fields: set[str] | None = None,
) -> dict[str, Any]:
    """校验并规范化前端可公开配置覆盖。"""
    if not isinstance(overrides, dict):
        return {}

    selected_fields = allowed_fields or PUBLIC_FRONTEND_CONFIG_FIELDS
    filtered: dict[str, Any] = {}
    for key in selected_fields:
        if key in overrides:
            filtered[key] = overrides[key]

    if not filtered:
        return {}

    merged_values = _base_settings.model_dump(by_alias=True)
    merged_values.update(_get_public_frontend_config_fallback(fallback))
    merged_values.update(filtered)
    validated = Settings.model_validate(merged_values)
    normalized = validated.model_dump(by_alias=True)
    return {
        key: normalized[key]
        for key in PUBLIC_FRONTEND_CONFIG_FIELDS
        if key in normalized
    }


def normalize_public_frontend_config(
    overrides: dict[str, Any] | None,
    fallback: dict[str, Any] | None = None,
    allowed_fields: set[str] | None = None,
) -> dict[str, Any]:
    """对外暴露的公开配置规范化入口。"""
    normalized = _normalize_public_frontend_overrides(
        overrides,
        fallback=fallback,
        allowed_fields=allowed_fields,
    )
    if normalized:
        return normalized
    return _get_public_frontend_config_fallback(fallback)


def set_request_settings_overrides(overrides: dict[str, Any] | None) -> Token[dict[str, Any]]:
    """为当前请求设置临时配置覆盖。"""
    normalized = _normalize_public_frontend_overrides(overrides)
    return _request_settings_overrides.set(normalized)


def reset_request_settings_overrides(token: Token[dict[str, Any]]) -> None:
    """恢复当前请求之前的配置上下文。"""
    _request_settings_overrides.reset(token)


def get_settings() -> Settings:
    """返回当前上下文下生效的配置对象。"""
    overrides = _request_settings_overrides.get()
    if not overrides:
        return _base_settings

    merged_values = _base_settings.model_dump(by_alias=True)
    merged_values.update(overrides)
    return Settings.model_validate(merged_values)


class SettingsProxy:
    """把全局配置包装成按请求解析的代理。"""

    def __getattr__(self, name: str) -> Any:
        return getattr(get_settings(), name)


# 模块导入时先加载基础配置，再通过代理按请求叠加前端公开设置。
_base_settings = load_settings()
_public_frontend_config_seed = get_default_system_public_config()
settings = SettingsProxy()
