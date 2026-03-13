import re
from functools import lru_cache

import tiktoken


DEFAULT_TOKENIZER_ENCODING = "cl100k_base"
SENTENCE_BREAK_PATTERN = re.compile(r"(?<=[。！？!?；;：:])\s+|(?<=[。！？!?；;：:])")


def normalize_embedding_text(text: str) -> str:
    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    paragraphs = []

    for paragraph in re.split(r"\n\s*\n", normalized):
        collapsed = re.sub(r"\s+", " ", paragraph).strip()
        if collapsed:
            paragraphs.append(collapsed)

    return "\n\n".join(paragraphs).strip()


@lru_cache(maxsize=16)
def _get_tokenizer(model_name: str, encoding_name: str):
    resolved_model = model_name.strip()
    resolved_encoding = encoding_name.strip() or DEFAULT_TOKENIZER_ENCODING

    if resolved_model:
        try:
            return tiktoken.encoding_for_model(resolved_model)
        except KeyError:
            pass

    try:
        return tiktoken.get_encoding(resolved_encoding)
    except KeyError:
        return tiktoken.get_encoding(DEFAULT_TOKENIZER_ENCODING)


def _encode_text(text: str, tokenizer_model: str, tokenizer_encoding: str) -> list[int]:
    tokenizer = _get_tokenizer(tokenizer_model, tokenizer_encoding)
    return tokenizer.encode(text)


def _decode_tokens(tokens: list[int], tokenizer_model: str, tokenizer_encoding: str) -> str:
    tokenizer = _get_tokenizer(tokenizer_model, tokenizer_encoding)
    return tokenizer.decode(tokens)


def count_tokens(text: str, tokenizer_model: str = "", tokenizer_encoding: str = DEFAULT_TOKENIZER_ENCODING) -> int:
    normalized = normalize_embedding_text(text)
    if not normalized:
        return 0
    return len(_encode_text(normalized, tokenizer_model, tokenizer_encoding))


def _split_semantic_units(text: str) -> list[str]:
    units: list[str] = []

    for paragraph in text.split("\n\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            continue

        sentences = [
            sentence.strip()
            for sentence in SENTENCE_BREAK_PATTERN.split(paragraph)
            if sentence.strip()
        ]

        if len(sentences) <= 1:
            units.append(paragraph)
            continue

        units.extend(sentences)

    return units or ([text] if text else [])


def _join_units(left: str, right: str) -> str:
    if not left:
        return right
    if not right:
        return left
    return f"{left}\n\n{right}"


def _split_text_by_tokens(
    text: str,
    chunk_tokens: int,
    overlap_tokens: int,
    tokenizer_model: str,
    tokenizer_encoding: str,
) -> list[str]:
    token_ids = _encode_text(text, tokenizer_model, tokenizer_encoding)
    if not token_ids:
        return []

    window_tokens = max(int(chunk_tokens), 1)
    overlap = max(0, min(int(overlap_tokens), window_tokens - 1))
    step = max(window_tokens - overlap, 1)
    chunks: list[str] = []

    start = 0
    while start < len(token_ids):
        end = min(start + window_tokens, len(token_ids))
        piece = _decode_tokens(token_ids[start:end], tokenizer_model, tokenizer_encoding).strip()
        if piece and (not chunks or chunks[-1] != piece):
            chunks.append(piece)

        if end >= len(token_ids):
            break

        start += step

    return chunks


def _tail_text_by_tokens(
    text: str,
    overlap_tokens: int,
    tokenizer_model: str,
    tokenizer_encoding: str,
) -> str:
    overlap = max(int(overlap_tokens), 0)
    if overlap <= 0:
        return ""

    token_ids = _encode_text(text, tokenizer_model, tokenizer_encoding)
    if not token_ids:
        return ""

    return _decode_tokens(token_ids[-overlap:], tokenizer_model, tokenizer_encoding).strip()


def _fit_overlap_seed(
    seed: str,
    next_unit: str,
    max_tokens: int,
    tokenizer_model: str,
    tokenizer_encoding: str,
) -> str:
    fitted = seed.strip()
    if not fitted:
        return ""

    while fitted and count_tokens(
        _join_units(fitted, next_unit),
        tokenizer_model,
        tokenizer_encoding,
    ) > max_tokens:
        seed_tokens = _encode_text(fitted, tokenizer_model, tokenizer_encoding)
        if len(seed_tokens) <= 1:
            return ""

        drop_count = max(1, min(8, len(seed_tokens) // 4 or 1))
        fitted = _decode_tokens(seed_tokens[drop_count:], tokenizer_model, tokenizer_encoding).strip()

    return fitted


def split_text_for_embedding(
    text: str,
    max_tokens: int,
    target_tokens: int,
    overlap_tokens: int,
    tokenizer_model: str = "",
    tokenizer_encoding: str = DEFAULT_TOKENIZER_ENCODING,
) -> list[str]:
    normalized = normalize_embedding_text(text)
    if not normalized:
        return []

    hard_limit = max(int(max_tokens), 1)
    preferred_limit = min(max(int(target_tokens), 1), hard_limit)
    overlap = max(0, min(int(overlap_tokens), preferred_limit - 1 if preferred_limit > 1 else 0))

    if count_tokens(normalized, tokenizer_model, tokenizer_encoding) <= preferred_limit:
        return [normalized]

    prepared_units: list[str] = []
    for unit in _split_semantic_units(normalized):
        unit = unit.strip()
        if not unit:
            continue

        if count_tokens(unit, tokenizer_model, tokenizer_encoding) <= hard_limit:
            prepared_units.append(unit)
            continue

        prepared_units.extend(
            _split_text_by_tokens(
                unit,
                chunk_tokens=preferred_limit,
                overlap_tokens=overlap,
                tokenizer_model=tokenizer_model,
                tokenizer_encoding=tokenizer_encoding,
            )
        )

    chunks: list[str] = []
    current = ""

    for unit in prepared_units:
        candidate = _join_units(current, unit)
        candidate_tokens = count_tokens(candidate, tokenizer_model, tokenizer_encoding)

        if current and candidate_tokens > preferred_limit:
            chunks.append(current)
            overlap_seed = _tail_text_by_tokens(
                current,
                overlap,
                tokenizer_model,
                tokenizer_encoding,
            )
            current = _fit_overlap_seed(
                overlap_seed,
                unit,
                max_tokens=hard_limit,
                tokenizer_model=tokenizer_model,
                tokenizer_encoding=tokenizer_encoding,
            )
            candidate = _join_units(current, unit)
            candidate_tokens = count_tokens(candidate, tokenizer_model, tokenizer_encoding)

        if candidate_tokens > hard_limit:
            if current:
                chunks.append(current)
                current = ""

            chunks.extend(
                _split_text_by_tokens(
                    unit,
                    chunk_tokens=preferred_limit,
                    overlap_tokens=overlap,
                    tokenizer_model=tokenizer_model,
                    tokenizer_encoding=tokenizer_encoding,
                )
            )
            continue

        current = candidate

    if current:
        chunks.append(current)

    deduplicated: list[str] = []
    for chunk in chunks:
        cleaned = normalize_embedding_text(chunk)
        if cleaned and (not deduplicated or deduplicated[-1] != cleaned):
            deduplicated.append(cleaned)

    return deduplicated or [normalized]