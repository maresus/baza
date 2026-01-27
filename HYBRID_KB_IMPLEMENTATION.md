# Hybrid Knowledge Base Implementation

## Pregled implementacije

Implementirali smo tri napredno RAG funkcionalnosti za ZDRAVSTVENI CENTER projekt:

1. **Hybrid Retrieval (BM25 + Vector Embeddings)**
2. **Cross-Encoder Re-ranking**
3. **Enhanced Global Confidence Gating**

---

## 1. Hybrid Retrieval System

### Opis
Kombinira keyword-based search (BM25) s semantic search (OpenAI embeddings) za boljšo natančnost iskanja.

### Komponente

#### BM25 Index
- Slovenian tokenization z stop word filtering
- IDF-based relevance scoring
- Optimiziran za majhne kolekcije dokumentov

#### Vector Store
- OpenAI embeddings (text-embedding-ada-002)
- Cosine similarity search
- In-memory storage

#### Hybrid Search
- Weighted combination: `score = (1-α) * BM25 + α * Vector`
- Default α=0.5 (enaka teža za oba)
- Normalizacija rezultatov na 0-1

### Datoteke
- `app/services/knowledge_base.py` - Nova implementacija
- `app/services/chat_router.py` - Integracija

### Inicializacija
```python
# Avtomatsko se inicializira ob prvem query-ju z INFO_RESPONSES
kb_module.initialize_knowledge_base(
    documents=INFO_RESPONSES,
    alpha=0.5,
    use_reranker=True
)
```

---

## 2. Cross-Encoder Re-ranker

### Opis
Uporablja cross-encoder model za re-ranking inicijalnih rezultatov. Cross-encoder vidi query in dokument skupaj, kar omogoča bolj natančno relevance scoring.

### Model
- `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`
- Multilingual model (podpira slovenščino)
- Trained on MS Marco dataset

### Delovanje
1. Hybrid search vrne top kandidate (top_k * 3)
2. Re-ranker oceni relevantnost vsakega para (query, document)
3. Rezultati se ponovno razvrstijo po re-ranker score

### Dependency
```txt
sentence-transformers>=2.2.0
```

---

## 3. Enhanced Global Confidence Gating

### Opis
Multi-signal confidence scoring sistem, ki preprečuje low-quality odgovore in prilagaja strategijo glede na zaupanje.

### Confidence Signals

#### 1. Search Score
- Hybrid BM25 + vector score (0-1)

#### 2. Score Gap Ratio
- Razlika med top 2 rezultatoma
- Višji gap = višja zaupanje v top rezultat

#### 3. BM25/Vector Agreement
- Ali se obe metodi ujemata
- Višje = obe metodi se strinjata

#### 4. Overall Confidence
```
confidence = 0.5 * top_score + 0.3 * score_gap_ratio + 0.2 * agreement
```

### Query Type Analysis

Sistem prepozna tip query-ja in prilagodi confidence threshold:

| Query Type | Required Confidence | Priority | Examples |
|-----------|---------------------|----------|----------|
| Booking | 0.70 | Critical | "naroči termin", "rezervacija" |
| Price | 0.65 | High | "koliko stane", "cena" |
| Contact | 0.50 | Medium | "naslov", "telefon", "lokacija" |
| Info | 0.55 | Medium | "dermatolog", "storitve" |
| General | 0.45 | Low | Ostali query-ji |

### Response Strategies

#### Strategy 1: Very High Confidence (≥0.75 + gap >0.3)
- **Action**: Return top result directly
- **Reason**: Clear winner, strong confidence

#### Strategy 2: Meets Query-Type Threshold
- **Action**: Return top result (with extra validation for critical queries)
- **Reason**: Confidence meets query-specific requirement

#### Strategy 3: Medium Confidence (≥0.35)
- **Action**: Use LLM to synthesize answer from top 2-3 retrieved docs
- **Reason**: Moderate confidence, LLM can combine context
- **Validation**: Check LLM response quality (length, decline phrases)

#### Strategy 4: Low Confidence (<0.35)
- **Action**: Ask for clarification
- **Reason**: Too uncertain, better to ask user
- **Contextual**: Different clarification based on query type

### Confidence Metadata Storage

Vsak assistant odgovor shranjuje confidence metadata v PostgreSQL:

```json
{
  "query_type": "price",
  "query_priority": "high",
  "required_confidence": 0.65,
  "overall_confidence": 0.72,
  "top_score": 0.85,
  "score_gap_ratio": 0.45,
  "bm25_vector_agreement": 0.82,
  "reranker_used": true,
  "num_results": 3
}
```

To omogoča:
- Analytics v admin panelu
- Debugging confidence gating
- Monitoring performance

---

## Testiranje

### 1. Zagon aplikacije
```bash
cd "/Volumes/SSD KLJUC/KOVACNIK AI/ZDRAVSTVENI CENTER"
python main.py
```

### 2. Test queries

**High confidence** (mora vrniti direkten odgovor):
- "Koliko stane dermatološki pregled?"
- "Kakšen je vaš naslov?"
- "Delovni čas?"

**Medium confidence** (mora uporabiti LLM):
- "Kakšne storitve imate?"
- "Ali imate parkirišče?"

**Low confidence** (mora vprašati za clarification):
- "Koliko?"
- "Kje?"
- "Kdaj?"

### 3. Preverjanje logov

Iščite v terminalu:
```
[KB] Initializing hybrid knowledge base...
[KB] BM25 indexing complete
[KB] Vector indexing complete
[RERANKER] Loading cross-encoder model...
[KB] Re-ranker enabled
[KB] Hybrid knowledge base ready!
```

Med query-jem:
```
[CONFIDENCE] Query type: price (priority: high)
[CONFIDENCE] Required confidence threshold: 0.65
[KB_SEARCH] Top result: cene (score: 0.850)
[CONFIDENCE] Overall confidence: 0.782
[CONFIDENCE] ✓ Meets query-type threshold - returning directly
```

### 4. Preverjanje confidence metadata

V admin panelu (`/admin` → "Orodja & Analitika" → "Zgodovina pogovorov"):
- Odpirite individualne chat session
- Preverjajte ali se shranjuje confidence metadata

---

## Performance Optimizations

1. **Lazy Initialization**: KB se inicializira šele ob prvem query-ju (ne ob zagonu)
2. **In-Memory Caching**: Embeddings se shranjujejo v RAM (INFO_RESPONSES je majhen)
3. **Re-ranker na kandidatih**: Re-ranking samo top_k * 3 rezultatov (ne vseh)
4. **Graceful Fallback**: Če re-ranker ne deluje, nadaljuje brez njega

---

## Dependencies

Dodane v `requirements.txt`:
```txt
openai>=1.0.0  # Already existed
sentence-transformers>=2.2.0  # New
```

Potrebno:
```bash
pip install -r requirements.txt
```

---

## Konfiguracijske možnosti

### Alpha (BM25 vs Vector weight)
```python
# V chat_router.py:457
kb_module.initialize_knowledge_base(
    documents=INFO_RESPONSES,
    alpha=0.5,  # 0=samo BM25, 1=samo vector, 0.5=enako
    use_reranker=True
)
```

### Re-ranker model
```python
# V knowledge_base.py:213
CrossEncoderReranker(model_name="cross-encoder/mmarco-mMiniLMv2-L12-H384-v1")
```

### Confidence thresholds
```python
# V chat_router.py:836-854 (_analyze_query_type)
return {"type": "booking", "required_confidence": 0.7, "priority": "critical"}
```

---

## Primerjava s KOVACNIK AI / KMETIJA POD GORO

| Feature | ZDRAVSTVENI CENTER | KOVACNIK AI | KMETIJA POD GORO |
|---------|-------------------|-------------|------------------|
| Hybrid Retrieval | ✅ | ✅ | ✅ |
| Re-ranker | ✅ | ✅ | ✅ |
| Global Confidence Gating | ✅ | ✅ | ✅ |
| Soft-switch (info ↔ booking) | ✅ | ✅ | ✅ |
| Cache | ✅ | ✅ | ✅ |
| Email/IMAP prefix filter | ✅ | ✅ | ✅ |

**Status**: ZDRAVSTVENI CENTER je sedaj na isti ravni kot KOVACNIK AI! 🎉

---

## Known Issues & Future Improvements

### Current Limitations
1. First query je počasnejši zaradi:
   - KB initialization
   - OpenAI embeddings API calls (15x)
   - Re-ranker model loading (~300MB)

2. OpenAI API calls pri vsakem query-ju za embedding (ne za odgovor)

### Potential Improvements
1. **Persistent embeddings**: Shrani embeddings v disk, ne računaj ponovno
2. **Batch embedding**: Embed vse INFO_RESPONSES ob deployment-u
3. **Local embeddings**: Uporabi sentence-transformers namesto OpenAI za embeddings
4. **Confidence monitoring dashboard**: Admin panel graf za confidence scores
5. **A/B testing**: Test različnih alpha vrednosti

---

## Environment Variables

Potrebno v `.env`:
```bash
OPENAI_API_KEY=sk-...  # Za embeddings in LLM
DATABASE_URL=postgresql://...  # Za chat history s confidence metadata
```

---

## Maintenance

### Dodajanje novih dokumentov
1. Dodaj v `INFO_RESPONSES` dict v `chat_router.py:218`
2. Sistem se bo avtomatsko reindeksiral ob naslednjem restartu

### Spreminjanje confidence thresholds
- Prilagodi v `_analyze_query_type()` funkciji
- Testiraj z različnimi query tipi
- Spremljaj confidence metadata v admin panelu

### Monitoring
- Preverjaj console loge za `[CONFIDENCE]` in `[KB_SEARCH]`
- Analiziraj confidence metadata v chat history
- Identificiraj low-confidence queries za izboljšave

---

## Zaključek

Implementacija je **production-ready** in zagotavlja:
- ✅ Boljšo natančnost iskanja (hybrid + re-ranking)
- ✅ Preprečevanje hallucinations (confidence gating)
- ✅ Sledljivost (confidence metadata)
- ✅ Prilagodljivost (query-type aware thresholds)
- ✅ Robustnost (graceful fallbacks)

System je sedaj na nivoju KOVACNIK AI in KMETIJA POD GORO! 🚀
