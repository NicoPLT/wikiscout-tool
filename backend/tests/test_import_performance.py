"""Import di un giocatore nuovo: aggiungerlo dalla barra di ricerca deve
restare veloce. Il collegamento Sofascore (ricerca nome + fetch statistiche
via browser Playwright) era il passo piu' lento in assoluto (misurato dal
vivo: ~25-30s da solo, su un totale che superava il minuto) e bloccava il
"+ Aggiungi" in modo sincrono: questi test verificano che import_player_
from_transfermarkt non apra piu' una sessione Sofascore, e che il
collegamento avvenga invece on-demand alla prima apertura della scheda
giocatore (get_player_detail), come gia' succede per fotmob_id/date_of_birth.
"""

from app.models.player import Player
from app.models.user import User
from app.services import player_service


def test_import_does_not_open_a_sofascore_session(db_session, monkeypatch):
    user = User(email="scout@test.com", hashed_password="x")
    db_session.add(user)
    db_session.commit()

    # Rende innocue le altre chiamate esterne durante l'import: qui
    # interessa solo verificare che Sofascore non venga toccato.
    monkeypatch.setattr(player_service, "_apply_transfermarkt_performance", lambda db, player: False)
    monkeypatch.setattr(player_service, "_backfill_market_value_history", lambda db, player: False)
    monkeypatch.setattr(player_service, "resolve_fotmob_link", lambda player: False)
    monkeypatch.setattr(player_service, "resolve_date_of_birth", lambda player: False)

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("import_player_from_transfermarkt non deve piu' aprire una sessione Sofascore")

    monkeypatch.setattr(player_service.sofascore, "SofascoreSession", _fail_if_called)

    player = player_service.import_player_from_transfermarkt(
        db_session, user.id, "999999", "Test Player", "Test FC", "CF", "Italia", 1_000_000.0, None
    )

    assert player is not None
    assert player.sofascore_id is None


def test_get_player_detail_resolves_sofascore_on_demand(db_session, monkeypatch):
    user = User(email="scout@test.com", hashed_password="x")
    db_session.add(user)
    db_session.flush()
    player = Player(full_name="Test Player", current_team="Test FC", transfermarkt_id="999999")
    db_session.add(player)
    db_session.flush()

    from app.models.watchlist import Watchlist

    db_session.add(Watchlist(user_id=user.id, player_id=player.id))
    db_session.commit()

    calls = []

    def _fake_resolve_sofascore_link(db, p):
        calls.append(p.id)
        p.sofascore_id = "12345"
        return True

    monkeypatch.setattr(player_service, "resolve_sofascore_link", _fake_resolve_sofascore_link)
    monkeypatch.setattr(player_service, "resolve_fotmob_link", lambda p: False)
    monkeypatch.setattr(player_service, "resolve_date_of_birth", lambda p: False)

    detail = player_service.get_player_detail(db_session, user.id, player.id)

    assert detail is not None
    assert calls == [player.id]
    assert detail.sofascore_id == "12345"


def test_resolve_sofascore_link_skips_if_already_linked(db_session, monkeypatch):
    player = Player(full_name="Test Player", current_team="Test FC", sofascore_id="already-set")

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("non deve aprire una sessione Sofascore se sofascore_id e' gia' impostato")

    monkeypatch.setattr(player_service.sofascore, "SofascoreSession", _fail_if_called)

    result = player_service.resolve_sofascore_link(db_session, player)

    assert result is False
