"""PostgreSQL persistence (SQLAlchemy). The only data store of the service.

Tables: intake_session (short-lived), consent (durable proof), audit_event (append-only),
kim_outbox (pending hand-overs; content is wiped once sent).
"""
import time
from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy import JSON, BigInteger, DateTime, Float, Integer, String, Text, create_engine, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool

from config import settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class IntakeSessionRow(Base):
    __tablename__ = "intake_session"
    sub: Mapped[str] = mapped_column(String(128), primary_key=True)
    messages: Mapped[list] = mapped_column(JSON, default=list)
    triage_score: Mapped[str | None] = mapped_column(String(16), nullable=True)
    anamnesis_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    touched: Mapped[float] = mapped_column(Float, default=time.time, index=True)


class ConsentRow(Base):
    """One row per grant; never deleted. A revoke only sets `revoked_at`."""

    __tablename__ = "consent"
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    patient_id: Mapped[str] = mapped_column(String(128), index=True)
    scope: Mapped[str] = mapped_column(String(64), default="epa-medication,kis-appointment,kim-letter")
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    token_jti: Mapped[str | None] = mapped_column(String(128), nullable=True)


class AuditRow(Base):
    __tablename__ = "audit_event"
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    event: Mapped[str] = mapped_column(String(64), index=True)
    patient: Mapped[str] = mapped_column(String(32), index=True)  # pseudonym
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class KimOutboxRow(Base):
    __tablename__ = "kim_outbox"
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    patient_id: Mapped[str] = mapped_column(String(128), index=True)
    subject: Mapped[str] = mapped_column(String(256))
    body: Mapped[str | None] = mapped_column(Text, nullable=True)  # wiped after sending
    attachments: Mapped[list | None] = mapped_column(JSON, nullable=True)  # [[filename, text]]
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)  # pending|sent|failed
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


_engine = None
_factory: sessionmaker | None = None


def configure(url: str | None = None) -> None:
    """(Re)creates the engine. In-memory SQLite is only meant for tests."""
    global _engine, _factory
    url = url or settings.database_url
    if url.startswith("sqlite"):
        _engine = create_engine(url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    else:
        _engine = create_engine(url, pool_pre_ping=True)
    _factory = sessionmaker(_engine, expire_on_commit=False)


def init_db(retries: int = 30, delay_s: float = 2.0) -> None:
    """Waits for the database to accept connections (container start order).

    With DB_AUTO_CREATE=true (dev/tests) it also creates the schema. In production the schema is owned
    by Alembic; the service then only verifies that migrations were applied.
    """
    if _engine is None:
        configure()
    for attempt in range(retries):
        try:
            if settings.db_auto_create:
                Base.metadata.create_all(_engine)
            else:
                with _engine.connect() as conn:
                    conn.execute(select(1))
            return
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(delay_s)


@contextmanager
def db_session():
    """Transaction scope: commits on success, rolls back on any exception."""
    if _factory is None:
        configure()
    session: Session = _factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def lock_patient(session: Session, sub: str) -> None:
    """Serialises work per patient across backend instances (released at commit/rollback)."""
    if session.get_bind().dialect.name == "postgresql":
        session.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": sub})


def is_healthy() -> bool:
    try:
        with db_session() as s:
            s.execute(select(1))
        return True
    except Exception:
        return False
