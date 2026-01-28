# ZDRAVSTVENI CENTER - SISTEMATIČNI NAČRT IMPLEMENTACIJE

## STATUS IMPLEMENTACIJE

| # | Feature | Status | Datum | Opombe |
|---|---------|--------|-------|--------|
| 0 | Kritični Bug Fixi | ✅ KONČANO | 2026-01-27 | conversation_state, detect_service_from_message, real slots |
| 1 | Smart Reminders & Follow-up | ✅ KONČANO | 2026-01-28 | Multi-stage SMS/Email, quick actions, no-show tracking |
| 2 | Conversational Analytics Dashboard | ✅ KONČANO | 2026-01-28 | trending, bottlenecks, sentiment |
| 3 | Intelligent Scheduling Engine | ✅ KONČANO | 2026-01-28 | user prefs, clinic optimization |
| 4 | Seamless Handoff z Kontekstom | ✅ KONČANO | 2026-01-28 | summary generator, priority queue |
| 5 | Proaktivni Health Assistant | ✅ KONČANO | 2026-01-28 | pattern detection, preventive reminders |
| 6 | Semantic Knowledge Graph | ✅ KONČANO | 2026-01-28 | medical concepts, connections |
| 7 | Multimodalni Input (Voice) | ✅ KONČANO | 2026-01-28 | Whisper transcription |
| 8 | Smart Triage z Symptom Checker | ✅ KONČANO | 2026-01-28 | soft triage, specialist routing |

---

## FAZA 0: KRITIČNI BUG FIXI

### 0.1 conversation_state undefined ✅
**Problem**: Variable `conversation_state` se uporablja ampak ni definirana
**Lokacija**: chat_router.py line 527
**Fix**: Dodal `conversation_state: dict[str, dict[str, Any]] = {}`
**Status**: ✅ KONČANO (2026-01-27)

### 0.2 detect_service_from_message undefined ✅
**Problem**: Funkcija ne obstaja, pravilna je `extract_service_type`
**Lokacija**: chat_router.py line 1482
**Fix**: Zamenjal z `extract_service_type(message)`
**Status**: ✅ KONČANO (2026-01-27)

### 0.3 Mock Time Slots ✅
**Problem**: get_available_time_slots vrača vse slote, ne preverja database
**Lokacija**: health_center_extensions.py
**Fix**: Dodal `_get_booked_slots()` ki query-ja database, integriral v `get_available_time_slots()`
**Status**: ✅ KONČANO (2026-01-27)

---

## FAZA 1: SMART REMINDERS & FOLLOW-UP ✅

### Opis
Sistem za pametne opomnike pred in po obisku.

### Implementirane Komponente

#### 1. **Pre-visit reminders** ✅
- **3 dni prej**: Email + SMS z navodili (kaj prinesti, kje parkirati)
- **2 uri prej**: SMS z quick actions (DA/PRESTAVI/ODPOVEJ)

#### 2. **Post-visit follow-up** ✅
- **1 dan po**: Follow-up SMS "Kako ste? Imate vprašanja?"

#### 3. **No-show tracking** ✅
- `detect_no_shows()` - avtomatska detekcija
- `mark_appointment_no_show()` - označevanje
- `get_reminder_stats()` - no-show rate statistika

#### 4. **SMS Quick Actions** ✅
- Webhook endpoint `/chat/sms-webhook` za Twilio
- `handle_sms_response()` - procesiranje DA/PRESTAVI/ODPOVEJ
- Avtomatski odgovori pacientom

### Tehnična Implementacija

**ReminderStage Enum:**
```python
NONE = 0           # Noben opomnik še poslan
SENT_3_DAY = 1     # Poslan 3 dni prej
SENT_2_HOUR = 2    # Poslan 2 uri prej
COMPLETED = 3      # Termin opravljen
NO_SHOW = 4        # Pacient ni prišel
FOLLOWUP_SENT = 5  # Follow-up poslan po obisku
```

**Database stolpci (avtomatski migration):**
- `reminder_stage` - trenutna stopnja opomnika
- `last_reminder_at` - timestamp zadnjega opomnika
- `patient_confirmed` - ali je pacient potrdil prihod

**Ključne funkcije:**
- `send_3_day_reminders()` - pošlje 3-dnevne opomnike
- `send_2_hour_reminders()` - pošlje 2-urne opomnike
- `send_post_visit_followups()` - pošlje follow-upe
- `check_and_send_reminders()` - glavna funkcija (vse stopnje)
- `handle_sms_response()` - procesira SMS odgovore

### Datoteke
- `app/services/reminder_scheduler.py` ✅ (razširjena)
- `app/services/sms_service.py` ✅ (nova - Twilio integracija)
- `app/services/chat_router.py` ✅ (dodan SMS webhook)

### Konfiguracija (.env)
```
REMINDER_CHECK_INTERVAL_MINUTES=30
ENABLE_SMS_REMINDERS=true
ENABLE_EMAIL_REMINDERS=true
SMS_MOCK_MODE=true  # za testiranje
TWILIO_ACCOUNT_SID=xxx
TWILIO_AUTH_TOKEN=xxx
TWILIO_PHONE_NUMBER=+1234567890
```

### Testiranje
```bash
python -c "import asyncio; from app.services.reminder_scheduler import test_reminder_scheduler; asyncio.run(test_reminder_scheduler())"
```

### Status: ✅ KONČANO (2026-01-28)

---

## FAZA 2: CONVERSATIONAL ANALYTICS DASHBOARD ✅

### Opis
Real-time insights za admina o pogovorih.

### Implementirane Komponente

#### 1. **Trending symptoms/topics** ✅
- `get_trending_topics()` - analiza najpogostejših tem
- Keyword detection za medicinske teme (koža, oči, sklepi, estetika, laser)
- Top 10 topics + top 20 keywords

#### 2. **Bottleneck analysis** ✅
- `get_booking_funnel()` - conversion funnel
- Tracking 6 stopenj: inquiry → date → time → info → confirm → complete
- Drop rate izračun za vsako stopnjo

#### 3. **Sentiment tracking** ✅
- `get_sentiment_stats()` - analiza tona
- Slovenščina: pozitivne/negativne ključne besede
- Daily trend tracking
- Flagged conversations (negativni pogovori)

#### 4. **Peak hours** ✅
- `get_peak_hours()` - analiza aktivnosti
- Hourly distribution (24h)
- Daily distribution (Pon-Ned)
- Smart recommendations

### API Endpoints

```
GET /api/admin/analytics/dashboard?days=7    # Vse statistike
GET /api/admin/analytics/trending?days=7     # Trending topics
GET /api/admin/analytics/funnel?days=30      # Booking funnel
GET /api/admin/analytics/sentiment?days=7    # Sentiment analiza
GET /api/admin/analytics/peak-hours?days=30  # Peak hours
GET /api/admin/analytics/reservations?days=30 # Statistika rezervacij
GET /api/admin/analytics/reminder-stats      # Reminder sistem statistika
```

### Datoteke
- `app/services/analytics_service.py` ✅ (nova - 450+ vrstic)
- `app/services/admin_router.py` ✅ (razširjena z analytics endpoints)

### Status: ✅ KONČANO (2026-01-28)

---

## FAZA 3: INTELLIGENT SCHEDULING ENGINE ✅

### Opis
Pametno predlaganje terminov glede na user preference in clinic optimization.

### Implementirane Komponente

#### 1. **User preference learning** ✅
- `get_user_preferences()` - analiza preteklih rezervacij
- Tracking: preferred hour, preferred day, preferred service
- No-show rate per user
- Recent services history

#### 2. **Clinic optimization** ✅
- `get_slot_occupancy()` - zasedenost po dnevih
- `get_weekly_load()` - tedenski pregled load-a
- Hourly breakdown (booked/available)
- Busiest/quietest hour detection

#### 3. **Smart suggestions** ✅
- `get_smart_suggestions()` - ML-like scoring sistem
- Scoring factors:
  - User preference match (+20 za hour, +15 za day)
  - Prime time bonus (+5 za 10:00-14:00)
  - Soon availability (+10 za danes)
  - Early/late penalty (-5 za <9 ali >17)
- `format_suggestion_message()` - personalizirano sporočilo

### API Endpoints

```
GET /api/admin/scheduler/suggestions?service_type=dermatolog&phone=040123456
GET /api/admin/scheduler/user-preferences/{phone}
GET /api/admin/scheduler/occupancy/{date}
GET /api/admin/scheduler/weekly-load?start_date=01.02.2026
```

### Primer uporabe
```python
scheduler = SmartScheduler()
suggestions = scheduler.get_smart_suggestions(
    service_type="dermatolog",
    phone="+38640123456",
    preferred_date="15.02.2026"
)
# Returns: ["Torek, 15.02.2026 ob 10:00 (vaš običajen čas)", ...]
```

### Datoteke
- `app/services/smart_scheduler.py` ✅ (nova - 400+ vrstic)
- `app/services/admin_router.py` ✅ (razširjena z scheduler endpoints)

### Status: ✅ KONČANO (2026-01-28)

---

## FAZA 4: SEAMLESS HANDOFF Z KONTEKSTOM ✅

### Opis
Inteligenten prenos pogovora na recepcijo z vsem kontekstom.

### Implementirane Komponente

#### 1. **Summary generator** ✅
- `generate_summary()` - rule-based povzetek
- `generate_llm_summary()` - LLM povzetek (OpenAI)
- Izvleče: ime, telefon, email, storitev, datum

#### 2. **Sentiment analysis** ✅
- `analyze_sentiment()` - analiza frustracije in urgentnosti
- Frustration keywords (slovenščina)
- Urgency keywords (medicinske nujnosti)
- Frustration level (0-10) + Urgency level (0-10)

#### 3. **Suggested responses** ✅
- `get_suggested_responses()` - predlogi odgovorov
- Template kategorije: booking_issue, general_inquiry, frustrated_patient, urgent_medical
- Personalizirani predlogi glede na sentiment

#### 4. **Priority queue** ✅
- `HandoffPriority` enum: LOW, MEDIUM, HIGH, URGENT
- `calculate_priority()` - avtomatski izračun
- `get_pending_handoffs()` - sortirana vrsta
- `resolve_handoff()` - označevanje rešenih

### API Endpoints

```
POST /api/admin/handoff/create/{session_id}?use_llm=true
GET  /api/admin/handoff/pending
GET  /api/admin/handoff/{session_id}
POST /api/admin/handoff/resolve/{session_id}
GET  /api/admin/handoff/stats
```

### Handoff paket vsebuje:
```json
{
    "session_id": "abc123",
    "priority": "HIGH",
    "summary": "Pacient išče dermatološki pregled...",
    "sentiment": {
        "overall": "frustrated",
        "frustration_level": 7,
        "urgency_level": 2
    },
    "key_info": {
        "phone": "+38640123456",
        "service_requested": "dermatolog"
    },
    "suggested_responses": ["Opravičujem se..."],
    "conversation_preview": [...]
}
```

### Datoteke
- `app/services/handoff_service.py` ✅ (nova - 450+ vrstic)
- `app/services/admin_router.py` ✅ (razširjena z handoff endpoints)

### Status: ✅ KONČANO (2026-01-28)

---

## FAZA 5: PROAKTIVNI HEALTH ASSISTANT ✅

### Opis
Bot predvideva potrebe in proaktivno kontaktira paciente.

### Implementirane Komponente

#### 1. **Seasonal pattern detection** ✅
- `detect_seasonal_needs()` - analiza sezonskih vzorcev
- SEASONAL_PATTERNS config za vsak mesec
- Sporočilo: "Vsako leto v tem času uporabljate storitev X..."

#### 2. **Preventive reminders** ✅
- `check_annual_checkups()` - letni pregledi
- ANNUAL_CHECKUP_INTERVALS: okulist (365 dni), dermatolog (365 dni)
- Avtomatsko opozorilo ko poteče interval

#### 3. **Follow-up care** ✅
- `check_followup_needs()` - kontrolni pregledi
- FOLLOWUP_REQUIRED: laser (14 dni), estetika (14 dni), ortoped (30 dni)
- Opozorilo v 7-dnevnem oknu

#### 4. **Health campaigns** ✅
- `get_active_campaigns()` - aktivne kampanje
- HEALTH_CAMPAIGNS per mesec
- Personalizacija glede na pacientovo zgodovino

### AlertType Enum
```python
SEASONAL_PATTERN    # Sezonski vzorec
ANNUAL_CHECKUP      # Letni pregled
FOLLOWUP_NEEDED     # Kontrolni pregled
HEALTH_CAMPAIGN     # Preventivna akcija
```

### API Endpoints

```
GET /api/admin/proactive/alerts/{phone}
GET /api/admin/proactive/campaigns
GET /api/admin/proactive/patient-patterns/{phone}
```

### Datoteke
- `app/services/proactive_assistant.py` ✅ (nova - 400+ vrstic)
- `app/services/admin_router.py` ✅ (razširjena z proactive endpoints)

### Status: ✅ KONČANO (2026-01-28)

---

## FAZA 6: SEMANTIC KNOWLEDGE GRAPH ✅

### Opis
Povezan graf medicinskih konceptov namesto flat KB.

### Implementirane Komponente

#### 1. **Medical concept graph** ✅
- `GraphNode` dataclass - vozlišča (simptom, specialist, storitev, priprava)
- `GraphEdge` dataclass - povezave z utežmi
- NodeType: SYMPTOM, SPECIALIST, SERVICE, PREPARATION, CONDITION, BODY_PART
- 20+ simptomov, 6 specialistov, 6 storitev, 6 priprav

#### 2. **Symptom → Specialist mapping** ✅
- Weighted edges (0.0-1.0)
- Npr: bolečina_kolena → ortoped (0.95), fizioterapevt (0.6)
- Multi-specialist support

#### 3. **Urgency indicators** ✅
- UrgencyLevel enum: ROUTINE, SOON, PRIORITY, URGENT, EMERGENCY
- Avtomatska detekcija urgentnih simptomov
- "Pokličite 112" za emergency

#### 4. **Contextual answers** ✅
- `query_symptoms()` - celotna analiza iz besedila
- `_build_contextual_response()` - personalizirano sporočilo
- Vključuje: simptome, specialista, urgentnost, priprave

### API Endpoints

```
POST /api/admin/knowledge-graph/query-symptoms?text=boli%20koleno
GET  /api/admin/knowledge-graph/preparations/{service_id}
GET  /api/admin/knowledge-graph/related/{node_id}
GET  /api/admin/knowledge-graph/stats
```

### Primer uporabe
```python
kg = KnowledgeGraph()
result = kg.query_symptoms("Boli me koleno in je otečeno")
# Returns:
# - detected_symptoms: ["Bolečina v kolenu", "Otekanje sklepa"]
# - recommended_specialists: [{"name": "Ortoped", "relevance_score": 1.9}]
# - urgency: {"level": "ROUTINE", "message": "..."}
# - preparations: ["Zdravstvena kartica", "Udobna oblačila"]
```

### Datoteke
- `app/services/knowledge_graph.py` ✅ (nova - 500+ vrstic)
- `app/services/admin_router.py` ✅ (razširjena z knowledge-graph endpoints)

### Status: ✅ KONČANO (2026-01-28)

---

## FAZA 7: MULTIMODALNI INPUT (VOICE) ✅

### Opis
Podpora za glasovna sporočila (Whisper transkripcija).

### Implementirane Komponente

#### 1. **Voice transcription** ✅
- `transcribe_audio()` - OpenAI Whisper API
- `transcribe_from_path()` - transkripcija iz datoteke
- `transcribe_from_bytes()` - transkripcija iz bajtov
- Slovenščina kot default jezik

#### 2. **Audio file handling** ✅
- `validate_audio_file()` - validacija formata in velikosti
- Podprti formati: mp3, mp4, mpeg, mpga, m4a, wav, webm, ogg
- Maksimalna velikost: 25 MB

#### 3. **Chat integration** ✅
- `/chat/voice` endpoint
- Transkribira audio → procesira kot chat sporočilo
- Vrne transkripcijo + odgovor chatbota

#### 4. **Text-to-Speech** ✅ (priprava za prihodnost)
- `text_to_speech()` - OpenAI TTS API
- Podpora za različne glasove (alloy, echo, fable, onyx, nova, shimmer)

### API Endpoints

```
POST /chat/voice
Content-Type: multipart/form-data
Body: file (audio), session_id (optional)

Response:
{
    "success": true,
    "transcription": "Želim rezervirati termin...",
    "reply": "Seveda, kateri specialist vas zanima?",
    "session_id": "abc123",
    "duration_seconds": 5.2
}
```

### Konfiguracija (.env)
```
OPENAI_API_KEY=sk-xxx  # Potreben za Whisper
```

### Datoteke
- `app/services/voice_service.py` ✅ (nova - 250+ vrstic)
- `app/services/chat_router.py` ✅ (dodan /voice endpoint)

### Status: ✅ KONČANO (2026-01-28)

---

## FAZA 8: SMART TRIAGE Z SYMPTOM CHECKER ✅

### Opis
Soft triage - usmerjanje k pravemu specialistu (NE diagnoza!).

### Implementirane Komponente

#### 1. **Symptom collection** ✅
- `TriageSession` dataclass - upravljanje seje
- Multi-step proces: INITIAL → DURATION → INTENSITY → HISTORY → COMPLETED
- Structured questions s predefiniranimi options

#### 2. **Specialist routing** ✅
- `analyze_symptoms()` - regex matching za simptome
- SYMPTOM_SPECIALIST_MAP z weighted confidence
- Podpora za: dermatolog, ortoped, okulist, urgenca

#### 3. **Urgency indicators (SOFT!)** ✅
- `SymptomIntensity` enum: MILD, MODERATE, SEVERE, EMERGENCY
- `MEDICAL_DISCLAIMER` - vedno vključen
- NIKOLI ne reče "ni urgentno"
- VEDNO: "Posvetujte se z zdravnikom"

#### 4. **Quick triage** ✅
- `quick_triage()` - single-step analiza brez interakcije
- Takojšnje priporočilo za preprostejše primere

### API Endpoints

```
POST /api/admin/triage/quick?symptoms=boli%20me%20koleno
POST /api/admin/triage/start/{session_id}
POST /api/admin/triage/respond/{session_id}  # body: {"response": "..."}
GET  /api/admin/triage/session/{session_id}
```

### Primer triage flow
```
1. START: "Kaj vas muči?"
2. USER: "Boli me koleno in je otečeno"
3. BOT: Analiza → "Za težave s sklepi priporočam ortopedski pregled."
4. BOT: "Kako dolgo že imate te težave?"
5. USER: "Teden dni"
6. BOT: "Kako močne so vaše težave (1-10)?"
7. USER: "7"
8. BOT: Final recommendation + DISCLAIMER + "Želite rezervirati termin?"
```

### Varnostna opozorila
- MEDICAL_DISCLAIMER je VEDNO vključen v odgovor
- Urgentni simptomi (kri, dihanje, prsih) → takojšnja napotitev na 112
- NI diagnoza, samo usmerjanje

### Datoteke
- `app/services/triage_service.py` ✅ (nova - 400+ vrstic)
- `app/services/admin_router.py` ✅ (razširjena z triage endpoints)

### Status: ✅ KONČANO (2026-01-28)

---

## OPOMBE IN LOG

### 2026-01-27
- Ustvarjen načrt implementacije
- Identificirani kritični bugi
- Prioritetna lista določena

---

## ZAKLJUČEK

### ✅ VSE FAZE KONČANE! (2026-01-28)

Implementirano:
- **3 kritični bugi** popravljeni
- **8 naprednih funkcionalnosti** implementiranih
- **~3000+ vrstic nove kode**
- **20+ novih API endpoints**

### Nova arhitektura

```
app/services/
├── reminder_scheduler.py    # FAZA 1 - Multi-stage reminders
├── sms_service.py           # FAZA 1 - Twilio SMS
├── analytics_service.py     # FAZA 2 - Dashboard analytics
├── smart_scheduler.py       # FAZA 3 - Intelligent scheduling
├── handoff_service.py       # FAZA 4 - Seamless handoff
├── proactive_assistant.py   # FAZA 5 - Proactive health
├── knowledge_graph.py       # FAZA 6 - Semantic graph
├── voice_service.py         # FAZA 7 - Voice/Whisper
└── triage_service.py        # FAZA 8 - Symptom triage
```

### Naslednji koraki (opcijsko)

1. ⬜ Frontend integracija - admin dashboard UI
2. ⬜ Production deployment - Twilio credentials
3. ⬜ Testing - unit testi za nove module
4. ⬜ Monitoring - logging in alerting
5. ⬜ Documentation - API docs, user guide
