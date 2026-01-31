"""
Translation utilities for multi-language support.
"""

from app.rag.knowledge_base import generate_llm_answer


def translate_reply(reply: str, lang: str) -> str:
    """
    Translate reply to English or German if needed.

    Args:
        reply: Text to translate
        lang: Target language ('en' or 'de')

    Returns:
        Translated text or original if translation fails/not needed
    """
    if not reply or lang not in {"en", "de"}:
        return reply

    try:
        prompt = (
            f"Translate this to English, keep it natural and friendly:\n{reply}"
            if lang == "en"
            else f"Translate this to German/Deutsch, keep it natural and friendly:\n{reply}"
        )
        return generate_llm_answer(prompt, history=[])
    except Exception:
        return reply


def maybe_translate(text: str, target_lang: str) -> str:
    """
    Translate text to target language if needed.

    Args:
        text: Text to translate
        target_lang: Target language ('si', 'en', or 'de')

    Returns:
        Translated text or original
    """
    if target_lang not in {"en", "de"} or not text:
        return text

    try:
        prompt = (
            f"Translate this to English, keep it natural and friendly:\n{text}"
            if target_lang == "en"
            else f"Translate this to German/Deutsch, keep it natural and friendly:\n{text}"
        )
        return generate_llm_answer(prompt, history=[])
    except Exception:
        return text


def translate_response(text: str, target_lang: str) -> str:
    """
    Translate response based on detected reservation language.

    Args:
        text: Text to translate
        target_lang: Target language

    Returns:
        Translated text or original
    """
    if target_lang == "si" or target_lang is None:
        return text

    try:
        if target_lang == "en":
            prompt = f"Translate to English, natural and friendly, only translation:\n{text}"
        elif target_lang == "de":
            prompt = f"Translate to German, natural and friendly, only translation:\n{text}"
        else:
            return text
        return generate_llm_answer(prompt, history=[])
    except Exception:
        return text
