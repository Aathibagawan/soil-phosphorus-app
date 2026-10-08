"""SQLAlchemy engine/session + prediction history table."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterator

from sqlalchemy import JSON, DateTime, Float, Integer, String, create_engine, delete, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from .config import DATABASE_URL, MAX_HISTORY_PER_CLIENT

_is_sqlite = DATABASE_URL.startswith("sqlite")
if _is_sqlite:
    from pathlib import Path
    Path(DATABASE_URL.replace("sqlite:///", "", 1)).parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_id: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    input_mode: Mapped[str] = mapped_column(String(20))
    rows_used: Mapped[int] = mapped_column(Integer)
    prediction: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(20))
    inputs: Mapped[dict] = mapped_column(JSON)            # {"mean": {...}, "last": {...}}
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    model_version: Mapped[str] = mapped_column(String(40))
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)


def init_db() -> None:
    Base.metadata.create_all(engine)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def save_prediction(db: Session, **fields) -> Prediction:
    row = Prediction(**fields)
    db.add(row)
    db.flush()
    # Retention: keep only the newest MAX_HISTORY_PER_CLIENT rows per client.
    cid = fields["client_id"]
    total = db.scalar(select(func.count()).select_from(Prediction).where(Prediction.client_id == cid)) or 0
    if total > MAX_HISTORY_PER_CLIENT:
        old_ids = db.scalars(
            select(Prediction.id).where(Prediction.client_id == cid)
            .order_by(Prediction.id.asc()).limit(total - MAX_HISTORY_PER_CLIENT)
        ).all()
        db.execute(delete(Prediction).where(Prediction.id.in_(old_ids)))
    db.commit()
    return row
