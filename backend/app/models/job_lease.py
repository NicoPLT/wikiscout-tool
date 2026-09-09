from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class JobLease(Base):
    """Renewable lock shared by all workers, including separate CI runners."""

    __tablename__ = "job_leases"
    name: Mapped[str] = mapped_column(String(50), primary_key=True)
    owner: Mapped[str | None] = mapped_column(String(36), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
