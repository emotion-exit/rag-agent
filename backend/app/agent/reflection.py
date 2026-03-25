from __future__ import annotations

import json
import re
from dataclasses import dataclass

REFLECTION_TAG_NAME = "reflection"
FINAL_ANSWER_TAG_NAME = "final_answer"

_ALLOWED_FLAG_VALUES = {"yes", "no"}
_ALLOWED_SUPPORT_VALUES = {"yes", "partial", "no"}


@dataclass(frozen=True)
class ReflectionVerdict:
    is_relevant: bool
    is_supported: str
    citation_complete: bool
    should_abstain: bool
    unsupported_points: tuple[str, ...]

    def blocks_answer(self) -> bool:
        return (
            self.should_abstain
            or not self.is_relevant
            or self.is_supported == "no"
            or not self.citation_complete
        )


def build_reflection_instruction(no_answer: str, token_budget: int) -> str:
    normalized_token_budget = max(int(token_budget or 0), 0)
    if normalized_token_budget <= 0:
        return "最终答案必须直接输出可渲染的 Markdown 正文，不要输出 reflection、思维链或其他隐藏标签。"

    return (
        "在输出最终答案前，必须先输出一个隐藏的 reflection 块，再输出 final_answer 块。\n"
        f"如果 reflection 判断无法可靠回答，final_answer 必须原样输出：{no_answer}\n"
        f"reflection 块尽量控制在 {normalized_token_budget} 个 tokens 以内，保持极简。\n"
        "严格使用以下结构，不要添加其他标签：\n"
        f"<{REFLECTION_TAG_NAME}>"
        '{"is_relevant":"yes|no","is_supported":"yes|partial|no","citation_complete":"yes|no","should_abstain":"yes|no","unsupported_points":["最多两条短语"]}'
        f"</{REFLECTION_TAG_NAME}>\n"
        f"<{FINAL_ANSWER_TAG_NAME}>给用户的最终 Markdown 答案</{FINAL_ANSWER_TAG_NAME}>\n"
        "reflection 要求：\n"
        "1. is_relevant 表示答案是否直接回应用户问题。\n"
        "2. is_supported 表示关键结论是否都被本轮知识片段支持。\n"
        "3. citation_complete 表示每个关键句后是否都带了来源编号。\n"
        "4. should_abstain 表示是否应直接拒答。\n"
        "5. unsupported_points 只允许填写最多两条简短短语；没有则返回空数组。\n"
        "6. 不要在 reflection 中写长篇解释或思维链。"
    )


def extract_tag_content(text: str, tag_name: str) -> str:
    match = re.search(
        rf"<{tag_name}>\s*(.*?)\s*</{tag_name}>",
        text or "",
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return ""
    return match.group(1).strip()


def _extract_json_object(raw_text: str) -> dict | None:
    text = str(raw_text or "").strip()
    if not text:
        return None

    candidates = [text]
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        candidates.insert(0, match.group(0))

    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload

    return None


def parse_reflection_verdict(text: str) -> ReflectionVerdict | None:
    payload = _extract_json_object(extract_tag_content(text, REFLECTION_TAG_NAME))
    if not payload:
        return None

    relevant = str(payload.get("is_relevant", "")).strip().lower()
    supported = str(payload.get("is_supported", "")).strip().lower()
    citation_complete = str(payload.get("citation_complete", "")).strip().lower()
    should_abstain = str(payload.get("should_abstain", "")).strip().lower()

    if relevant not in _ALLOWED_FLAG_VALUES:
        return None
    if citation_complete not in _ALLOWED_FLAG_VALUES:
        return None
    if should_abstain not in _ALLOWED_FLAG_VALUES:
        return None
    if supported not in _ALLOWED_SUPPORT_VALUES:
        return None

    raw_unsupported = payload.get("unsupported_points", [])
    unsupported_points: list[str] = []
    if isinstance(raw_unsupported, list):
        for item in raw_unsupported:
            normalized = str(item or "").strip()
            if normalized:
                unsupported_points.append(normalized)
            if len(unsupported_points) >= 2:
                break

    return ReflectionVerdict(
        is_relevant=relevant == "yes",
        is_supported=supported,
        citation_complete=citation_complete == "yes",
        should_abstain=should_abstain == "yes",
        unsupported_points=tuple(unsupported_points),
    )
