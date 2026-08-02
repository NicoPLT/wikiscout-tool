"""Un singolo import chiamava get_current_club_id, get_season_summary e
get_recent_matches sullo stesso player_id: tutte e tre rifacevano
indipendentemente la stessa richiesta pesante (l'intera carriera del
giocatore). Misurato dal vivo su un caso reale: un singolo import poteva
superare il minuto. Questi test verificano che la cache elimini le
richieste ridondanti senza servire dati diversi da quelli che si
otterrebbero senza cache."""

import pytest

from app.scrapers import transfermarkt_performance as tp


@pytest.fixture(autouse=True)
def _reset_caches():
    """Le cache sono dict a livello di modulo: senza reset si sporcano
    tra un test e l'altro."""
    tp._all_games_cache.clear()
    tp._competition_name_cache.clear()
    tp._club_name_cache.clear()
    tp._club_primary_competition_cache.clear()
    yield
    tp._all_games_cache.clear()
    tp._competition_name_cache.clear()
    tp._club_name_cache.clear()
    tp._club_primary_competition_cache.clear()


def _fake_game(season_id=2025, club_id="1", competition_id="IT1", is_national=False):
    return {
        "gameInformation": {
            "gameId": "1",
            "competitionId": competition_id,
            "seasonId": season_id,
            "isNationalGame": is_national,
            "isGamePostponed": False,
            "date": {"dateTimeUTC": "2026-01-01T00:00:00+00:00"},
            "season": {"nonCyclicalName": "25/26"},
        },
        "clubsInformation": {
            "club": {"clubId": club_id, "venue": "home"},
            "opponent": {"clubId": "2", "venue": "away"},
        },
        "statistics": {
            "generalStatistics": {"participationState": "played"},
            "goalStatistics": {"goalsScoredTotal": 1, "assists": 0},
            "cardStatistics": {"yellowCardGross": 0},
            "playingTimeStatistics": {"playedMinutes": 90, "isStarting": True},
        },
    }


class _CountingGet:
    def __init__(self, response_by_path):
        self.calls: list[str] = []
        self._response_by_path = response_by_path

    def __call__(self, path, params=None):
        self.calls.append(path)
        return self._response_by_path.get(path, {"data": []})


def test_get_all_games_is_cached_within_ttl(monkeypatch):
    games = [_fake_game()]
    fake_get = _CountingGet({"/player/123/performance-game": {"data": {"performance": games}}})
    monkeypatch.setattr(tp, "_get", fake_get)

    first = tp.get_all_games("123")
    second = tp.get_all_games("123")

    assert first == games
    assert second == games
    assert fake_get.calls == ["/player/123/performance-game"], "seconda chiamata non doveva rifare la richiesta"


def test_get_all_games_cache_expires_after_ttl(monkeypatch):
    games = [_fake_game()]
    fake_get = _CountingGet({"/player/123/performance-game": {"data": {"performance": games}}})
    monkeypatch.setattr(tp, "_get", fake_get)
    monkeypatch.setattr(tp, "_ALL_GAMES_CACHE_TTL_SECONDS", 0.0)

    tp.get_all_games("123")
    tp.get_all_games("123")

    assert fake_get.calls == ["/player/123/performance-game", "/player/123/performance-game"]


def test_get_all_games_cache_is_per_player(monkeypatch):
    fake_get = _CountingGet(
        {
            "/player/123/performance-game": {"data": {"performance": [_fake_game()]}},
            "/player/456/performance-game": {"data": {"performance": []}},
        }
    )
    monkeypatch.setattr(tp, "_get", fake_get)

    tp.get_all_games("123")
    tp.get_all_games("456")
    tp.get_all_games("123")

    assert fake_get.calls == ["/player/123/performance-game", "/player/456/performance-game"]


def test_single_import_style_sequence_fetches_games_only_once(monkeypatch):
    """Riproduce esattamente la sequenza usata da
    import_player_from_transfermarkt: get_current_club_id ->
    get_season_summary -> get_recent_matches, tutte sullo stesso
    player_id."""
    games = [_fake_game(season_id=2025, club_id="1"), _fake_game(season_id=2025, club_id="1")]
    fake_get = _CountingGet(
        {
            "/player/123/performance-game": {"data": {"performance": games}},
            "/clubs": {"data": [{"id": "1", "name": "Test FC", "baseDetails": {"primaryCompetitionId": "IT1"}}]},
            "/competitions": {"data": [{"id": "IT1", "name": "Serie A"}]},
        }
    )
    monkeypatch.setattr(tp, "_get", fake_get)

    club_id = tp.get_current_club_id("123")
    tp.get_season_summary("123", club_id)
    tp.get_recent_matches("123", limit=5)

    games_fetches = [c for c in fake_get.calls if c == "/player/123/performance-game"]
    assert len(games_fetches) == 1, f"attese 1 fetch di performance-game, trovate {len(games_fetches)}: {fake_get.calls}"


def test_resolve_competition_names_does_not_refetch_cached_ids(monkeypatch):
    fake_get = _CountingGet({"/competitions": {"data": [{"id": "IT1", "name": "Serie A"}]}})
    monkeypatch.setattr(tp, "_get", fake_get)

    first = tp.resolve_competition_names({"IT1"})
    second = tp.resolve_competition_names({"IT1"})

    assert first == {"IT1": "Serie A"}
    assert second == {"IT1": "Serie A"}
    assert fake_get.calls == ["/competitions"]


def test_resolve_competition_names_only_fetches_missing_ids(monkeypatch):
    tp._competition_name_cache["IT1"] = "Serie A"
    fake_get = _CountingGet({"/competitions": {"data": [{"id": "EL", "name": "UEFA Europa League"}]}})
    monkeypatch.setattr(tp, "_get", fake_get)

    result = tp.resolve_competition_names({"IT1", "EL"})

    assert result == {"IT1": "Serie A", "EL": "UEFA Europa League"}
    assert fake_get.calls == ["/competitions"]


def test_resolve_club_names_does_not_refetch_cached_ids(monkeypatch):
    fake_get = _CountingGet({"/clubs": {"data": [{"id": "1", "name": "Test FC"}]}})
    monkeypatch.setattr(tp, "_get", fake_get)

    tp.resolve_club_names({"1"})
    tp.resolve_club_names({"1"})

    assert fake_get.calls == ["/clubs"]


def test_get_club_primary_competition_is_cached(monkeypatch):
    fake_get = _CountingGet(
        {"/clubs": {"data": [{"id": "1", "baseDetails": {"primaryCompetitionId": "IT1"}}]}}
    )
    monkeypatch.setattr(tp, "_get", fake_get)

    first = tp.get_club_primary_competition("1")
    second = tp.get_club_primary_competition("1")

    assert first == "IT1"
    assert second == "IT1"
    assert fake_get.calls == ["/clubs"]
