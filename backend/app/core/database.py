"""SQLite 引擎（WAL）与会话依赖。单机演示，同步会话即可，不做并发优化。"""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings

engine = create_engine(
    settings.database_url,
    echo=False,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def _init_sqlite_pragmas(dbapi_conn, _record) -> None:  # noqa: ANN001
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


def init_db() -> None:
    import app.models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    _ensure_user_ai_columns()


def _ensure_user_ai_columns() -> None:
    """SQLite 零迁移：create_all 不补列，对既有 user 表幂等 ADD COLUMN（V5 FR-201）。"""
    from sqlalchemy import text

    alter_cols = (
        ("is_ai", "BOOLEAN NOT NULL DEFAULT 0"),
        ("ai_persona", "VARCHAR(128) NOT NULL DEFAULT ''"),
    )
    with engine.begin() as conn:
        cols = {row[1] for row in conn.execute(text("PRAGMA table_info(user)"))}
        if not cols:
            return  # 库中尚无 user 表（create_all 已按新结构建表）
        for name, ddl in alter_cols:
            if name not in cols:
                conn.execute(text(f"ALTER TABLE user ADD COLUMN {name} {ddl}"))


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
