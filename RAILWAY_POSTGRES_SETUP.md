# Railway PostgreSQL Setup

## Problem
SQLite baza se briše pri vsakem Railway deploymentu, ker Railway ne ohrani lokalnih datotek.

## Rešitev
Sistem že podpira PostgreSQL! Samo nastaviti morate Railway addon.

---

## Koraki

### 1. Odprite Railway Dashboard
https://railway.app/ → Vaš projekt (zdravstveni_center)

### 2. Dodajte PostgreSQL Database
1. Kliknite **"+ New"** → **"Database"** → **"Add PostgreSQL"**
2. Railway bo ustvaril PostgreSQL addon znotraj istega projekta
3. **Počakajte ~30 sekund** da se baza inicializira

### 3. Povežite Database z Aplikacijo
**POMEMBNO**: Railway **avtomatično** nastavi `DATABASE_URL` env var za vse servise v projektu.

Preverite:
1. V Railway dashboardu: Kliknite na vaš servis (FastAPI app)
2. Zavihek **"Variables"**
3. Preverite da obstaja `DATABASE_URL` → `${{Postgres.DATABASE_URL}}`
   - Če NE obstaja, dodajte:
     - **Key:** `DATABASE_URL`
     - **Value:** `${{Postgres.DATABASE_URL}}`

### 4. Re-deploy Aplikacijo
1. Railway bo avtomatično re-deployal
2. Ali ročno: **Settings** → **"Redeploy"**

### 5. Preverite Logs
V Railway dashboardu:
1. Kliknite na vaš servis
2. Zavihek **"Deployments"** → Latest deployment → **"View Logs"**
3. Iščite:
   ```
   [INFO] Using PostgreSQL database
   ```
   - Če vidite to: ✅ SUCCESS
   - Če vidite `[INFO] Using SQLite database`: ❌ DATABASE_URL ni nastavljen

---

## Automatična Migracija

Sistem avtomatično:
1. Zazna `DATABASE_URL` env var ([reservation_service.py:18](app/services/reservation_service.py#L18))
2. Preklopi na PostgreSQL ([reservation_service.py:63-65](app/services/reservation_service.py#L63-L65))
3. Ustvari tabele če ne obstajajo ([reservation_service.py:88](app/services/reservation_service.py#L88))

**Ni potrebno ničesar ročno migrirati!**

---

## Obstoječi Podatki

### Če želite prenesti obstoječe SQLite podatke v Postgres:

1. **Exportaj iz SQLite** (lokalno):
```bash
cd /Volumes/SSD\ KLJUC/KOVACNIK\ AI/ZDRAVSTVENI\ CENTER
python3 -c "
import sqlite3
import json
conn = sqlite3.connect('data/reservations.db')
cursor = conn.cursor()
cursor.execute('SELECT * FROM reservations')
rows = cursor.fetchall()
cols = [d[0] for d in cursor.description]
data = [dict(zip(cols, row)) for row in rows]
with open('reservations_export.json', 'w') as f:
    json.dump(data, f, indent=2)
print(f'Exported {len(data)} reservations')
"
```

2. **Importaj v Postgres** (preko API):
```bash
# Prenesite DATABASE_URL iz Railway
export DATABASE_URL="postgres://user:pass@host:port/db"

python3 -c "
import json
import psycopg2
with open('reservations_export.json') as f:
    data = json.load(f)
conn = psycopg2.connect('$DATABASE_URL')
cursor = conn.cursor()
for row in data:
    cursor.execute('''
        INSERT INTO reservations (date, time, name, email, phone, ...)
        VALUES (%s, %s, %s, %s, %s, ...)
    ''', (row['date'], row['time'], ...))
conn.commit()
print('Import complete!')
"
```

**ALI** enostavneje: Samo začnite z prazno bazo in naredite nove reservacije.

---

## Preverjanje

### Test 1: Ustvari naročilo
1. Odpri chatbot: https://[vaša-railway-url].railway.app
2. Naredite naročilo
3. Preverite v admin panelu da se prikaže

### Test 2: Re-deploy
1. Railway dashboard → **Redeploy**
2. Počakajte da deploy uspe
3. Preverite v admin panelu da naročila **ŠE VEDNO OBSTAJAJO** ✅

### Test 3: Database Content
Railway dashboard → PostgreSQL service → **Data** tab → Pogledate vsebino `reservations` tabele

---

## Stroški

Railway PostgreSQL:
- **Free tier**: 512 MB storage, 1GB RAM (zadostuje za testiranje)
- **Hobby tier**: $5/mesec za več storage/RAM

---

## Troubleshooting

### Problem: "Using SQLite database" v logih
**Rešitev**: DATABASE_URL ni nastavljen ali je napačen format
1. Preverite Variables v Railway
2. Dodajte: `DATABASE_URL = ${{Postgres.DATABASE_URL}}`
3. Redeploy

### Problem: "psycopg2 module not found"
**Rešitev**: Že dodano v requirements.txt (vrstica 10: `psycopg2-binary`)

### Problem: Baza je prazna po deploymentu
**Rešitev**:
1. Preverite da je PostgreSQL addon **v istem projektu** kot FastAPI app
2. Preverite DATABASE_URL reference

---

**Status po setup**: 🟢 Podatki bodo persistent čez vse deploymente!
