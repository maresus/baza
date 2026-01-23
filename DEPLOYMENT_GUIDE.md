# 🏥 Zdravstveni Center AI - Navodila za Deployment

Ta sistem je **TEMPLATE** za katerikoli zdravstveni center. Pred deploymentom moraš prilagoditi podatke za konkretnega kupca.

## 📋 Checklist za Customizacijo

### 1. **Osnovni podatki** (OBVEZNO)

Spremeni v datoteki `knowledge.jsonl`:
- ❌ "[Naslov zdravstvenega centra]" → ✅ Pravi naslov
- ❌ "[Telefonska številka]" → ✅ Prava telefonska
- ❌ "[Email naslov]" → ✅ Pravi email

### 2. **Imena zdravnikov** (PRIPOROČENO)

V `knowledge.jsonl` dodaj resnična imena:
```json
{"text": "Naš dermatolog: Dr. [Ime Priimek], specialist dermatologije", ...}
```

### 3. **Cene storitev** (PRIPOROČENO)

V `app/services/health_center_extensions.py` - SERVICES dict:
```python
SERVICES = {
    "dermatolog": {
        "name": "Dermatološki pregled",
        "duration_minutes": 30,
        "price_range": "25-150 €",  # ← Spremeni cene
        ...
    },
    ...
}
```

### 4. **Delovni čas** (ČE JE DRUGAČEN)

V `app/services/health_center_extensions.py`:
```python
WORKING_HOURS = {
    "start": 8,  # ← Spremeni začetek
    "end": 18,   # ← Spremeni konec
}

WORKING_DAYS = {0, 1, 2, 3, 4}  # Pon-Pet (0=Pon, 6=Ned)
```

### 5. **Kontaktni podatki v email template**

V `app/services/email_service.py` (ko ga boš prilagajal):
- Spremeni telefonsko številko
- Spremeni email
- Spremeni naslov
- Dodaj logo zdravstvenega centra

### 6. **Frontend branding**

V `static/chat.html` in `static/admin.html`:
- Logo zdravstvenega centra
- Barve (CSS)
- Naziv centra

### 7. **Environment spremenljivke** (.env)

Ustvari `.env` datoteko:
```bash
OPENAI_API_KEY=sk-...
DATABASE_URL=postgresql://...  # Za production
ADMIN_TOKEN=tvoj_secret_token
RESEND_API_KEY=re_...
```

## 🚀 Deployment Postopek

### Korak 1: Customizacija
1. Kloniraj ta projekt
2. Spremeni vse podatke po checklisti zgoraj
3. Testiraj backend: `python test_betnava_appointments.py`
4. Testiraj chat: Zaženi `uvicorn main:app --reload` in testiraj na http://localhost:8000

### Korak 2: Deploy na Railway
```bash
# Git init (če še ni)
git init
git add .
git commit -m "Initial deployment for [Ime centra]"

# Railway CLI
railway login
railway init
railway up
```

### Korak 3: Nastavi DNS
- Dodaj custom domain v Railway
- Poveži zdravstvenemu centru na njihov subdomen (npr. chat.zdravstveni-center.si)

### Korak 4: Email setup
- Ustvari Resend account
- Dodaj domain verification
- Testiraj email potrdila

## 📦 Paketi storitev

Sistem podpira 6 tipov storitev:
1. **DERMATOLOG** - Dermatološki pregled (30 min)
2. **ORTOPED** - Ortopedski pregled (30 min)
3. **OKULIST** - Okulistični pregled (30 min)
4. **LASERSKI_POSEG** - Laserski poseg (30 min)
5. **ESTETSKI_POSEG** - Estetski poseg (30 min)
6. **KOZMETIKA** - Kozmetični salon (60 min)

**Kako dodati novo storitev:**
1. Dodaj v `SERVICES` dict v `health_center_extensions.py`
2. Dodaj v `SERVICE_NAME_MAP` za AI rozpoznavanje
3. Dodaj v knowledge.jsonl opis storitve

## 🎨 Branding Placeholders

**Spremeni pred deploymentom:**
- `[Naslov zdravstvenega centra]`
- `[Telefonska številka]`
- `[Email naslov]`
- `[Mesto]`
- `Zdravstveni center` → `[Ime centra]`

## ✅ Funkcionalnosti

- ✅ Backend API (ReservationService, health_center_extensions.py)
- ✅ Chat conversation flow za naročanje terminov (chat_router.py - 712 vrstic, čist kod)
- ✅ Validacija terminov (30-min sloti, delovni čas, delovni dnevi)
- ✅ 6 tipov storitev (dermatolog, ortoped, okulist, laserski poseg, estetski poseg, kozmetika)
- ✅ Knowledge base (61 vnosov, generičen template)
- ✅ Email potrdila (async)
- ⏳ Frontend (chat.html, admin.html - še potrebna prilagoditev)

## ⚠️ POMEMBNO

- **NE deploy-aj** brez spremembe kontaktnih podatkov!
- **TESTIRAJ** vse funkcionalnosti lokalno
- **BACKUP** database pred production deploymentom
- **SPREMENI** admin token pred deploymentom

## 🔧 Primer Customizacije

**Za BETNAVA Maribor:**
```python
# health_center_extensions.py
CONTACT_PHONE = "02 333 99 00"
CONTACT_EMAIL = "info@mc-betnava.si"
CENTER_NAME = "BETNAVA"
CENTER_ADDRESS = "Maribor, Slovenija"

# knowledge.jsonl
{"text": "BETNAVA je zdravstveni center v Mariboru...", ...}
```

## 📞 Support

Za vprašanja glede customizacije kontaktiraj razvijalca.
