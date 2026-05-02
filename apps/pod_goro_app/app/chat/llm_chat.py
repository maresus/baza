"""
Direct LLM chat - core of Pod Goro V2 architecture.
One LLM call for info queries.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Generator
from openai import OpenAI

from app.rag.search import get_context


_SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "system.txt"

_DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

_BOOKING_HINTS = {
    "room":    "Gost želi rezervirati SOBO. Odgovori toplo in osebno, nato naravno predlagaj rezervacijsko formo spodaj pod pogovorom.",
    "table":   "Gost želi rezervirati MIZO. Odgovori toplo, nato predlagaj formo spodaj pod pogovorom.",
    "bike":    "Gost želi izposoditi KOLESA. Odgovori toplo, nato predlagaj formo spodaj pod pogovorom.",
    "animals": "Gost sprašuje o HRANJENJU ŽIVALI. Pojasni aktivnost toplo, nato predlagaj formo spodaj.",
}


def _load_system_prompt() -> str:
    if _SYSTEM_PROMPT_PATH.exists():
        return _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()
    return "Si pomočnik Kmetije Pod Goro."


def _build_messages(
    message: str,
    history: list[dict[str, str]] | None,
    booking_type_hint: str | None,
) -> list[dict]:
    """Build messages list for OpenAI call."""
    rag_context = get_context(message, top_k=3)
    system_prompt = _load_system_prompt()

    from datetime import datetime
    _DAYS_SL = ["ponedeljek", "torek", "sreda", "četrtek", "petek", "sobota", "nedelja"]
    _now = datetime.now()
    system_prompt += (
        f"\n\nDanes je {_DAYS_SL[_now.weekday()]}, {_now.strftime('%-d. %-m. %Y')}. "
        f"Jutri je {_DAYS_SL[(_now.weekday()+1)%7]}."
    )

    if rag_context:
        system_prompt += f"\n\n## Dodatni kontekst iz baze znanja:\n{rag_context}"

    if booking_type_hint and booking_type_hint in _BOOKING_HINTS:
        system_prompt += f"\n\n## NAVODILO ZA TA ODGOVOR:\n{_BOOKING_HINTS[booking_type_hint]}"

    messages = [{"role": "system", "content": system_prompt}]

    if history:
        for msg in history[-6:]:
            messages.append(msg)

    messages.append({"role": "user", "content": message})
    return messages


def chat(
    message: str,
    history: list[dict[str, str]] | None = None,
    client: OpenAI | None = None,
    model: str | None = None,
    booking_type_hint: str | None = None,
) -> dict[str, str]:
    """Main chat function for info queries."""
    if model is None:
        model = _DEFAULT_MODEL
    if client is None:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    messages = _build_messages(message, history, booking_type_hint)

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        max_completion_tokens=800,
    )

    reply = response.choices[0].message.content if response.choices else ""
    if not reply:
        reply = "Oprostite, nisem razumel vprašanja. Pokličite nas: 041 123 456"

    return {"reply": reply}


def chat_stream(
    message: str,
    history: list[dict[str, str]] | None = None,
    client: OpenAI | None = None,
    model: str | None = None,
    booking_type_hint: str | None = None,
) -> Generator[str, None, None]:
    """Streaming chat — yields text chunks, ends with [DONE]."""
    if model is None:
        model = _DEFAULT_MODEL
    if client is None:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    messages = _build_messages(message, history, booking_type_hint)

    stream = client.chat.completions.create(
        model=model,
        messages=messages,
        max_completion_tokens=800,
        stream=True,
    )

    for chunk in stream:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            yield delta

    yield "[DONE]"
