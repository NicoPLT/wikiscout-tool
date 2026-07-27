"""Seed di dati mock (Fase A) per popolare la dashboard senza chiavi API.

Crea l'utente scout (se AUTH_PASSWORD_HASH e' impostato in .env), 13
giocatori con dati fittizi ma realistici (squadre e campionati reali, nomi
di fantasia per non attribuire statistiche inventate a persone reali),
il loro storico partite/valore di mercato, e li aggiunge tutti alla
watchlist dell'utente.

Uso (dalla cartella backend, dopo `alembic upgrade head`):
    python scripts/seed_mock_data.py
"""

import random
import sys
from datetime import date, datetime, timedelta, timezone

sys.path.append(".")

from app.core.config import get_settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.db import base as _base  # noqa: E402,F401  # registra TUTTI i modelli prima di usare l'ORM
from app.models.market_value import PlayerMarketValueHistory  # noqa: E402
from app.models.player import Player  # noqa: E402
from app.models.stats import PlayerStatsMatch  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.watchlist import Watchlist  # noqa: E402

settings = get_settings()
random.seed(42)

TODAY = date.today()

# competition covered by Understat = Top 5 campionati europei
PLAYERS = [
    dict(
        full_name="Marco Bellandi",
        date_of_birth=date(2001, 3, 14),
        nationality="Italia",
        position="Attaccante",
        current_team="Fiorentina",
        league="Serie A",
        is_xg_covered=True,
        base_value=18_000_000,
    ),
    dict(
        full_name="Dario Conti",
        date_of_birth=date(1999, 7, 2),
        nationality="Italia",
        position="Centrocampista",
        current_team="Torino",
        league="Serie A",
        is_xg_covered=True,
        base_value=9_500_000,
    ),
    dict(
        full_name="Kwame Asante",
        date_of_birth=date(2002, 11, 20),
        nationality="Ghana",
        position="Attaccante",
        current_team="Brentford",
        league="Premier League",
        is_xg_covered=True,
        base_value=27_000_000,
    ),
    dict(
        full_name="Lucas Ferreira",
        date_of_birth=date(2000, 5, 9),
        nationality="Brasile",
        position="Centrocampista",
        current_team="Real Sociedad",
        league="La Liga",
        is_xg_covered=True,
        base_value=22_000_000,
    ),
    dict(
        full_name="Julian Hoffmann",
        date_of_birth=date(1998, 1, 30),
        nationality="Germania",
        position="Difensore",
        current_team="Werder Bremen",
        league="Bundesliga",
        is_xg_covered=True,
        base_value=12_000_000,
    ),
    dict(
        full_name="Antoine Lefevre",
        date_of_birth=date(2003, 9, 17),
        nationality="Francia",
        position="Centrocampista",
        current_team="Stade Rennais",
        league="Ligue 1",
        is_xg_covered=True,
        base_value=15_500_000,
    ),
    dict(
        full_name="Tomas Herrera",
        date_of_birth=date(2000, 2, 24),
        nationality="Spagna",
        position="Difensore",
        current_team="Celta Vigo",
        league="La Liga",
        is_xg_covered=True,
        base_value=8_000_000,
    ),
    dict(
        full_name="Bram van Dijk",
        date_of_birth=date(2001, 12, 5),
        nationality="Paesi Bassi",
        position="Attaccante",
        current_team="AZ Alkmaar",
        league="Eredivisie",
        is_xg_covered=False,
        base_value=6_500_000,
    ),
    dict(
        full_name="Rui Nogueira",
        date_of_birth=date(2002, 4, 11),
        nationality="Portogallo",
        position="Ala",
        current_team="Braga",
        league="Primeira Liga",
        is_xg_covered=False,
        base_value=11_000_000,
    ),
    dict(
        full_name="Milan Petrovic",
        date_of_birth=date(1999, 10, 8),
        nationality="Serbia",
        position="Centrocampista",
        current_team="Trabzonspor",
        league="Super Lig",
        is_xg_covered=False,
        base_value=4_500_000,
    ),
    dict(
        full_name="Ola Eriksen",
        date_of_birth=date(2000, 6, 19),
        nationality="Norvegia",
        position="Attaccante",
        current_team="Bodo/Glimt",
        league="Eliteserien",
        is_xg_covered=False,
        base_value=7_200_000,
    ),
    dict(
        full_name="Chidi Okafor",
        date_of_birth=date(2003, 3, 2),
        nationality="Nigeria",
        position="Attaccante",
        current_team="Leeds United",
        league="Championship",
        is_xg_covered=False,
        base_value=5_800_000,
    ),
    dict(
        full_name="Noah Bergstrom",
        date_of_birth=date(2001, 8, 27),
        nationality="Svezia",
        position="Centrocampista",
        current_team="Malmo FF",
        league="Allsvenskan",
        is_xg_covered=False,
        base_value=3_200_000,
    ),
]

OPPONENTS = [
    "AC Sparta",
    "Nord United",
    "Città Alta FC",
    "Rio Vermelho",
    "Deportivo Sur",
    "Athletic Norte",
    "Real Costa",
    "FC Alba",
    "Stella Rossa",
    "Porto Vecchio",
]


def build_matches(player: Player, n: int) -> list[PlayerStatsMatch]:
    matches = []
    for i in range(n):
        match_date = TODAY - timedelta(days=7 * (n - i))
        minutes = random.choice([90, 90, 90, 78, 65, 45, 90])
        goals = random.choices([0, 1, 2], weights=[65, 28, 7])[0]
        assists = random.choices([0, 1], weights=[75, 25])[0]
        rating = round(random.uniform(6.0, 8.3), 1)
        xg = round(goals * random.uniform(0.6, 1.3) + random.uniform(0, 0.3), 2) if player.is_xg_covered else None
        xa = round(assists * random.uniform(0.5, 1.1) + random.uniform(0, 0.2), 2) if player.is_xg_covered else None

        matches.append(
            PlayerStatsMatch(
                player_id=player.id,
                match_date=match_date,
                competition=player.league,
                opponent=random.choice(OPPONENTS),
                is_home=random.choice([True, False]),
                minutes_played=minutes,
                goals=goals,
                assists=assists,
                rating=rating,
                xg=xg,
                xa=xa,
                source="seed",
            )
        )
    return matches


def build_market_value_history(player: Player, base_value: float) -> list[PlayerMarketValueHistory]:
    points = []
    value = base_value * random.uniform(0.75, 0.9)
    for i in range(6, 0, -1):
        recorded_at = TODAY - timedelta(days=30 * i)
        value = value * random.uniform(0.95, 1.12)
        points.append(
            PlayerMarketValueHistory(
                player_id=player.id, value_eur=round(value, 2), recorded_at=recorded_at, source="seed"
            )
        )
    points.append(
        PlayerMarketValueHistory(
            player_id=player.id, value_eur=round(base_value, 2), recorded_at=TODAY, source="seed"
        )
    )
    return points


def main() -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == settings.AUTH_EMAIL).one_or_none()
        if user is not None:
            # Il seed e' pensato per il bootstrap iniziale (Fase A, prima di avere
            # dati reali). Se l'utente scout esiste gia' vuol dire che l'ambiente
            # e' gia' stato inizializzato (ed eventualmente lo scout ha gia'
            # rimosso volontariamente alcuni giocatori mock dalla watchlist): non
            # ricreare ne' ri-aggiungere nulla, altrimenti i mock rimossi
            # "ricompaiono" a ogni riesecuzione dello script.
            print(
                f"Utente scout {user.email} gia' presente: ambiente gia' inizializzato, "
                "seed saltato (nessuna modifica ai giocatori/watchlist esistenti)."
            )
            return

        if not settings.AUTH_PASSWORD_HASH:
            print(
                "AUTH_PASSWORD_HASH non impostato in .env: l'utente scout verra' creato "
                "automaticamente al primo login (vedi README). Seed solo dei giocatori."
            )
        else:
            user = User(email=settings.AUTH_EMAIL, hashed_password=settings.AUTH_PASSWORD_HASH)
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"Creato utente scout: {user.email}")

        created_players = []
        for idx, data in enumerate(PLAYERS, start=1):
            existing = db.query(Player).filter(Player.full_name == data["full_name"]).one_or_none()
            if existing is not None:
                created_players.append(existing)
                continue

            player = Player(
                full_name=data["full_name"],
                date_of_birth=data["date_of_birth"],
                nationality=data["nationality"],
                position=data["position"],
                current_team=data["current_team"],
                league=data["league"],
                photo_url=f"https://i.pravatar.cc/150?img={idx + 10}",
                transfermarkt_id=f"mock-tm-{idx}",
                api_football_id=f"mock-af-{idx}",
                sofascore_id=f"mock-sofa-{idx}",
                understat_id=f"mock-understat-{idx}" if data["is_xg_covered"] else None,
                is_xg_covered=data["is_xg_covered"],
                market_value_eur=data["base_value"],
                last_synced_at=datetime.now(timezone.utc) - timedelta(hours=random.randint(2, 60)),
            )
            db.add(player)
            db.flush()  # per ottenere player.id

            matches = build_matches(player, n=16)
            db.add_all(matches)

            mv_history = build_market_value_history(player, data["base_value"])
            db.add_all(mv_history)
            db.flush()

            last5 = sorted(matches, key=lambda m: m.match_date, reverse=True)[:5]
            player.goals_last5 = sum(m.goals for m in last5)
            player.assists_last5 = sum(m.assists for m in last5)
            player.goals_season = sum(m.goals for m in matches)
            player.assists_season = sum(m.assists for m in matches)
            player.appearances_season = len(matches)
            player.minutes_season = sum(m.minutes_played for m in matches)
            player.rating_avg = round(sum(m.rating for m in matches) / len(matches), 2)
            if player.is_xg_covered:
                player.xg_season = round(sum(m.xg or 0 for m in matches), 2)
                player.xa_season = round(sum(m.xa or 0 for m in matches), 2)

            mv_sorted = sorted(mv_history, key=lambda m: m.recorded_at)
            previous_value = float(mv_sorted[-2].value_eur)
            current_value = float(mv_sorted[-1].value_eur)
            player.market_value_eur = current_value
            player.market_value_change_eur = round(current_value - previous_value, 2)
            player.market_value_change_pct = round((current_value - previous_value) / previous_value * 100, 2)

            now = datetime.now(timezone.utc)
            player.stats_updated_at = now - timedelta(hours=random.randint(2, 40))
            player.market_value_updated_at = now - timedelta(days=random.randint(1, 6))
            player.rating_updated_at = now - timedelta(hours=random.randint(2, 40))

            created_players.append(player)
            print(f"Creato giocatore: {player.full_name} ({player.current_team})")

        db.commit()

        if user is not None:
            for player in created_players:
                exists = (
                    db.query(Watchlist)
                    .filter(Watchlist.user_id == user.id, Watchlist.player_id == player.id)
                    .one_or_none()
                )
                if exists is None:
                    db.add(Watchlist(user_id=user.id, player_id=player.id, tags=["mock"]))
            db.commit()
            print(f"Aggiunti {len(created_players)} giocatori alla watchlist di {user.email}")
        else:
            print(
                "Nessun utente creato: imposta AUTH_PASSWORD_HASH e rilancia lo script per "
                "popolare anche la watchlist, oppure aggiungi i giocatori dalla UI dopo il login."
            )

        print("Seed completato.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
