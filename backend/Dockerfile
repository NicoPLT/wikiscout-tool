# Immagine ufficiale Playwright: Python + Chromium + tutte le dipendenze di
# sistema gia' installate e allineate alla versione di playwright in
# requirements.txt. Necessaria per lo scraping Sofascore (app/scrapers/sofascore.py):
# Nixpacks da solo non installa i pacchetti di sistema che Chromium richiede,
# questo Dockerfile evita quel problema alla radice. Railway rileva
# automaticamente questo file e lo usa al posto di Nixpacks/Procfile.
FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT"]
