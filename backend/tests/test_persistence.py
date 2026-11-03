from app.core import kim_outbox
from app.core.db import AuditRow, ConsentRow, IntakeSessionRow, KimOutboxRow, db_session
from app.core.audit import audit
from app.core.session import store


def test_session_survives_new_request():
    with store.locked("u1") as s:
        s.messages.append("Husten")
        s.triage_score = "Gelb"
    with store.locked("u1") as s:
        assert s.messages == ["Husten"] and s.triage_score == "Gelb"


def test_exception_rolls_back():
    try:
        with store.locked("u1") as s:
            s.messages.append("x")
            raise RuntimeError
    except RuntimeError:
        pass
    with store.locked("u1") as s:
        assert s.messages == []


def test_consent_is_stored_and_revoked_on_reset():
    with store.locked("u1") as s:
        s.triage_score = "Gelb"
        s.grant("jti-1")
    with db_session() as d:
        row = d.query(ConsentRow).one()
        assert row.token_jti == "jti-1" and row.revoked_at is None
    store.reset("u1")
    with db_session() as d:
        assert d.query(ConsentRow).one().revoked_at is not None
        assert d.get(IntakeSessionRow, "u1") is None


def test_audit_row_is_pseudonymised():
    audit("chat_message", "real-subject", count=1)
    with db_session() as d:
        row = d.query(AuditRow).one()
        assert "real-subject" not in str(row.patient)


def test_outbox_retry_sends_and_wipes_content(monkeypatch):
    def down(*a, **k):
        raise ConnectionRefusedError()

    monkeypatch.setattr("app.core.kim_outbox.send_kim_message", down)
    assert kim_outbox.enqueue_and_send("p1", "Betreff", "Brieftext", [("t.json", "{}")]) is False
    with db_session() as d:
        assert d.query(KimOutboxRow).one().status == "pending"

    monkeypatch.setattr("app.core.kim_outbox.send_kim_message", lambda *a, **k: None)
    kim_outbox.retry_pending()
    with db_session() as d:
        row = d.query(KimOutboxRow).one()
        assert row.status == "sent" and not row.body


def test_purge_expired_drops_idle_sessions():
    with store.locked("u1") as s:
        s.messages.append("x")
    with db_session() as d:
        d.get(IntakeSessionRow, "u1").touched = 1.0
    store.purge_expired()
    with db_session() as d:
        assert d.get(IntakeSessionRow, "u1") is None
