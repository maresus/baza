"""
Test RAG speed vs Full KB
"""
import time
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.rag.knowledge_base import generate_llm_answer

def test_rag():
    """Test RAG z realnimi vprašanji."""

    questions = [
        "A imate zajčke?",
        "Koliko stane nočitev?",
        "Kdaj ste odprti?",
        "Kaj je na jedilniku?",
        "Kje se nahajate?",
    ]

    print("=" * 60)
    print("RAG SPEED TEST")
    print("=" * 60)

    total_time = 0

    for q in questions:
        print(f"\n📝 Vprašanje: {q}")

        start = time.time()
        answer = generate_llm_answer(q)
        elapsed = time.time() - start
        total_time += elapsed

        print(f"⏱️  Čas: {elapsed:.2f}s")
        print(f"💬 Odgovor: {answer[:200]}...")

    print("\n" + "=" * 60)
    print(f"POVPREČNI ČAS: {total_time / len(questions):.2f}s")
    print("=" * 60)

if __name__ == "__main__":
    test_rag()
