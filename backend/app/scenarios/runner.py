"""冲突剧本基类：准备数据 → 驱动真实 API/服务 → 断言期望 → 输出对照表。

运行方式：
    cd backend
    .venv\\Scripts\\python.exe -m app.scenarios.run_all
剧本通过 TestClient 驱动完整 HTTP 链路（含 JWT、LangGraph 编排、ACL 消息），
与真实前端调用路径一致。每次运行使用独立临时数据库，互不污染。
"""
from __future__ import annotations

import contextlib
import os
import tempfile
import traceback
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CheckResult:
    name: str
    expect: str
    actual: str
    passed: bool


@dataclass
class ScenarioResult:
    code: str
    title: str
    passed: bool
    checks: list[CheckResult] = field(default_factory=list)
    error: str = ""
    expectation: str = ""

    def line(self) -> str:
        flag = "PASS" if self.passed else "FAIL"
        return f"[{flag}] {self.code} {self.title}（{sum(c.passed for c in self.checks)}/{len(self.checks)} 断言通过）"


def make_tmp_env() -> tuple[str, str]:
    """返回 (db_path, checkpointer_path)，并设置环境切换数据库。"""
    tmpdir = Path(tempfile.mkdtemp(prefix="mas_scenario_"))
    db_path = tmpdir / "scenario.db"
    cp_path = tmpdir / "checkpoints.db"
    return str(db_path), str(cp_path)


def isolated_app(db_path: str, cp_path: str):
    """构建一套指向临时库的隔离应用（重置 engine/checkpointer/注册表/图缓存）。"""
    os.environ["SEED_DEMO_DATA"] = "0"  # 剧本仅使用基础账号/商品
    os.environ.setdefault("DEEPSEEK_API_KEY", "")  # 默认无 Key 规则模式
    import app.core.config as _cfg

    _cfg.settings.seed_demo = False

    import sqlite3

    from sqlalchemy import event
    from sqlmodel import create_engine

    import app.core.config as cfg_mod
    from app.core import database as db_mod

    # 1) 重置业务引擎
    url = f"sqlite:///{db_path.replace(chr(92), '/')}"
    cfg_mod.settings.database_url = url
    with contextlib.suppress(Exception):
        db_mod.engine.dispose()
    new_engine = create_engine(url, echo=False, connect_args={"check_same_thread": False})

    @event.listens_for(new_engine, "connect")
    def _pragmas(dbapi_conn, _record):  # noqa: ANN001
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA busy_timeout=5000")
        cur.close()

    db_mod.engine = new_engine

    # 1b) 所有以 `from app.core.database import engine` 持引用的模块统一重绑
    import importlib

    for mod_name in (
        "app.agents.coordinator",
        "app.agents.user_agent",
        "app.agents.commodity",
        "app.agents.moderation",
        "app.agents.search",
        "app.agents.negotiation",
        "app.agents.order",
        "app.agents.credit",
        "app.agents.arbitrator",
        "app.graph.flows.appeal_flow",
        "app.graph.flows.publish_flow",
        "app.graph.flows.trade_flow",
        "app.kernel.observe",
        "app.kernel.post",
        "app.kernel.registry",
        "app.services.flow_index",
        "app.services.order_service",
        "app.api.routes_console",
        "app.seeds.seed",
    ):
        try:
            mod = importlib.import_module(mod_name)
            if hasattr(mod, "engine"):
                mod.engine = new_engine
        except ImportError:
            continue

    # 2) 重置检查点
    import app.graph.checkpoint as cp_mod

    if cp_mod._conn is not None:
        with contextlib.suppress(Exception):
            cp_mod._conn.close()
    from langgraph.checkpoint.sqlite import SqliteSaver

    conn = sqlite3.connect(cp_path, check_same_thread=False)
    cp_mod._conn = conn
    cp_mod._saver = SqliteSaver(conn)
    cp_mod._saver.setup()

    # 3) 强制 RuleLLM 规则模式（剧本不依赖外部 API）
    import app.llm.client as llm_mod

    llm_mod.llm_client._client = None

    # 4) 重置 Agent 注册表与流程图缓存（lifespan 会重新注册/编译）
    from app.graph.runner import runner
    from app.kernel.registry import registry

    registry._agents.clear()
    runner._graphs.clear()
    runner._thread_flow.clear()

    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    return client, app


class Scenario:
    code: str = "C?"
    title: str = ""
    expectation: str = ""  # 通过条件（run_all 汇总表展示）

    def run(self, client) -> list[CheckResult]:
        raise NotImplementedError

    def check(self, name: str, expect: str, actual, passed: bool) -> CheckResult:
        return CheckResult(name=name, expect=expect, actual=str(actual), passed=bool(passed))

    def login(self, client, student_no: str, password: str = "123456") -> dict:
        r = client.post("/api/auth/login", json={"student_no": student_no, "password": password})
        token = r.json()["data"]["token"]
        return {"Authorization": f"Bearer {token}"}

    def execute(self) -> ScenarioResult:
        result = ScenarioResult(code=self.code, title=self.title, passed=False,
                                expectation=self.expectation)
        db_path, cp_path = make_tmp_env()
        try:
            client, _app = isolated_app(db_path, cp_path)
            with client:
                result.checks = self.run(client)
            result.passed = all(c.passed for c in result.checks) and bool(result.checks)
        except Exception as exc:  # noqa: BLE001
            result.error = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()[:600]}"
        finally:
            # 先释放连接再删临时库（Windows 文件锁）
            with contextlib.suppress(Exception):
                from app.core import database as _db

                _db.engine.dispose()
            with contextlib.suppress(Exception):
                import app.graph.checkpoint as _cp

                if _cp._conn is not None:
                    _cp._conn.close()
            import gc

            gc.collect()
            for p in (db_path, cp_path):
                for suffix in ("", "-wal", "-shm"):
                    with contextlib.suppress(PermissionError):
                        Path(str(p) + suffix).unlink(missing_ok=True)
        return result
