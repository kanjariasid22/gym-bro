"""SQLAlchemy engine and session helpers."""

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def _make_engine():
    settings = get_settings()
    sqlite_path = settings.resolve_sqlite_path()
    if sqlite_path is not None:
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)

    connect_args = {}
    if settings.database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    engine = create_engine(
        settings.database_url,
        connect_args=connect_args,
    )

    if settings.database_url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_conn, _connection_record):  # noqa: ANN001
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _sqlite_columns(table: str) -> set[str]:
    with engine.connect() as conn:
        rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return {r[1] for r in rows}


def _migrate_sqlite() -> None:
    """Add program status / session override columns; backfill one active per user."""
    if not get_settings().database_url.startswith("sqlite"):
        return

    with engine.begin() as conn:
        tables = {
            r[0]
            for r in conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            ).fetchall()
        }
        if "programs" not in tables:
            return

        prog_cols = {r[1] for r in conn.execute(text("PRAGMA table_info(programs)")).fetchall()}
        if "status" not in prog_cols:
            conn.execute(
                text("ALTER TABLE programs ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'active'")
            )
        if "archived_at" not in prog_cols:
            conn.execute(text("ALTER TABLE programs ADD COLUMN archived_at DATETIME"))

        if "workout_sessions" in tables:
            sess_cols = {
                r[1] for r in conn.execute(text("PRAGMA table_info(workout_sessions)")).fetchall()
            }
            if "plan_overrides_json" not in sess_cols:
                conn.execute(
                    text("ALTER TABLE workout_sessions ADD COLUMN plan_overrides_json TEXT")
                )

        # Ensure at most one active program per user (keep newest created_at)
        users = conn.execute(text("SELECT DISTINCT user_id FROM programs")).fetchall()
        for (user_id,) in users:
            rows = conn.execute(
                text(
                    "SELECT id FROM programs WHERE user_id=:uid ORDER BY created_at DESC, id DESC"
                ),
                {"uid": user_id},
            ).fetchall()
            if not rows:
                continue
            keep_id = rows[0][0]
            conn.execute(
                text("UPDATE programs SET status='active', archived_at=NULL WHERE id=:id"),
                {"id": keep_id},
            )
            for (pid,) in rows[1:]:
                conn.execute(
                    text(
                        "UPDATE programs SET status='archived', "
                        "archived_at=COALESCE(archived_at, CURRENT_TIMESTAMP) WHERE id=:id"
                    ),
                    {"id": pid},
                )


def init_db() -> None:
    """Create tables from models (simple schema bootstrap for v1)."""
    from app import models  # noqa: F401

    Path(get_settings().memory_data_dir).mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    _migrate_sqlite()
