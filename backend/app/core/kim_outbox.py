"""Transactional outbox for KIM letters.

The letter is stored first, then sent. If the KIM client module is down the row stays `pending` and
the retry worker delivers it later. Once sent, the medical content is wiped from the row.
"""
import smtplib

from sqlalchemy import select

from app.core.audit import audit
from app.core.db import KimOutboxRow, db_session, utcnow
from app.core.kim_client import send_kim_message
from config import settings

_SEND_ERRORS = (OSError, smtplib.SMTPException)


def _attempt(row: KimOutboxRow) -> bool:
    """Tries to send one row in place; the caller commits."""
    row.attempts += 1
    attachments = [(name, text.encode()) for name, text in (row.attachments or [])]
    try:
        send_kim_message(row.subject, row.body or "", attachments=attachments)
    except _SEND_ERRORS as exc:
        row.last_error = type(exc).__name__
        row.status = "failed" if row.attempts >= settings.kim_max_attempts else "pending"
        audit("kim_failed", row.patient_id, error=row.last_error, attempt=row.attempts, status=row.status)
        return False
    row.status, row.sent_at, row.last_error = "sent", utcnow(), None
    row.body, row.attachments = None, None
    audit("kim_sent", row.patient_id, outbox_id=row.id, attempt=row.attempts)
    return True


def enqueue_and_send(patient_id: str, subject: str, body: str, attachments: list[tuple[str, str]]) -> bool:
    """Stores the letter, tries to send immediately. Returns whether it was delivered."""
    with db_session() as db:
        row = KimOutboxRow(patient_id=patient_id, subject=subject, body=body, attachments=attachments)
        db.add(row)
        db.flush()
        return _attempt(row)


def retry_pending() -> int:
    """Re-sends pending letters. Returns the number delivered."""
    from app.core.session import store

    delivered = []
    with db_session() as db:
        rows = db.scalars(
            select(KimOutboxRow).where(KimOutboxRow.status == "pending").order_by(KimOutboxRow.id).limit(50)
        ).all()
        for row in rows:
            if _attempt(row):
                delivered.append(row.patient_id)
    for patient_id in delivered:
        store.mark_kim_sent(patient_id)
    return len(delivered)
