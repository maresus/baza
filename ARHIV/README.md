# ARHIV

Ta mapa je namenjena arhiviranju testnih podatkov in zgodovine.

Zgodovina pogovorov je shranjena v PostgreSQL bazi (tabela `chat_messages`),
zato podatki ostanejo tudi po vnovičnem deploymentu.

## Dostop do zgodovine pogovorov

Zgodovina pogovorov je dostopna v admin panelu:
- Odprite `/admin` ali `/admin_new`
- Pojdite na zavihek "Orodja & Analitika"
- Kliknite na "📝 Zgodovina pogovorov"

Tam boste videli vse pogovore iz zadnjih 7 dni.
