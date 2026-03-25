from __future__ import annotations

import openai
from google.adk.models.lite_llm import LiteLlm

from app.config import settings

AUXILIARY_COMPLETION_TIMEOUT_SECONDS = 8.0


def build_llm() -> LiteLlm:
    """构建对话模型实例。"""
    return LiteLlm(
        model=f"openai/{settings.chat_model}",
        api_key=settings.chat_api_key,
        api_base=settings.chat_base_url,
        temperature=settings.chat_temperature,
        headers=settings.get_chat_headers(),
    )


def _build_auxiliary_client() -> openai.OpenAI:
    return openai.OpenAI(
        api_key=settings.chat_api_key,
        base_url=settings.chat_base_url,
        default_headers=settings.get_chat_headers(),
        timeout=AUXILIARY_COMPLETION_TIMEOUT_SECONDS,
        max_retries=1,
    )


def run_auxiliary_completion(system_prompt: str, user_prompt: str) -> str:
    """调用同一套聊天模型做检索辅助任务。"""
    if not settings.chat_api_key.strip() or not settings.chat_model.strip() or not settings.chat_base_url.strip():
        return ""

    try:
        client = _build_auxiliary_client()
        response = client.chat.completions.create(
            model=settings.chat_model,
            temperature=0.0,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
    except Exception:
        return ""

    message = response.choices[0].message if response.choices else None
    return str(getattr(message, "content", "") or "").strip()
