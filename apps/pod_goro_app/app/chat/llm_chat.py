"""
Direct LLM chat - core of Pod Goro V2 architecture.
One LLM call for info queries.
"""
from __future__ import annotations

import os
from pathlib import Path
from openai import OpenAI

from app.rag.search import get_context


_SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "system.txt"

_DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")


def _load_system_prompt() -> str:
    if _SYSTEM_PROMPT_PATH.exists():
        return _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()
    return "Si pomočnik Kmetije Pod Goro."


def chat(
    message: str,
    history: list[dict[str, str]] | None = None,
    client: OpenAI | None = None,
    model: str | None = None,
) -> dict[str, str]:
    """
    Main chat function for info queries.
    Returns {"reply": "..."}
    """
    if model is None:
        model = _DEFAULT_MODEL

    if client is None:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # Get RAG context
    rag_context = get_context(message, top_k=3)

    # Build conversation
    system_prompt = _load_system_prompt()
    if rag_context:
        system_prompt += f"\n\n## Dodatni kontekst iz baze znanja:\n{rag_context}"

    messages = [{"role": "system", "content": system_prompt}]

    # Add history (last 6 messages)
    if history:
        for msg in history[-6:]:
            messages.append(msg)

    messages.append({"role": "user", "content": message})

    # Single LLM call
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        max_completion_tokens=800,
    )

    reply = response.choices[0].message.content if response.choices else ""

    if not reply:
        reply = "Oprostite, nisem razumel vprašanja. Pokličite nas: 041 123 456"

    return {"reply": reply}
