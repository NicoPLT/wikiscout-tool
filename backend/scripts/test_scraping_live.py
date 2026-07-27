"""Debug rapido dello scraping live, senza far girare tutto il job notturno.

Uso (dalla cartella backend, con .venv attivo):
    python scripts/test_scraping_live.py "Erling Haaland"

Stampa: risultati ricerca Transfermarkt, e per il primo risultato il
matching Sofascore + statistiche stagionali + ultime partite reali.
Non scrive nulla nel database: solo lettura, per verificare velocemente se
uno scraper si e' rotto (es. Transfermarkt/Sofascore hanno cambiato la
struttura delle pagine) senza aspettare il giro notturno completo.
"""

import json
import sys

sys.path.append(".")

from app.scrapers import sofascore, transfermarkt  # noqa: E402


def main() -> None:
    if len(sys.argv) != 2:
        print('Uso: python scripts/test_scraping_live.py "Nome Cognome"')
        raise SystemExit(1)

    query = sys.argv[1]

    print(f"=== Ricerca Transfermarkt: '{query}' ===")
    tm_results = transfermarkt.search_players_transfermarkt(query)
    print(json.dumps(tm_results, indent=2, ensure_ascii=False))

    if not tm_results:
        print("Nessun risultato Transfermarkt, mi fermo qui.")
        return

    top = tm_results[0]
    print(f"\n=== Sofascore: ricerca+statistiche per '{top['full_name']}' ({top['current_team']}) ===")

    with sofascore.SofascoreSession() as session:
        if not session.ok:
            print("Sessione Sofascore non disponibile (Playwright/Chromium mancante?).")
            return

        candidates = sofascore.search_players(session, top["full_name"])
        print("Candidati Sofascore:", json.dumps(candidates, indent=2, ensure_ascii=False))

        if not candidates:
            print("Nessun candidato Sofascore trovato.")
            return

        sofascore_id = candidates[0]["id"]
        season_stats = sofascore.get_season_stats(session, sofascore_id)
        print("\nStatistiche stagionali:", json.dumps(season_stats, indent=2, ensure_ascii=False))

        recent_matches = sofascore.get_recent_matches(session, sofascore_id, limit=5)
        print(
            "\nUltime partite:",
            json.dumps(recent_matches, indent=2, ensure_ascii=False, default=str),
        )


if __name__ == "__main__":
    main()
