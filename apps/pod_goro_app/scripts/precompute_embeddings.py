"""
Pre-compute embeddings za vse knowledge base chunke.

Zaženi enkrat po spremembi knowledge.jsonl:
    python scripts/precompute_embeddings.py

Ustvari: data/embeddings.json
"""

import json
import os
import sys
import time
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from openai import OpenAI
from app.rag.knowledge_base import KNOWLEDGE_CHUNKS, EMBEDDING_MODEL

# Output path
EMBEDDINGS_PATH = PROJECT_ROOT / "data" / "embeddings.json"


def get_client() -> OpenAI:
    """Get OpenAI client."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        # Try loading from .env
        env_path = PROJECT_ROOT / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("OPENAI_API_KEY="):
                    api_key = line.split("=", 1)[1].strip()
                    break

    if not api_key:
        raise RuntimeError("OPENAI_API_KEY ni nastavljen")

    return OpenAI(api_key=api_key)


def compute_embedding(client: OpenAI, text: str) -> list[float]:
    """Compute embedding for text."""
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text
    )
    return response.data[0].embedding


def main():
    print("=" * 60)
    print("PRE-COMPUTE EMBEDDINGS")
    print("=" * 60)

    print(f"\nChunkov: {len(KNOWLEDGE_CHUNKS)}")
    print(f"Model: {EMBEDDING_MODEL}")
    print(f"Output: {EMBEDDINGS_PATH}")

    # Ensure data directory exists
    EMBEDDINGS_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Load existing embeddings if any
    existing = {}
    if EMBEDDINGS_PATH.exists():
        try:
            existing = json.loads(EMBEDDINGS_PATH.read_text(encoding="utf-8"))
            print(f"Obstoječih embeddings: {len(existing)}")
        except Exception:
            pass

    client = get_client()
    embeddings = {}
    new_count = 0
    cached_count = 0

    start_time = time.time()

    for i, chunk in enumerate(KNOWLEDGE_CHUNKS):
        text = chunk.paragraph

        # Skip if already computed
        if text in existing:
            embeddings[text] = existing[text]
            cached_count += 1
            continue

        # Compute new embedding
        try:
            embedding = compute_embedding(client, text)
            embeddings[text] = embedding
            new_count += 1

            if new_count % 10 == 0:
                print(f"  Computed {new_count} new embeddings...")

        except Exception as e:
            print(f"  ERROR za chunk {i}: {e}")
            continue

    elapsed = time.time() - start_time

    # Save embeddings
    EMBEDDINGS_PATH.write_text(
        json.dumps(embeddings, ensure_ascii=False),
        encoding="utf-8"
    )

    print(f"\n" + "=" * 60)
    print(f"KONČANO!")
    print(f"  Novih: {new_count}")
    print(f"  Iz cache-a: {cached_count}")
    print(f"  Čas: {elapsed:.1f}s")
    print(f"  Shranjeno v: {EMBEDDINGS_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    main()
