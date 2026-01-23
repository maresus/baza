# Email Reminder System - Zdravstveni Center

## 📧 Pregled sistema

Avtomatski email sistem za zdravstveni center z naslednjimi funkcionalnostmi:

### 1. Email Templates
- **Potrditev termina** (`send_reservation_confirmed`) - pošlje ob potrditvi + iCal priponka
- **Zavrnitev termina** (`send_reservation_rejected`) - pošlje ob zavrnitvi
- **24h opomnik** (`send_appointment_reminder`) - avtomatski opomnik dan pred terminom

### 2. iCalendar Integration
- Generira `.ics` datoteko (RFC 5545 compliant)
- Deluje z Google Calendar, Outlook, Apple Calendar
- 30-minutno trajanje termina
- Vključen VALARM reminder 24h pred terminom

### 3. Automated Reminder Scheduler
- Background servis, ki teče vzporedno s FastAPI
- Preverja termine vsako uro (konfigurirano: `REMINDER_CHECK_INTERVAL_MINUTES`)
- Išče termine, ki so 24-26 ur stran
- Pošlje reminder email in označi `reminder_sent = 1`

## 🚀 Aktivacija

### Environment Variables (.env)

```bash
# SMTP nastavitve
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=info@zdravstveni-center.si
SMTP_PASSWORD=your_app_password
SMTP_FROM_EMAIL=info@zdravstveni-center.si
SMTP_FROM_NAME=Zdravstveni center
ADMIN_EMAIL=info@zdravstveni-center.si

# Opcijsko - Reminder scheduler
REMINDER_CHECK_INTERVAL_MINUTES=60  # Default: 60 min
REMINDER_HOURS_BEFORE=24  # Default: 24h
```

### Railway Deployment

V Railway dodaj environment variables:
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASSWORD`
- `SMTP_FROM_EMAIL`
- `SMTP_FROM_NAME`
- `ADMIN_EMAIL`

Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`

## 📂 Datoteke

### Nove datoteke:
- `app/services/reminder_scheduler.py` - Automated reminder scheduler
- `EMAIL_SYSTEM.md` - Ta dokumentacija

### Spremenjene datoteke:
- `app/services/email_service.py` - Dodani reminder templates + iCal
- `main.py` - Scheduler integration + static files mounting

## 🧪 Testiranje

### Lokalno testiranje:

```bash
cd "ZDRAVSTVENI CENTER"
source venv/bin/activate

# Test reminder scheduler
python -m app.services.reminder_scheduler

# Test email templates (generira HTML files)
python -m app.services.email_service
```

### Admin Panel:

```
http://localhost:8000/static/admin_new.html
```

Ustvari testni termin:
1. Klikni "+" ali izberi časovni slot
2. Nastavi datum na **jutri**
3. Izberi čas
4. Dodaj email naslov
5. Status: **confirmed**
6. Shrani

Scheduler bo avtomatsko poslal reminder email čez ~1 uro (ko bo termin 24h stran).

## 🔧 Kako deluje

### Flow:

1. **Pacient naroči termin** → chatbot ustvari termin s status `pending`
2. **Admin odpre admin panel** → vidi pending termine
3. **Admin klikne "✅ Potrdi"** →
   - Status → `confirmed`
   - Pošlje potrditveni email z iCal priponko
4. **24h pred terminom** →
   - Scheduler najde termin
   - Pošlje reminder email
   - Označi `reminder_sent = 1`

### Database:

Scheduler doda stolpec `reminder_sent` v `reservations` tabelo:
```sql
ALTER TABLE reservations ADD COLUMN reminder_sent INTEGER DEFAULT 0
```

To se zgodi avtomatsko ob prvem zagonu.

### Scheduler Logic:

```python
# Preverja vsako uro
while True:
    appointments = get_appointments_needing_reminder()  # WHERE status='confirmed' AND reminder_sent=0
    for apt in appointments:
        if 24h <= time_until_appointment <= 26h:  # 2h buffer
            send_appointment_reminder(apt)
            mark_reminder_sent(apt.id)
    await asyncio.sleep(60 * 60)  # Wait 1 hour
```

## 📊 Monitoring

### Logs:

Scheduler logira vse aktivnosti:
```
🔔 Checking for appointments needing reminders...
Found 2 appointment(s) needing reminder
Sending reminder for appointment #123 - Janez Novak on 24.01.2026 at 14:30
✅ Reminder sent successfully for appointment #123
✅ Reminder check completed. Sent 2 reminder(s)
```

### Preverba stanja:

```bash
# Preveri če scheduler teče
curl http://localhost:8000/health

# Preveri logs v Railway
railway logs
```

## 🐛 Troubleshooting

### Emaili se ne pošiljajo:
- Preveri SMTP credentials v `.env` ali Railway
- Preveri `[EMAIL]` log messages v console
- Test: `python -m app.services.email_service`

### Scheduler ne pošilja reminderjev:
- Preveri ali scheduler teče: `ps aux | grep reminder`
- Preveri logs: `🔔 Checking for appointments...`
- Test: `python -m app.services.reminder_scheduler`
- Preveri database: `SELECT * FROM reservations WHERE reminder_sent = 0 AND status = 'confirmed'`

### iCal priponka ne deluje:
- iCal dela samo preko SMTP (ne preko Resend API)
- Preveri da je `SMTP_USER` nastavljen, ne `RESEND_API_KEY`

## 🔮 Prihodnje izboljšave

- [ ] SMS reminders (Twilio/Vonage)
- [ ] Email reminder 1h pred terminom
- [ ] Cancellation link v emailu
- [ ] Email tracking (open rate, click rate)
- [ ] Multi-language support (EN, DE, IT)
- [ ] Custom reminder timing per service type

## 📞 Support

Za vprašanja ali težave kontaktiraj:
- GitHub: https://github.com/maresus/zdravstveni_center
- Email: info@zdravstveni-center.si

---

**Last updated:** 2026-01-23
**Version:** 1.0.0
**Status:** ✅ Production Ready
