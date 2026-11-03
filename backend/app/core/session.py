"""Intake sessions and consent, persisted in PostgreSQL.

`store.locked(sub)` is a per-patient critical section (advisory lock + transaction):
 - changes are committed when the block ends normally,
 - an exception (e.g. a TI outage -> HTTP 502) rolls everything back, so a retry starts clean,
 - several backend instances can run side by side.
Consent is kept in its own durable table; a session reset or timeout revokes it.
"""
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select, update

from app.core.db import ConsentRow, IntakeSessionRow, db_session, lock_patient
from config import settings


@dataclass
class IntakeSession:
    sub: str
    messages: list[str] = field(default_factory=list)
    triage_score: str | None = None
    anamnesis_summary: str | None = None
    result: dict = field(default_factory=dict)  # appointment / ePA / KIM outcome
    consent_until: float = 0.0  # epoch seconds of the active consent; 0 = none
    _grant_jti: str | None = field(default=None, repr=False)
    _granted: bool = field(default=False, repr=False)
    _revoked: bool = field(default=False, repr=False)

    @property
    def consent_active(self) -> bool:
        return self.consent_until > time.time()

    @property
    def completed(self) -> bool:
        return bool(self.result.get("appointment_id"))

    def grant(self, token_jti: str | None = None) -> None:
        self.consent_until = time.time() + settings.consent_ttl_s
        self._granted, self._revoked, self._grant_jti = True, False, token_jti

    def revoke(self) -> None:
        self.consent_until = 0.0
        self._revoked, self._granted = True, False


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _revoke_active(db, sub: str) -> None:
    db.execute(
        update(ConsentRow)
        .where(ConsentRow.patient_id == sub, ConsentRow.revoked_at.is_(None))
        .values(revoked_at=_now())
    )


def _active_consent_until(db, sub: str) -> float:
    exp = db.scalar(
        select(ConsentRow.expires_at)
        .where(ConsentRow.patient_id == sub, ConsentRow.revoked_at.is_(None))
        .order_by(ConsentRow.expires_at.desc())
        .limit(1)
    )
    if exp is None:
        return 0.0
    if exp.tzinfo is None:  # SQLite returns naive timestamps
        exp = exp.replace(tzinfo=timezone.utc)
    return exp.timestamp()


class SessionStore:
    def __init__(self) -> None:
        self._hits: dict[str, list[float]] = {}
        self._hits_lock = threading.Lock()

    @contextmanager
    def locked(self, sub: str):
        with db_session() as db:
            lock_patient(db, sub)
            row = db.get(IntakeSessionRow, sub)
            now = time.time()
            if row is not None and now - row.touched > settings.session_ttl_s:
                # idle session expired: drop it together with its consent
                _revoke_active(db, sub)
                db.delete(row)
                db.flush()
                row = None
            session = IntakeSession(sub=sub)
            if row is not None:
                session.messages = list(row.messages or [])
                session.triage_score = row.triage_score
                session.anamnesis_summary = row.anamnesis_summary
                session.result = dict(row.result or {})
                session.consent_until = _active_consent_until(db, sub)

            yield session

            if session._revoked:
                _revoke_active(db, sub)
            if session._granted:
                db.add(
                    ConsentRow(
                        patient_id=sub,
                        expires_at=_now() + timedelta(seconds=settings.consent_ttl_s),
                        token_jti=session._grant_jti,
                    )
                )
            if row is None:
                row = IntakeSessionRow(sub=sub)
                db.add(row)
            row.messages = list(session.messages)
            row.triage_score = session.triage_score
            row.anamnesis_summary = session.anamnesis_summary
            row.result = dict(session.result)
            row.touched = now

    def reset(self, sub: str) -> None:
        with db_session() as db:
            lock_patient(db, sub)
            _revoke_active(db, sub)
            db.execute(delete(IntakeSessionRow).where(IntakeSessionRow.sub == sub))

    def purge_expired(self) -> int:
        """Housekeeping: removes idle sessions (and revokes their consent). Returns the count."""
        cutoff = time.time() - settings.session_ttl_s
        with db_session() as db:
            subs = list(db.scalars(select(IntakeSessionRow.sub).where(IntakeSessionRow.touched < cutoff)))
            for sub in subs:
                _revoke_active(db, sub)
            if subs:
                db.execute(delete(IntakeSessionRow).where(IntakeSessionRow.sub.in_(subs)))
            return len(subs)

    def mark_kim_sent(self, sub: str) -> None:
        """Called when a queued KIM letter is delivered later by the retry worker."""
        with db_session() as db:
            lock_patient(db, sub)
            row = db.get(IntakeSessionRow, sub)
            if row is not None:
                row.result = {**(row.result or {}), "kim_sent": True}

    def rate_limited(self, sub: str) -> bool:
        # per instance; a shared limiter belongs at the gateway/reverse proxy
        with self._hits_lock:
            now = time.time()
            hits = [t for t in self._hits.get(sub, []) if now - t < 60]
            limited = len(hits) >= settings.rate_limit_per_min
            if not limited:
                hits.append(now)
            self._hits[sub] = hits
            return limited


store = SessionStore()
