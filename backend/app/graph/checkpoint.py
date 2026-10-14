"""SQLite 检查点生命周期（与业务库分离，避免锁竞争）。"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver

_DB_PATH = Path(__file__).resolve().parents[2] / "checkpoints.db"
_saver: SqliteSaver | None = None
_conn: sqlite3.Connection | None = None


def init_checkpointer() -> SqliteSaver:
    global _saver, _conn
    if _saver is None:
        _conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
        _saver = SqliteSaver(_conn)
        _saver.setup()
    return _saver


def close_checkpointer() -> None:
    global _saver, _conn
    if _conn is not None:
        _conn.close()
    _saver = None
    _conn = None


def get_checkpointer() -> SqliteSaver:
    if _saver is None:
        init_checkpointer()
    return _saver
