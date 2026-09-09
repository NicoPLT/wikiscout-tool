# Attivare WikiScout senza servizi a pagamento

Questa guida sostituisce la parte di deploy del vecchio handoff. Il codice e' per
un singolo utente. Nessuna password/connection string va incollata nel repository.

## 1. Pubblicare le modifiche

Pubblicare questo codice sul branch principale del repository collegato a Render
e Netlify. Il Dockerfile Render esegue `alembic upgrade head` prima di avviare l'API.
La revisione attesa e' `0008_free_sync`; aggiunge checkpoint, dati storici salvati e
il lock del worker. Non cancella i giocatori esistenti.

Prima di un deploy fare una copia del database dalla propria connessione PostgreSQL
(ad esempio `pg_dump` in locale). Il nuovo backup richiede lo schema aggiornato.

Sul servizio Render creato manualmente verificare:

```text
ENABLE_SCHEDULER=false
REDIS_URL=
APIFY_TOKEN=
ENABLE_API_FOOTBALL=false
```

Mantenere `DATABASE_URL`, `SECRET_KEY`, `AUTH_EMAIL`, `AUTH_PASSWORD_HASH` e
`CORS_ORIGINS` gia' corretti. `NIGHTLY_JOB_SECRET` non serve piu'. Non creare Cron
Render: [prevede un costo minimo mensile](https://render.com/docs/cronjobs).
Il file `render.yaml` descrive solo il servizio web Free; non modifica da solo un
servizio creato manualmente. Netlify mantiene `VITE_API_BASE_URL` invariato.

## 2. Preparare i due segreti GitHub

Nel repository: Settings > Secrets and variables > Actions > Secrets.

- `NEON_DATABASE_URL`: stessa connessione PostgreSQL Neon del backend, completa di
  `sslmode=require`. Accetta `postgresql://` oppure `postgresql+psycopg2://`.
- `BACKUP_ENCRYPTION_KEY`: una chiave generata **una volta sola**, dalla cartella
  backend con `python scripts/backup.py --generate-key` dopo aver installato le
  dipendenze. Salvare la chiave anche nel proprio password manager: serve per
  ripristinare i backup, GitHub non permette di rileggere un segreto salvato.

Non impostare chiavi Apify o API-Football. Non occorre un token GitHub personale.
Il token automatico del workflow ha solamente `contents: read`.

Dopo il deploy riuscito, sotto Actions > Variables aggiungere:

```text
WIKISCOUT_SYNC_ENABLED=true
```

## 3. Primo aggiornamento

Aprire Actions > **Aggiornamento e backup WikiScout** > **Run workflow** sul branch
principale. Il job controlla la configurazione, installa solo Chromium, crea e
carica il backup cifrato, poi esegue il worker direttamente sul runner GitHub.
Il processo Render non viene usato per lo scraping notturno.

La programmazione e' ogni giorno alle **03:17 UTC** (05:17 italiane in estate,
04:17 in inverno). GitHub puo' ritardare l'avvio; non e' un servizio con orario
garantito. Nei repository pubblici la programmazione viene disabilitata dopo
60 giorni senza attivita': controllare periodicamente Actions e riabilitarla se
necessario. [Regole GitHub](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

Un run `partial`/`error` risulta fallito in Actions per rendere visibili i problemi;
i checkpoint gia' salvati restano validi. La scheda mostra quale fonte e' mancante.
Un rerun immediato salta le fonti riuscite e rispetta l'attesa di 6 ore per gli
errori. Dopo un arresto forzato il lock scade in 10 minuti. Non lanciare workflow
in parallelo per accelerare: aumenterebbe solo il rischio di blocco delle fonti.

## 4. Budget gratuito

Il limite del workflow e' 45 minuti, incluso setup e backup, quindi al massimo
1.395 minuti per 31 esecuzioni giornaliere. Le esecuzioni manuali e gli altri
repository consumano la stessa quota dell'account. GitHub Free include 2.000
minuti mensili sui repository privati con runner standard. I runner standard
nei repository pubblici sono gratuiti; non serve rendere pubblico il progetto.
[Quote ufficiali](https://docs.github.com/en/billing/concepts/product-billing/github-actions).

Per evitare addebiti, mantenere i piani Free e verificare il blocco della spesa
extra nelle impostazioni di fatturazione dell'account. GitHub senza metodo di
pagamento blocca gli utilizzi oltre quota. Su un account con carta gia' presente,
impostare un budget Actions con arresto all'esaurimento; il limite di 45 minuti
non controlla gli altri consumi dell'account.

Backup cifrati: retention 14 giorni. Controllare che artifact e Packages restino
entro i 500 MB inclusi di GitHub Free. Controllare anche le quote effettive Neon
(storage e CU-ore) e Netlify (il piano puo' essere legacy o a crediti). Questi
limiti sono imposti dai provider e non possono essere eliminati dal codice.

## 5. Scaricare e ripristinare un backup

Aprire un run GitHub, scaricare l'artifact `wikiscout-backup-...` e scompattarlo:
contiene `wikiscout.backup.enc`. Nessun backup e' aggiunto al repository. Ogni
backup contiene l'applicazione **prima** dell'aggiornamento notturno; le modifiche
successive entreranno nel backup del giorno dopo. L'export dalla UI e' immediato.

Per ripristinare:

1. Preparare un database PostgreSQL **vuoto** ed eseguire le migrazioni.
2. Configurare `DATABASE_URL` verso quel database, `AUTH_EMAIL`,
   `AUTH_PASSWORD_HASH` e la `BACKUP_ENCRYPTION_KEY` originale. Non puntare il
   comando al database in uso: lo script rifiuta destinazioni non vuote.
3. Dalla cartella backend eseguire:

```text
python scripts/backup.py --restore percorso/wikiscout.backup.enc
```

Il ripristino conserva ID, note, tag, statistiche, alert e checkpoint. La password
viene presa dall'hash configurato per il ripristino: gli hash originali non sono
nei backup. Verificare accesso e dati prima di cambiare la connessione Render.

Per creare una copia cifrata in locale:

```text
python scripts/backup.py --output ../backups/wikiscout.backup.enc
```

`BACKUP_ENCRYPTION_KEY` puo' essere una variabile d'ambiente oppure stare nel file locale backend/.env. Le
esportazioni JSON della UI sono leggibili e vanno conservate privatamente; non
sono file `.enc`. Per ripristinarle nello stesso database vuoto, usare
`python scripts/backup.py --restore-json percorso/wikiscout-export.json` (nessuna chiave
di cifratura necessaria).
