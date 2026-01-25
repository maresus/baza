# Chatbot Optimization Plan - Zdravstveni Center

## 🎯 Cilj
Preprečiti ciklanje, izboljšati zanesljivost odgovorov, zmanjšati stroške LLM klicev.

---

## 📋 Must-Have Optimizacije

### 1. **Hybrid Retrieval (BM25 + Vector)**
**Problem:** Samo vektorsko iskanje včasih zgreši ključne besede.
**Rešitev:** Kombinacija BM25 (keyword-based) + semantic search (embeddings).

**Implementacija:**
```python
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

# BM25 za keyword matching
bm25 = BM25Okapi(tokenized_corpus)
keyword_results = bm25.get_top_n(query, corpus, n=10)

# Vector search za semantic matching
model = SentenceTransformer('paraphrase-multilingual-mpnet-base-v2')
vector_results = vector_store.similarity_search(query, k=10)

# Merge + deduplicate
combined_results = merge_and_score(keyword_results, vector_results)
```

**Prioriteta:** 🔴 HIGH
**Effort:** Medium (2-3h)

---

### 2. **Re-ranker za Retrieval Rezultate**
**Problem:** Prvi retrieval lahko vrne neoptimalne rezultate.
**Rešitev:** Dodatna faza re-rankinga z cross-encoder modelom.

**Implementacija:**
```python
from sentence_transformers import CrossEncoder

reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')

# Re-rank retrieval results
pairs = [[query, doc] for doc in retrieved_docs]
scores = reranker.predict(pairs)
reranked = sorted(zip(retrieved_docs, scores), key=lambda x: x[1], reverse=True)
top_3 = [doc for doc, score in reranked[:3]]
```

**Prioriteta:** 🟡 MEDIUM
**Effort:** Low (1-2h)

---

### 3. **Stroga Validacija LLM Izhodov**
**Problem:** LLM lahko "halucinira" odgovore brez podlage.
**Rešitev:** Vsak odgovor mora biti podprt z virom/citatom.

**Implementacija:**
```python
def validate_answer(answer: str, sources: list[str]) -> bool:
    """Preveri, ali je odgovor podprt z viri."""
    # 1. Zahtevaj citation format: "... [vir: X]"
    if "[vir:" not in answer.lower():
        return False

    # 2. Preveri, ali je vsebina v virih
    for source in sources:
        if any(keyword in source.lower() for keyword in extract_keywords(answer)):
            return True

    return False

# V prompt template dodaj:
prompt += """
POMEMBNO: Vsak odgovor MORA vsebovati ekspliciten vir:
- "Cena laserskega posega je 150€ [vir: cenik.txt]"
- Če vir ne obstaja, odgovori: "Žal te informacije nimam na voljo."
"""
```

**Prioriteta:** 🔴 HIGH
**Effort:** Low (1-2h)

---

### 4. **Global Confidence Gating**
**Problem:** Bot odgovarja tudi, ko je negotov → napačne informacije.
**Rešitev:** Nizek confidence → "Ne vem" ali vprašaj za pojasnilo.

**Implementacija:**
```python
def get_answer_with_confidence(query: str, context: str) -> tuple[str, float]:
    # LLM mora vrniti tudi confidence score
    prompt = f"""
    Context: {context}
    Question: {query}

    Answer the question and rate your confidence (0.0-1.0):

    Answer: [your answer]
    Confidence: [0.0-1.0]
    """

    response = llm.complete(prompt)
    answer, confidence = parse_response(response)

    # Confidence threshold
    if confidence < 0.7:
        return "Žal nisem prepričan v ta odgovor. Lahko prosim razjasnite vprašanje?", confidence

    return answer, confidence
```

**Prioriteta:** 🔴 HIGH
**Effort:** Medium (2h)

---

### 5. **Cache za Retrieval + Odgovore**
**Problem:** Ponavljajoči LLM klici za ista vprašanja → visoki stroški.
**Rešitev:** Redis cache za retrieval in končne odgovore.

**Implementacija:**
```python
import redis
import hashlib

redis_client = redis.Redis(host='localhost', port=6379, db=0)

def cached_retrieval(query: str, ttl: int = 3600):
    cache_key = hashlib.md5(query.encode()).hexdigest()
    cached = redis_client.get(cache_key)

    if cached:
        return json.loads(cached)

    # Retrieve + cache
    results = retrieval_pipeline(query)
    redis_client.setex(cache_key, ttl, json.dumps(results))
    return results

def cached_llm_answer(query: str, context: str, ttl: int = 3600):
    cache_key = hashlib.md5(f"{query}:{context}".encode()).hexdigest()
    cached = redis_client.get(cache_key)

    if cached:
        return cached.decode()

    # LLM call + cache
    answer = llm.complete(query, context)
    redis_client.setex(cache_key, ttl, answer)
    return answer
```

**Prioriteta:** 🟡 MEDIUM
**Effort:** Medium (2-3h)

---

### 6. **Anti-Loop Logika**
**Problem:** Uporabnik ponovi isto vprašanje → bot se vrti v zanki.
**Rešitev:** Detekcija ponavljanja → clarification ali hand-off.

**Implementacija:**
```python
def detect_loop(conversation_history: list[dict]) -> bool:
    """Preveri, ali se zadnje 3 sporočila ponavljajo."""
    if len(conversation_history) < 3:
        return False

    last_3_questions = [msg["content"] for msg in conversation_history[-3:] if msg["role"] == "user"]

    # Semantic similarity check
    embeddings = embed_model.encode(last_3_questions)
    similarity = cosine_similarity(embeddings[0], embeddings[-1])

    return similarity > 0.85  # 85% podobnost = loop

# V chat flow:
if detect_loop(conversation_history):
    return "Opazil sem, da se vprašanje ponavlja. Lahko prosim podrobneje opišete, kaj vas zanima? Ali želite pogovor z osebjem?"
```

**Prioriteta:** 🔴 HIGH
**Effort:** Low (1-2h)

---

### 7. **Robustno "Affirmative/Confirm" Razumevanje**
**Problem:** "DA", "SEVEDA", "LAHKO" resetira flow namesto da nadaljuje.
**Rešitev:** Context-aware intent detection za potrditve.

**Implementacija:**
```python
AFFIRMATIVE_PATTERNS = [
    r'\b(da|ja|yes|seveda|lahko|ok|okay|v redu|sure|dobro)\b',
    r'\b(prosim|please|grem naprej|nadaljuj)\b'
]

def is_affirmative(message: str, context: dict) -> bool:
    """Preveri, ali je sporočilo potrditev (glede na kontekst)."""
    msg_lower = message.lower().strip()

    # 1. Pattern matching
    if any(re.search(pattern, msg_lower) for pattern in AFFIRMATIVE_PATTERNS):
        # 2. Context check: ali čakamo na potrditev?
        if context.get("waiting_for_confirmation"):
            return True

    return False

# V flow:
if is_affirmative(user_message, session_context):
    # Nadaljuj s prejšnjim flow, ne resetiraj
    return continue_previous_flow(session_context)
else:
    # Nov intent
    return handle_new_intent(user_message)
```

**Prioriteta:** 🔴 HIGH
**Effort:** Low (1h)

---

## 🗂️ Implementacijski Plan

### Faza 1 (Tedaj, 1 dan)
- ✅ Anti-loop logika
- ✅ Stroga validacija LLM izhodov
- ✅ Robustno affirmative razumevanje

### Faza 2 (Naslednji teden, 2 dni)
- 🔄 Hybrid retrieval (BM25 + vector)
- 🔄 Global confidence gating
- 🔄 Re-ranker

### Faza 3 (Opcijsko)
- ⏳ Redis cache za retrieval/odgovore

---

## 📊 Pričakovani Rezultati

| Metrika | Trenutno | Po optimizaciji |
|---------|----------|-----------------|
| Ciklanje | ~15% sessij | **<3%** |
| Halucinacije | ~10% odgovorov | **<2%** |
| LLM stroški | 100% | **~60%** (cache) |
| Confidence | N/A | **>85%** povprečje |
| Retrieval accuracy | ~70% | **>90%** (hybrid + rerank) |

---

## 🔧 Datoteke za Spremembe

1. **app/services/chat_router.py** - Anti-loop, affirmative handling
2. **app/core/retrieval.py** - Hybrid search, re-ranking
3. **app/core/llm_service.py** - Confidence gating, validation
4. **app/core/cache.py** - Redis cache layer (new)
5. **app/prompts/system_prompt.txt** - Strožji prompt za citations

---

## 📝 Testiranje

### Anti-loop test:
```python
conversation = [
    {"role": "user", "content": "Koliko stane pregled?"},
    {"role": "assistant", "content": "Ortopedski pregled stane 80€."},
    {"role": "user", "content": "Koliko stane pregled?"},  # Ponavljanje
]
# Pričakovan output: "Opazil sem, da se vprašanje ponavlja..."
```

### Affirmative test:
```python
context = {"waiting_for_confirmation": True, "last_intent": "book_appointment"}
user_message = "Da, prosim"
# Pričakovan output: Nadaljuje z booking flow, ne resetira
```

### Confidence test:
```python
query = "Koliko stane redek poseg XYZ?"
# Če confidence < 0.7 → "Žal nisem prepričan..."
```

---

## 🚀 Deployment

Po implementaciji:
1. Test na staging okolju z 50 testnimi query-ji
2. A/B test (50% prometa na novo verzijo)
3. Monitor metrics: loop rate, hallucination rate, cache hit rate
4. Full rollout po 1 tednu testiranja

---

**Version:** 1.0.0
**Created:** 2026-01-25
**Status:** 🟡 Plan - Ready for implementation
