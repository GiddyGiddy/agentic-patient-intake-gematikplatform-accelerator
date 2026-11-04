"""The Alembic migrations must produce exactly the schema the models describe."""
import sqlalchemy as sa
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext

from app.core.db import Base


def _config(url: str) -> Config:
    cfg = Config("alembic.ini")
    cfg.cmd_opts = type("O", (), {"x": [f"url={url}"]})()
    return cfg


def test_upgrade_head_matches_models_and_downgrades(tmp_path):
    url = f"sqlite:///{tmp_path / 'mig.db'}"
    cfg = _config(url)

    command.upgrade(cfg, "head")
    engine = sa.create_engine(url)
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == [], f"models and migrations differ: {diff}"
    assert set(sa.inspect(engine).get_table_names()) >= {"intake_session", "consent", "audit_event", "kim_outbox"}

    command.downgrade(cfg, "base")
    assert set(sa.inspect(engine).get_table_names()) <= {"alembic_version"}


def test_single_migration_head():
    from alembic.script import ScriptDirectory

    heads = ScriptDirectory.from_config(Config("alembic.ini")).get_heads()
    assert len(heads) == 1
