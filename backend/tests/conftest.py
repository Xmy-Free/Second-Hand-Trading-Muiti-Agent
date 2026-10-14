"""pytest 公共夹具。

- 每个用例独立的临时业务库 + 检查点库（复用 app.scenarios.runner.isolated_app）；
- 全局强制 RuleLLM 模式（llm_client._client=None），任何用例都不允许真实联网；
- app_client 走 with 上下文触发 FastAPI lifespan（建库/种子/Agent 注册/图编译）。
"""
from __future__ import annotations

import contextlib
import gc
import tempfile
from collections.abc import Callable
from pathlib import Path

import pytest

from app.llm.client import llm_client
from app.scenarios.runner import isolated_app


@pytest.fixture(autouse=True)
def _force_rule_mode(monkeypatch) -> None:
    """会话级兜底：测试前后都强制规则模式，且仅播种基础数据，防止故障注入伪客户端泄漏。"""
    monkeypatch.setenv("SEED_DEMO_DATA", "0")
    import app.core.config as cfg_mod

    monkeypatch.setattr(cfg_mod.settings, "seed_demo", False)
    llm_client._client = None
    yield
    llm_client._client = None


@pytest.fixture
def app_client():
    """函数级隔离应用：临时 SQLite + 临时检查点 + 强制 RuleLLM + 重置注册表/图。"""
    tmpdir = Path(tempfile.mkdtemp(prefix="mas_pytest_"))
    db_path = str(tmpdir / "test.db")
    cp_path = str(tmpdir / "checkpoints.db")
    client, _app = isolated_app(db_path, cp_path)
    try:
        with client:  # 触发 lifespan：init_db/run_seeds/bootstrap
            yield client
    finally:
            # 先释放引擎连接，再关检查点连接（Windows 文件锁）
            with contextlib.suppress(Exception):
                from app.core import database as db_mod

                db_mod.engine.dispose()
            with contextlib.suppress(Exception):
                import app.graph.checkpoint as cp_mod

                if cp_mod._conn is not None:
                    cp_mod._conn.close()
            gc.collect()
            for p in (db_path, cp_path):
                for suffix in ("", "-wal", "-shm"):
                    with contextlib.suppress(PermissionError):
                        Path(str(p) + suffix).unlink(missing_ok=True)


@pytest.fixture
def login_factory(app_client) -> Callable[[str], dict[str, str]]:
    """返回 (student_no, password='123456') -> 带 JWT 的请求头字典。"""

    def _login(student_no: str, password: str = "123456") -> dict[str, str]:
        resp = app_client.post(
            "/api/auth/login",
            json={"student_no": student_no, "password": password},
        )
        assert resp.status_code == 200, resp.text
        token = resp.json()["data"]["token"]
        return {"Authorization": f"Bearer {token}"}

    return _login
