"""Audit trail for TI-relevant actions. One JSON line per event; never contains medical content.

The patient id is pseudonymised (SHA-256 prefix) so logs can be correlated without exposing the KVNR.
"""
import hashlib
import json
import logging
import sys
from datetime import datetime, timezone

from app.core.db import AuditRow, db_session
from config import settings

_logger = logging.getLogger("audit")
_logger.setLevel(logging.INFO)
_logger.propagate = False


def _ensure_handlers() -> None:
    if _logger.handlers:
        return
    fmt = logging.Formatter("%(message)s")
    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(fmt)
    _logger.addHandler(stream)
    if settings.audit_log_file:
        file = logging.FileHandler(settings.audit_log_file, encoding="utf-8")
        file.setFormatter(fmt)
        _logger.addHandler(file)


def pseudonym(patient_id: str) -> str:
    return hashlib.sha256(patient_id.encode()).hexdigest()[:16]


def audit(event: str, patient_id: str, **details) -> None:
    _ensure_handlers()
    pseud = pseudonym(patient_id)
    _logger.info(
        json.dumps(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "event": event,
                "patient": pseud,
                **details,
            },
            ensure_ascii=False,
        )
    )
    # durable copy; a database problem must not break the patient flow, the stdout line remains
    try:
        with db_session() as db:
            db.add(AuditRow(event=event, patient=pseud, details=details))
    except Exception:
        _logger.error(json.dumps({"event": "audit_db_write_failed", "audited_event": event}))
