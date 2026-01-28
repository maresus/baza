# kovacnik-bots (mono-repo)

En skupen repozitorij za vec strank (Kovacnik, Pod Goro, ...).
Core logika bo skupna, vsaka stranka ima svoj config + knowledge.

Struktura:
- core/        -> skupni motor (router, state, rag)
- apps/        -> posamezne stranke (config, knowledge, prompts)
- tests/       -> golden testi
- deploy/      -> Railway/infra config

Zacetek: najprej pripravimo infra (Redis, scaffold), nato migriramo kodo.
