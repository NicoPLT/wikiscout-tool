"""Importa tutti i modelli cosi' che Base.metadata li conosca (usato da Alembic)."""

from app.db.base_class import Base  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.player import Player  # noqa: F401
from app.models.stats import PlayerStatsMatch  # noqa: F401
from app.models.market_value import PlayerMarketValueHistory  # noqa: F401
from app.models.tag import Tag  # noqa: F401
from app.models.watchlist import Watchlist  # noqa: F401
from app.models.data_source_log import DataSourceLog  # noqa: F401
from app.models.watch_alert import PlayerWatchAlert  # noqa: F401
