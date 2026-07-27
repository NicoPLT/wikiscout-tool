# WikiScout Tool

Applicazione interna per scout di calcio: watchlist personale di giocatori con
dashboard in stile foglio Excel (AG Grid), aggiornata una volta al giorno da
un job notturno (non live).

Monorepo:

```
wikiscout-tool/
  frontend/   React 18 + Vite + TypeScript + AG Grid + Tailwind
  backend/    FastAPI + PostgreSQL + Redis + APScheduler
  docker-compose.yml   Postgres + Redis per lo sviluppo locale
```

## Fase A vs Fase B

Il progetto e' pensato per essere usabile subito, senza chiavi API:

- **Fase A (ora)**: tutta l'app funziona con dati mock, generati dallo script
  `backend/scripts/seed_mock_data.py` direttamente nel database. 13 giocatori
  di fantasia, squadre e campionati reali, con storico partite e valore di
  mercato.
- **Fase B (quando avrai le chiavi)**: gli scraper in `backend/app/scrapers/`
  sono gia' scritti e collegati al job notturno, ma restano "spenti" finche'
  `API_FOOTBALL_KEY` / `APIFY_TOKEN` non sono impostate in `.env` — vedi
  [dove ottenere le chiavi](#fase-b-chiavi-api-esterne) piu' sotto.

Il layer che legge/scrive i dati (`backend/app/services/player_service.py`)
e' lo stesso in entrambe le fasi: cambia solo chi popola le tabelle
(seed vs. job di scraping), non come la dashboard le legge.

## Setup locale

### 1. Database e cache (Docker)

```bash
docker compose up -d
```

Avvia Postgres (porta 5432, utente/password/db `wikiscout`) e Redis (porta
6379). Se non usi Docker, installa Postgres 16+ e Redis 7+ localmente e
aggiorna `DATABASE_URL` / `REDIS_URL` in `backend/.env` di conseguenza.

### 2. Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate    # macOS/Linux

pip install -r requirements.txt
copy .env.example .env         # Windows: copy, macOS/Linux: cp

# genera l'hash della password del tuo account scout e incollalo in .env
# come AUTH_PASSWORD_HASH
python scripts/hash_password.py "la-tua-password"

alembic upgrade head
python scripts/seed_mock_data.py

uvicorn app.main:app --reload
```

L'API e' su `http://localhost:8000` (docs interattive su `/docs`).

### 3. Frontend

```bash
cd frontend
npm install
copy .env.example .env.local   # o cp su macOS/Linux
npm run dev
```

L'app e' su `http://localhost:5173`. Accedi con l'email in `AUTH_EMAIL`
(default `scout@wikiscout.it`) e la password usata al passo precedente.

## Struttura dati (Postgres)

| Tabella | Contenuto |
|---|---|
| `players` | anagrafica + id esterni (Transfermarkt/API-Football/Sofascore/Understat) + snapshot denormalizzato per la dashboard |
| `player_stats_matches` | statistiche partita per partita (fonte di verita' per la pagina di dettaglio) |
| `player_market_value_history` | storico valore di mercato |
| `watchlists` | giocatori seguiti da un utente, con note/tag |
| `data_sources_log` | log di ogni esecuzione del job di aggiornamento |
| `users` | account (single-user) |

Migration in `backend/alembic/versions/`. Per generarne di nuove dopo aver
modificato i modelli in `backend/app/models/`:

```bash
alembic revision --autogenerate -m "descrizione"
alembic upgrade head
```

## Job notturno di aggiornamento

`backend/app/scrapers/jobs.py` orchestra, una volta al giorno (default 03:00
UTC, configurabile con `NIGHTLY_JOB_HOUR`/`NIGHTLY_JOB_MINUTE`), per ogni
giocatore in watchlist:

1. Statistiche recenti da API-Football (se ha giocato nelle ultime 48h)
2. xG/xA da Understat, solo per i campionati coperti (Top 5 europei)
3. Valore di mercato da Transfermarkt (refresh settimanale, non giornaliero)
4. Rating da Sofascore

Ogni chiamata alle API esterne e' loggata e conteggiata (`app/scrapers/rate_limit.py`)
per non sforare i limiti giornalieri gratuiti; se manca la chiave o si e'
vicini al limite, lo step viene saltato con un warning nei log e in
`data_sources_log`, senza rompere il job.

## Fase B: chiavi API esterne

Finche' i campi restano vuoti in `.env`, l'app funziona comunque con i dati
del seed mock.

- **API-Football**: statistiche partite/goal/assist/minuti.
  Registrati su https://www.api-football.com/ (piano gratuito disponibile,
  anche via RapidAPI) e incolla la chiave in `API_FOOTBALL_KEY`.
- **Apify** (usato per gli scraper mirati di Understat/Transfermarkt/Sofascore):
  registrati su https://apify.com/, crea un token API personale e incollalo
  in `APIFY_TOKEN`. Dovrai anche configurare/scegliere gli actor Apify da
  usare per ciascuna fonte in `backend/app/scrapers/understat.py`,
  `transfermarkt.py`, `sofascore.py` (variabili `*_ACTOR_ID` in cima al file).

## Deploy

Split su due provider: il backend ha bisogno di un processo persistente
(scheduler notturno) + Postgres + Redis, cosa che Netlify/Vercel da soli non
offrono bene; il frontend statico invece va benissimo su Netlify.

### Backend + DB + Redis → Railway

1. Crea un nuovo progetto Railway, aggiungi i plugin **PostgreSQL** e **Redis**
   (Railway genera automaticamente `DATABASE_URL`/`REDIS_URL` come variabili,
   ma il codice si aspetta i nomi usati in `.env.example`: mappa/rinomina le
   variabili del servizio backend di conseguenza, es.
   `DATABASE_URL=${{Postgres.DATABASE_URL}}` sostituendo il driver con
   `postgresql+psycopg2://` se necessario).
2. Collega il repository, imposta **Root Directory** su `backend/`.
3. Railway rileva `requirements.txt` (Nixpacks) e usa il `Procfile`:
   `web: bash -c "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT"`
   — esegue le migration e avvia sia l'API che lo scheduler (in-process via
   APScheduler) con un solo comando.
4. Variabili d'ambiente da impostare (vedi `backend/.env.example`):
   `SECRET_KEY`, `AUTH_EMAIL`, `AUTH_PASSWORD_HASH`, `CORS_ORIGINS`
   (l'URL Netlify del frontend), `ENABLE_SCHEDULER`, `NIGHTLY_JOB_HOUR`,
   `NIGHTLY_JOB_MINUTE`, e in Fase B `API_FOOTBALL_KEY`/`APIFY_TOKEN`.
5. Dopo il primo deploy, esegui una volta il seed mock (Fase A) da una shell
   Railway o in locale puntando a `DATABASE_URL` di Railway:
   `python scripts/seed_mock_data.py`.

### Frontend → Netlify

1. Nuovo sito Netlify collegato al repo, **Base directory** `frontend/`.
2. `netlify.toml` gia' presente imposta build command (`npm run build`) e
   publish directory (`dist`), oltre al redirect SPA per React Router.
3. Imposta la variabile d'ambiente `VITE_API_BASE_URL` (Site settings >
   Environment variables) con l'URL pubblico del servizio Railway.
4. Deploy.

## Login single-user

Un solo account (email/password), pensato solo per proteggere la watchlist
da accessi pubblici — nessuna gestione ruoli/inviti. La password si imposta
generando un hash bcrypt con `backend/scripts/hash_password.py` e
incollandolo in `AUTH_PASSWORD_HASH`; l'utente viene creato automaticamente
al primo login (o dal seed, se l'hash e' gia' impostato prima di eseguirlo).
