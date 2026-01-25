# Anti-Loop & Robustnost Guide - Zdravstveni Center Bot

**Verzija:** 1.0
**Datum:** 2026-01-25
**Status:** 🔴 KRITIČNO - implementiraj ASAP

---

## 🎯 Cilj

Prepreči ciklanje in nezanesljive odgovore z minimalnimi, praktičnimi ukrepi.

---

## 1️⃣ Anti-Loop Guard

### Problem
Uporabnik ponovi isto vprašanje 2-3x → bot se vrti v zanki.

### Rešitev
```python
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

class ConversationTracker:
    def __init__(self):
        self.recent_questions = []  # Zadnja 3 user sporočila
        self.embeddings = []

    def detect_loop(self, new_message: str, embedding_model) -> bool:
        """Preveri ponavljanje zadnjih 2-3 vprašanj."""
        if len(self.recent_questions) < 2:
            return False

        # Embedaj novo sporočilo
        new_emb = embedding_model.encode(new_message)

        # Preveri podobnost z zadnjimi 2-3 sporočili
        for prev_emb in self.embeddings[-3:]:
            similarity = cosine_similarity([new_emb], [prev_emb])[0][0]
            if similarity > 0.9:  # 90% podobnost = loop
                return True

        return False

    def add_message(self, message: str, embedding):
        """Dodaj sporočilo v zgodovino."""
        self.recent_questions.append(message)
        self.embeddings.append(embedding)
        # Obdrži samo zadnje 3
        if len(self.recent_questions) > 3:
            self.recent_questions.pop(0)
            self.embeddings.pop(0)

# V chat_router.py
tracker = ConversationTracker()

@router.post("/chat")
async def chat(request: ChatRequest):
    # ...
    if tracker.detect_loop(request.message, embed_model):
        return {
            "response": "Vidim, da se vrtiva. Prosím, povejte samo:\n- Storitev (npr. ortoped)\n- Datum (npr. 15.2.)\n- Ura (npr. 14:00)",
            "needs_clarification": True
        }

    # Če se ponovi ŠE enkrat po tem opozorilu
    if tracker.loop_count >= 2:
        return {
            "response": "Za pomoč me prosim kontaktirajte na info@zdravstveni-center.si ali pokličite 01 234 5678.",
            "handoff": True
        }
```

**Datoteka:** `app/services/chat_router.py`
**LOC:** ~50 linij
**Effort:** 1-2h

---

## 2️⃣ Strict Confirmation Handling

### Problem
Bot: "Potrdite termin 15.2. ob 14:00?"
User: "Da"
→ Bot reseta flow namesto da nadaljuje.

### Rešitev
```python
class FlowState:
    """Hrani trenutni flow state."""
    waiting_for_confirmation: bool = False
    pending_action: str = None  # "book_appointment", "cancel", etc.
    pending_data: dict = {}  # {date: "15.02.2026", time: "14:00", ...}

AFFIRMATIVE_KEYWORDS = {
    "da", "ja", "yes", "seveda", "lahko", "ok", "okay",
    "v redu", "sure", "dobro", "prosim", "please", "grem naprej"
}

def is_affirmative(message: str) -> bool:
    """Preveri, ali je sporočilo potrditev."""
    tokens = message.lower().strip().split()
    # Če je kratko (1-2 besedi) in vsebuje affirmative keyword
    if len(tokens) <= 2:
        return any(word in AFFIRMATIVE_KEYWORDS for word in tokens)
    return False

@router.post("/chat")
async def chat(request: ChatRequest):
    session = get_session(request.session_id)
    message = request.message.strip()

    # STRICT CONFIRMATION: če čakamo potrditev
    if session.flow_state.waiting_for_confirmation:
        if is_affirmative(message):
            # Nadaljuj s pending action, NE resetiraj
            action = session.flow_state.pending_action
            data = session.flow_state.pending_data

            if action == "book_appointment":
                # Ustvari termin
                reservation_id = create_reservation(
                    date=data["date"],
                    time=data["time"],
                    location=data["service"],
                    name=data.get("name"),
                    phone=data.get("phone"),
                    email=data.get("email")
                )
                return {"response": f"✅ Termin rezerviran! ID: {reservation_id}"}

            elif action == "change_time":
                # Spremeni uro
                # ...

        else:
            # Če NIJE potrditev, interpretiraj kot spremembo
            session.flow_state.waiting_for_confirmation = False
            # Parse new intent
            # ...

    # Normalen flow
    # ...
```

**Datoteka:** `app/services/chat_router.py`
**LOC:** ~30 linij
**Effort:** 1h

---

## 3️⃣ Global Confidence Gating

### Problem
Bot odgovarja tudi, ko ni prepričan → napačne informacije.

### Rešitev
```python
def get_retrieval_confidence(query: str, retrieved_docs: list) -> float:
    """Izračunaj confidence score za retrieval."""
    if not retrieved_docs:
        return 0.0

    # Preveri overlap ključnih besed
    query_tokens = set(query.lower().split())
    doc_tokens = set(" ".join([d.page_content for d in retrieved_docs]).lower().split())
    overlap = len(query_tokens & doc_tokens) / len(query_tokens) if query_tokens else 0

    # Preveri semantic similarity (če dostopen)
    avg_similarity = np.mean([doc.metadata.get("score", 0) for doc in retrieved_docs])

    # Kombiniraj
    confidence = (overlap * 0.5) + (avg_similarity * 0.5)
    return confidence

CONFIDENCE_THRESHOLD = 0.6  # 60% minimalna zanesljivost

@router.post("/chat")
async def chat(request: ChatRequest):
    # Retrieve docs
    retrieved_docs = retriever.get_relevant_documents(request.message)

    # Preveri confidence
    confidence = get_retrieval_confidence(request.message, retrieved_docs)

    if confidence < CONFIDENCE_THRESHOLD:
        # NE odgovarjaj vsebinsko, vprašaj konkretno
        return {
            "response": "Nisem prepričan, da pravilno razumem. Lahko pojasnite:\n- Za katero storitev vas zanima? (dermatolog / ortoped / okulist / ...)\n- Za kateri datum?",
            "confidence": confidence,
            "needs_clarification": True
        }

    # Nadaljuj z normalnim odgovorom
    # ...
```

**Datoteka:** `app/services/chat_router.py`
**LOC:** ~40 linij
**Effort:** 1-2h

---

## 4️⃣ Stroga Validacija LLM Odgovora

### Problem
LLM si izmisli odgovore brez podlage v virih.

### Rešitev
```python
SYSTEM_PROMPT = """
Ti si zdravstveni center asistent. KRITIČNO PRAVILO:

- Odgovarjaj SAMO na podlagi podanih virov (Context).
- Če informacije NI v virih, odgovori: "Tega v bazi nimam. Prosim pokličite 01 234 5678 ali pošljite email na info@zdravstveni-center.si"
- NIKOLI si ne izmisli cen, terminov, ali drugih podatkov.
- Vedno citiraj vir: "Cena je 80€ [vir: cenik.txt]"

Context:
{context}

Question: {question}

Answer (z virom):
"""

def validate_answer_has_source(answer: str, context_docs: list) -> bool:
    """Preveri, ali je odgovor podprt z virom."""
    # 1. Preveri, ali vsebuje vsaj nekaj ključnih besed iz context
    context_text = " ".join([doc.page_content for doc in context_docs]).lower()
    answer_tokens = set(answer.lower().split())
    context_tokens = set(context_text.split())

    overlap = len(answer_tokens & context_tokens)
    if overlap < 3:  # Manj kot 3 skupne besede = verjetno izmišljen
        return False

    # 2. Preveri citation format
    if "[vir:" not in answer.lower():
        return False

    return True

@router.post("/chat")
async def chat(request: ChatRequest):
    # ...
    answer = llm.complete(prompt)

    # Validacija
    if not validate_answer_has_source(answer, retrieved_docs):
        return {
            "response": "Oprostite, te informacije trenutno nimam v bazi. Za več kontaktirajte info@zdravstveni-center.si",
            "validation_failed": True
        }

    return {"response": answer}
```

**Datoteka:** `app/services/chat_router.py`
**LOC:** ~30 linij
**Effort:** 1h

---

## 5️⃣ Hybrid Retrieval (BM25 + Vector)

### Problem
Samo vektorsko iskanje zgreši natančne ključne besede.

### Rešitev
```python
from rank_bm25 import BM25Okapi
from typing import List

class HybridRetriever:
    def __init__(self, vector_store, documents: List[str]):
        self.vector_store = vector_store
        # Pripravi BM25
        tokenized_docs = [doc.lower().split() for doc in documents]
        self.bm25 = BM25Okapi(tokenized_docs)
        self.documents = documents

    def retrieve(self, query: str, k: int = 5) -> List[str]:
        """Hybrid retrieval: BM25 + Vector."""
        # 1. BM25 retrieval (keyword-based)
        tokenized_query = query.lower().split()
        bm25_scores = self.bm25.get_scores(tokenized_query)
        bm25_top_indices = np.argsort(bm25_scores)[-k:]

        # 2. Vector retrieval (semantic)
        vector_results = self.vector_store.similarity_search(query, k=k)

        # 3. Merge & deduplicate
        combined = {}
        for idx in bm25_top_indices:
            combined[self.documents[idx]] = bm25_scores[idx] * 0.4  # 40% weight

        for doc in vector_results:
            if doc.page_content in combined:
                combined[doc.page_content] += doc.metadata.get("score", 0) * 0.6  # 60% weight
            else:
                combined[doc.page_content] = doc.metadata.get("score", 0) * 0.6

        # Sort by combined score
        sorted_docs = sorted(combined.items(), key=lambda x: x[1], reverse=True)
        return [doc for doc, score in sorted_docs[:k]]

# Uporaba
retriever = HybridRetriever(vector_store, all_documents)
results = retriever.retrieve("Koliko stane ortopedski pregled?", k=3)
```

**Datoteka:** `app/core/retrieval.py` (nova)
**LOC:** ~50 linij
**Effort:** 2h

**Dependencija:**
```bash
pip install rank-bm25
```

---

## 6️⃣ Cache Query Rezultatov

### Problem
Isti LLM klici za ista vprašanja → visoki stroški.

### Rešitev
```python
import hashlib
from functools import lru_cache
from datetime import datetime, timedelta

# Simple in-memory cache (ali Redis)
CACHE = {}
CACHE_TTL = timedelta(hours=24)

def cache_key(query: str, context: str) -> str:
    """Generiraj cache key."""
    combined = f"{query}:{context}"
    return hashlib.md5(combined.encode()).hexdigest()

def get_cached_answer(query: str, context: str):
    """Preveri cache."""
    key = cache_key(query, context)
    if key in CACHE:
        cached_data, timestamp = CACHE[key]
        if datetime.now() - timestamp < CACHE_TTL:
            return cached_data
        else:
            del CACHE[key]  # Expired
    return None

def set_cached_answer(query: str, context: str, answer: str):
    """Shrani v cache."""
    key = cache_key(query, context)
    CACHE[key] = (answer, datetime.now())

@router.post("/chat")
async def chat(request: ChatRequest):
    # Retrieve context
    context = retriever.retrieve(request.message)
    context_str = "\n".join(context)

    # Check cache
    cached = get_cached_answer(request.message, context_str)
    if cached:
        return {"response": cached, "cached": True}

    # LLM call
    answer = llm.complete(request.message, context_str)

    # Cache result
    set_cached_answer(request.message, context_str, answer)

    return {"response": answer, "cached": False}
```

**Datoteka:** `app/core/cache.py` (nova)
**LOC:** ~40 linij
**Effort:** 1h

---

## 7️⃣ Omeji "Help" in "Greeting" Reset

### Problem
"Pozdravljeni" ali "OK" resetira aktivni flow.

### Rešitev
```python
GREETING_PATTERNS = ["pozdrav", "zdravo", "hej", "hello", "hi"]
HELP_PATTERNS = ["pomoč", "help", "ne razumem"]

def is_greeting_or_help(message: str) -> bool:
    """Preveri, ali je sporočilo pozdrav ali help."""
    msg_lower = message.lower()
    if any(pattern in msg_lower for pattern in GREETING_PATTERNS):
        return True
    if any(pattern in msg_lower for pattern in HELP_PATTERNS):
        return True
    return False

@router.post("/chat")
async def chat(request: ChatRequest):
    session = get_session(request.session_id)

    # FLOW PRESERVATION: če je flow aktiven, ne resetiraj
    if session.flow_state.active_flow:
        if is_greeting_or_help(request.message):
            # Ignoriraj greeting, nadaljuj flow
            return {
                "response": f"Nadaljujeva z rezervacijo. {session.flow_state.next_prompt}",
                "flow_preserved": True
            }

    # Če ni aktivnega flowa, normalno obravnavaj
    if is_greeting_or_help(request.message):
        return {"response": "Pozdravljen! Kako vam lahko pomagam?"}

    # Normalen flow
    # ...
```

**Datoteka:** `app/services/chat_router.py`
**LOC:** ~20 linij
**Effort:** 30min

---

## 📋 Implementacijski Checklist

### Faza 1 - KRITIČNO (1 dan)
- [ ] Anti-loop guard (detector ponavljanja)
- [ ] Strict confirmation handling ("da" ne resetira)
- [ ] Confidence gating (ne odgovarjaj, če si negotov)
- [ ] Stroga validacija LLM (samo iz virov)

### Faza 2 - POMEMBNO (2 dni)
- [ ] Hybrid retrieval (BM25 + vector)
- [ ] Cache query rezultatov
- [ ] Omeji greeting/help reset

### Testiranje
- [ ] Test loop detection (3x isto vprašanje)
- [ ] Test confirmation flow (DA po "Potrdite?")
- [ ] Test low confidence (nejasen query)
- [ ] Test source validation (LLM output)
- [ ] Test cache hit rate (ponavljajoče query)

---

## 🎯 Pričakovani Rezultati

| Metrika | Prej | Po implementaciji |
|---------|------|-------------------|
| Loop rate | ~15% | **<2%** |
| False positives | ~10% | **<3%** |
| Cache hit rate | 0% | **~40%** |
| LLM cost | 100% | **~60%** |

---

## 🔧 Datoteke za Spremembe

1. `app/services/chat_router.py` - Glavna logika (vseh 7 ukrepov)
2. `app/core/retrieval.py` - Hybrid retriever (nova)
3. `app/core/cache.py` - Cache layer (nova)
4. `app/models/flow_state.py` - FlowState model (nova ali update)

---

## 📝 Testni Scenariji

### Test 1: Loop Detection
```
User: "Koliko stane pregled?"
Bot: "Ortopedski pregled stane 80€."
User: "Koliko stane pregled?"
Bot: "Ortopedski pregled stane 80€."
User: "Koliko stane pregled?"
Bot: "Vidim, da se vrtiva. Prosím, povejte samo: Storitev + Datum + Ura."
```

### Test 2: Confirmation Handling
```
User: "Rezerviraj ortopedski pregled 15.2. ob 14:00"
Bot: "Potrdite rezervacijo: Ortoped, 15.2.2026, 14:00?"
User: "Da"
Bot: "✅ Termin rezerviran! ID: 12345"  ← NE resetira flow
```

### Test 3: Confidence Gating
```
User: "Kdaj je odprt ambulanta za zobe?"
Bot retrieval confidence: 0.4 (nizka)
Bot: "Nisem prepričan. Za katero storitev vas zanima? (dermatolog/ortoped/okulist/...)"
```

### Test 4: Source Validation
```
LLM output: "Laserski poseg stane 500€"  ← BREZ [vir: ...]
Validation: FAIL
Bot: "Oprostite, te informacije trenutno nimam v bazi."
```

---

**Version:** 1.0.0
**Status:** 🔴 READY TO IMPLEMENT
**Priority:** CRITICAL
