# Zdravstveni center AI – Digitalni zdravstveni asistent

Pametni chatbot za naročanje pregledov in informacije o zdravstvenih storitvah.

## 🏥 Storitve

- **Dermatologija**: Pregledi kože, laserski in estetski posegi
- **Ortopedija**: Pregledi sklepov, hrbtenice, športne poškodbe
- **Oftalmologija**: Očesni pregledi, predpis očal in leč
- **Laserski posegi**: Odstranjevanje žilic, bradavic, zdravljenje glivic
- **Estetski posegi**: Botox, fillerji, biorevitalizacija
- **Kozmetika**: Nega obraza, tretmaji kože

## 🚀 Quick Start

```bash
# Zaženi server
uvicorn main:app --reload --port 8000

# V drugem terminalu - smoke testi
./tests/smoke_test.sh
```

## 🔐 Environment spremenljivke

| Spremenljivka | Opis | Obvezno |
|---------------|------|---------|
| OPENAI_API_KEY | OpenAI API ključ | DA |
| DATABASE_URL | PostgreSQL connection string | DA (production) |
| ADMIN_TOKEN | Token za admin API | DA |
| RESEND_API_KEY | Resend API za email | DA |

## 📡 API Endpoints

### Chat
- POST /chat - Pošlji sporočilo chatbotu
- GET / - Chat UI (testiranje)
- GET /widget - Widget za WordPress embed

### Admin
- GET /api/admin/reservations - Seznam terminov
- PATCH /api/admin/reservations/{id} - Posodobi termin
- POST /api/admin/reservations/{id}/confirm - Potrdi
- POST /api/admin/reservations/{id}/reject - Zavrni

### Reservation Types
- **appointment** - Zdravstveni termin (30 ali 60 min)
  - service_type: DERMATOLOG, ORTOPED, OKULIST, LASERSKI_POSEG, ESTETSKI_POSEG, KOZMETIKA
  - duration_minutes: 30 ali 60
  - Termini na 30 min (8:00, 8:30, 9:00, ...)

## 🏥 Delovni Čas

- **Dnevi**: Ponedeljek - Petek
- **Ure**: 8:00 - 18:00
- **Termini**: Vsak 30 min

## 🚀 Deployment

Railway auto-deploy iz main branch.

## 📧 Email Potrdila

Sistem avtomatsko pošilja email potrdila za:
- ✅ Potrjene termine
- ❌ Zavrnjene termine
- 📝 Spremembe terminov

## 📞 Kontakt

**Zdravstveni center**
Lokacija: [Mesto]
Tel: [Telefonska številka]
Email: [Email naslov]
