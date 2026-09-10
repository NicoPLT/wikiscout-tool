# WikiScout Tool

Watchlist personale di calcio per un solo scout. Frontend React/Vite su Netlify,
API FastAPI su Render Free, database PostgreSQL su Neon Free. Gli aggiornamenti
sono eseguiti direttamente da GitHub Actions: non richiedono Cron Render, Apify,
API-Football, Redis o altri servizi a pagamento.

## Comportamento

- La ricerca interroga Transfermarkt; aggiunta, dashboard e schede usano il database.
- Un nuovo giocatore compare subito come **In attesa**. Le statistiche mancanti
  vengono recuperate al prossimo giro notturno o avviando manualmente il workflow.
- Statistiche e rating: non prima di 20 ore dall'ultimo successo. Valori di
  mercato, anagrafica/link e trasferimenti: settimanalmente.
- Lo storico stagioni e trasferimenti e' persistito. La scheda non apre browser.
- Ogni fonte salva ultimo tentativo, ultimo successo, errore e prossimo tentativo.
  Un fallimento conserva i dati precedenti e viene ritentato non prima di 6 ore.
- Le modifiche sono salvate per giocatore/fonte: un'interruzione non annulla tutto
  il giro. I giocatori con tentativi piu' vecchi vengono elaborati prima.
- Il worker si ferma dopo circa 35 minuti (piu' la richiesta in corso); il workflow
  ha un limite assoluto di 45 minuti. Un primo caricamento di 200 profili potrebbe
  richiedere piu' giri. Non esiste una garanzia di copertura delle fonti non ufficiali.
- La tabella AG Grid viene scaricata soltanto su desktop. Il mobile usa le card.
- Il login avvia il backend mentre si compilano le credenziali. Un errore di rete
  durante il ripristino della sessione permette di riprovare senza perdere il token;
  una sessione rifiutata con 401 richiede invece un nuovo accesso.
- La watchlist appare senza attendere i tag. Dopo il login le letture della lista
  e dei tag hanno limiti rispettivamente di 30 e 15 secondi; l'accesso iniziale
  attende fino a 120 secondi per consentire il riavvio del servizio gratuito.
- Durante accesso, apertura della schermata e caricamento dei dati, un cronometro
  mostra il tempo trascorso nella fase corrente. L'avviso distingue l'eventuale
  riavvio iniziale dal recupero dei dati; non mostra percentuali o tempi rimanenti
  che il server non fornisce.
- **Esporta dati** scarica un JSON con giocatori, note, tag, statistiche e alert.
  L'esportazione non contiene hash di login o segreti. Conservarla privatamente.

## Attivazione online

Seguire [la guida operativa gratuita](docs/free-deployment.md). Il workflow e'
intenzionalmente disabilitato finche' non sono configurati i segreti e la variabile
`WIKISCOUT_SYNC_ENABLED=true`. Non creare il Cron Render descritto nel vecchio handoff.

## Sviluppo locale

1. Avviare PostgreSQL con `docker compose up -d`. Redis e' facoltativo.
2. In `backend/`, creare un ambiente Python 3.11 e installare
   `pip install -r requirements-dev.txt`.
3. Copiare `.env.example` in `.env`, impostare database, email, hash password,
   chiave JWT e CORS. Generare l'hash con `python scripts/hash_password.py "password scelta"`.
4. Eseguire `alembic upgrade head` e `uvicorn app.main:app --reload`.
5. In `frontend/`, eseguire `npm ci`, impostare `VITE_API_BASE_URL` e `npm run dev`.
6. Per eseguire il worker in locale: `python -m playwright install chromium`,
   poi `python scripts/run_nightly.py` dalla cartella backend.

`ENABLE_SCHEDULER=false` e' il default. Abilitarlo solo per un processo locale che
resta acceso. Il vecchio `POST /internal/nightly-job` non avvia piu' thread: risponde
503 se disabilitato, 401 con segreto errato, 410 con segreto valido.

## Verifiche

```text
cd backend
python -m pytest -q
cd ../frontend
npm run build
npm run lint
```

La suite copre import e letture senza rete, una watchlist di 200 giocatori,
aggiornamenti parziali, rollback, checkpoint, limiti del worker, lock con scadenza,
valutazioni gratuite, rating per partita, backup/ripristino e autenticazione export.
Le prove locali usano SQLite in memoria e fonti simulate: non consumano API esterne.
La migrazione `0008_free_sync` aggiunge colonne e una tabella, senza rimuovere dati.

Per il controllo browser locale: avviare il frontend e lanciare
`python scripts/check_ui.py --base-url http://127.0.0.1:5175` dal backend.
Le API sono intercettate e simulate; il controllo non usa il database online.

Per verificare anche login, timeout, ripristino della sessione, tag lenti e recupero
di un file JavaScript non scaricato, usare la build di produzione:

```text
cd frontend
npm run build
npm run preview -- --host 127.0.0.1 --port 5175
# In un altro terminale, dalla cartella backend:
python scripts/check_startup_ui.py --base-url http://127.0.0.1:5175
```

Le correzioni all'avvio richiedono il deploy sia del frontend Netlify sia del
backend Render. Non richiedono migrazioni aggiuntive o nuove variabili d'ambiente.
Durante i deploy separati, il frontend resta compatibile con la precedente
risposta di login del backend.
