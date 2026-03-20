"""Translation service via LLM provider.

Ported from v0.7.5 translate_server.py (port 8089).
Cloud mode: uses LLM provider for high-quality translation.
"""

from __future__ import annotations

SUPPORTED_LANGUAGES = {
    "zh": "Chinese", "en": "English", "ja": "Japanese", "ko": "Korean",
    "es": "Spanish", "fr": "French", "de": "German", "ru": "Russian",
    "ar": "Arabic", "pt": "Portuguese", "it": "Italian", "th": "Thai",
    "vi": "Vietnamese", "id": "Indonesian", "ms": "Malay", "nl": "Dutch",
    "pl": "Polish", "tr": "Turkish", "hi": "Hindi", "sv": "Swedish",
}


def detect_language(text: str) -> str:
    """Simple heuristic language detection via Unicode ranges."""
    for ch in text[:200]:
        cp = ord(ch)
        if 0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF:
            return "zh"
        if 0x3040 <= cp <= 0x309F or 0x30A0 <= cp <= 0x30FF:
            return "ja"
        if 0xAC00 <= cp <= 0xD7AF:
            return "ko"
        if 0x0600 <= cp <= 0x06FF:
            return "ar"
        if 0x0E00 <= cp <= 0x0E7F:
            return "th"
        if 0x0400 <= cp <= 0x04FF:
            return "ru"
    return "en"


async def translate_text(text: str, source: str = "auto", target: str = "en") -> dict:
    """Translate text using LLM provider."""
    from ..llm.provider import get_llm_provider

    if source == "auto":
        source = detect_language(text)

    src_name = SUPPORTED_LANGUAGES.get(source, source)
    tgt_name = SUPPORTED_LANGUAGES.get(target, target)

    messages = [
        {"role": "system", "content": f"You are a professional translator. Translate the following text from {src_name} to {tgt_name}. Output ONLY the translation, nothing else."},
        {"role": "user", "content": text},
    ]

    llm = get_llm_provider()
    result = await llm.chat(messages, max_tokens=4096, temperature=0.3)
    translated = result.get("content", "")

    return {
        "source_lang": source,
        "target_lang": target,
        "original": text,
        "translated": translated,
    }
