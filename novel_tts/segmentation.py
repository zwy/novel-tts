# novel_tts/segmentation.py
import re


def split_chapter_text(text: str, min_chars: int = 120, max_chars: int = 220) -> list[str]:
    cleaned = re.sub(r"\s+", "", text)
    if not cleaned:
        return []

    sentences = re.split(r"(?<=[。！？；])", cleaned)
    chunks: list[str] = []
    buffer = ""

    for sentence in sentences:
        if not sentence:
            continue
        if len(buffer) + len(sentence) <= max_chars:
            buffer += sentence
            if len(buffer) >= min_chars:
                chunks.append(buffer)
                buffer = ""
            continue
        if buffer:
            chunks.append(buffer)
            buffer = ""
        if len(sentence) <= max_chars:
            buffer = sentence
            continue

        comma_parts = re.split(r"(?<=，)", sentence)
        long_buf = ""
        for p in comma_parts:
            if len(long_buf) + len(p) <= max_chars:
                long_buf += p
            else:
                if long_buf:
                    chunks.append(long_buf)
                long_buf = p
        if long_buf:
            buffer = long_buf

    if buffer:
        chunks.append(buffer)

    merged: list[str] = []
    for c in chunks:
        if merged and len(merged[-1]) < min_chars and len(merged[-1]) + len(c) <= max_chars:
            merged[-1] += c
        else:
            merged.append(c)
    return merged
