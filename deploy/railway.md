# Railway setup (osnutek)

1) Ustvari GitHub repo in pushaj mono-repo.
2) V Railway dodaj projekt iz GitHub repo.
3) Dodaj Redis service (Railway -> New -> Redis).
4) Ustvari dva servisa (kovacnik, pod-goro) in za oba nastavi:
   - REDIS_URL
   - OPENAI_API_KEY
   - DATABASE_URL (ce se uporablja)

Naslednji korak bo: pripravimo Dockerfile/Procfile za oba servisa.
