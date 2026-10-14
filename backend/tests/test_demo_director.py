"""TR-3.1/3.2（AC-1/AC-2）：一键全自动演示导演。

- 演示节奏间隔 patch 为 0，用例快速完成；
- admin start 返回 running；运行中再次 start 返回 409；
- 轮询 status 至 completed，断言 8 阶段覆盖 publish/search/negotiate/pay/fulfill/review；
- completed 后库内真实新增：≥1 带图 on_sale 商品、≥1 frozen 商品（veto 支线）、
  ≥1 笔 paid/receiving/completed/reviewed 订单；
- 非管理员 start 返回 403；
- start 后立即 stop：幂等不抛 500，且不再产生新阶段。

导演是进程级 asyncio 单例：fixture 每个用例前重置锁/任务/状态机，
避免 TestClient 门户事件循环切换后 asyncio.Lock 绑定旧循环。
"""
from __future__ import annotations

import asyncio
import time

import pytest
from sqlmodel import Session, select

from app.core import database as db_mod
from app.models import Item, Order
from app.services.demo_director import director

POLL_INTERVAL = 0.2
DEMO_TIMEOUT = 60.0


@pytest.fixture
def reset_director(monkeypatch):
    """零节奏 + 单例复位（每个用例绑定到当前 app_client 的门户事件循环）。"""
    monkeypatch.setattr(director, "pace_min", 0.0, raising=False)
    monkeypatch.setattr(director, "pace_max", 0.0, raising=False)
    director._lock = asyncio.Lock()
    director._task = None
    director._stop_requested = False
    director.run_id = ""
    director.status = "idle"
    director.phase = ""
    director.phase_index = 0
    director.steps = []
    director.result = None
    director.message = ""
    yield director
    # 用例结束：若仍有运行任务，等待其走到终态，避免跨用例门户线程残留
    task = director._task
    if task is not None and not task.done():
        director._stop_requested = True
        deadline = time.monotonic() + 15.0
        while not task.done() and time.monotonic() < deadline:
            time.sleep(0.05)


def _poll_status(client, headers, *, expect: str, timeout: float = DEMO_TIMEOUT) -> dict:
    deadline = time.monotonic() + timeout
    data: dict = {}
    while time.monotonic() < deadline:
        resp = client.get("/api/console/demo/status", headers=headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        if data["status"] == expect:
            return data
        if expect != "completed" and data["status"] in ("error",):
            pytest.fail(f"演示进入 error 终态：{data.get('message')}")
        time.sleep(POLL_INTERVAL)
    pytest.fail(f"等待演示状态 {expect} 超时，最后状态：{data.get('status')} / {data.get('phase')}")


def _db_snapshot() -> tuple[set[int], set[int], set[int]]:
    with Session(db_mod.engine) as session:
        item_ids = {int(v) for v in session.exec(select(Item.id)).all()}
        on_sale_ids = {
            int(v) for v in session.exec(
                select(Item.id).where(Item.status == "on_sale")).all()
        }
        order_ids = {int(v) for v in session.exec(select(Order.id)).all()}
    return item_ids, on_sale_ids, order_ids


def test_demo_full_run_completed_with_real_data(
    app_client, login_factory, reset_director
) -> None:
    admin = login_factory("2400320321")

    before_items, _before_on_sale, before_orders = _db_snapshot()

    start = app_client.post("/api/console/demo/start", headers=admin)
    assert start.status_code == 200, start.text
    assert start.json()["data"]["status"] == "running"
    assert start.json()["data"]["run_id"]

    # AC-2：运行中再次启动 → 409，且不产生第二条流程
    again = app_client.post("/api/console/demo/start", headers=admin)
    assert again.status_code == 409, again.text

    final = _poll_status(app_client, admin, expect="completed")

    # AC-1：8 个阶段，覆盖发布/搜索/议价/支付/交付/评价关键阶段
    assert final["phase_count"] >= 8
    assert len(final["steps"]) >= final["phase_count"] * 2  # 每阶段 start+done
    blob = " ".join(
        f"{s.get('phase', '')} {s.get('label', '')}" for s in final["steps"]
    )
    for keyword in ("publish", "search", "negotiat", "pay", "fulfill", "review"):
        assert keyword in blob, f"演示阶段缺少关键阶段：{keyword}"
    # veto 支线：阶段与步骤摘要中必须出现违禁/freeze 语义
    assert "publish_banned" in [s.get("phase") for s in final["steps"]]
    assert final["result"] and final["result"].get("order_id")

    # TR-3.2：演示数据真实落库（相对演示前快照的增量）
    with Session(db_mod.engine) as session:
        on_sale_rows = session.exec(
            select(Item).where(Item.status == "on_sale")
        ).all()
        new_on_sale = [it for it in on_sale_rows if it.id not in before_items]
        assert len(new_on_sale) >= 1, "演示应新增至少 1 件带图在售商品"
        assert all(it.image_url for it in new_on_sale)

        new_frozen = session.exec(
            select(Item).where(Item.status == "frozen")
        ).all()
        new_frozen = [it for it in new_frozen if it.id not in before_items]
        assert len(new_frozen) >= 1, "veto 支线应新增至少 1 件 frozen 商品"

        new_orders = session.exec(select(Order)).all()
        new_orders = [o for o in new_orders if o.id not in before_orders]
        assert new_orders, "演示应产生真实订单"
        advanced = [o for o in new_orders
                    if o.status in ("paid", "receiving", "completed", "reviewed")]
        assert advanced, "演示订单应已支付/收货/完成/评价"
        assert final["result"]["order_id"] in {o.id for o in new_orders}


def test_demo_start_forbidden_for_non_admin(
    app_client, login_factory, reset_director
) -> None:
    student = login_factory("20240001")
    resp = app_client.post("/api/console/demo/start", headers=student)
    assert resp.status_code == 403, resp.text
    # 被拒后不得启动演示
    status = app_client.get(
        "/api/console/demo/status",
        headers=login_factory("2400320321"),
    ).json()["data"]
    assert status["status"] == "idle"


def test_demo_stop_is_idempotent_and_halts_phases(
    app_client, login_factory, reset_director
) -> None:
    admin = login_factory("2400320321")

    start = app_client.post("/api/console/demo/start", headers=admin)
    assert start.status_code == 200, start.text

    stop = app_client.post("/api/console/demo/stop", headers=admin)
    # AC-2：停止不报错（实际语义：恒返回 stopped，已完成时幂等不抛 500）
    assert stop.status_code == 200, stop.text
    assert stop.json()["data"]["status"] == "stopped"

    # 再次 stop 同样幂等
    stop_again = app_client.post("/api/console/demo/stop", headers=admin)
    assert stop_again.status_code == 200, stop_again.text

    # 等待后台任务真正走到终态（stopped 或在停止前刚好 completed）
    final = _poll_terminal(app_client, admin)
    assert final["status"] in ("stopped", "completed")

    steps_after = list(final["steps"])
    time.sleep(0.6)  # 给可能收尾的执行器线程一个窗口
    later = app_client.get("/api/console/demo/status", headers=admin).json()["data"]
    # 停止后不再产生新的阶段步骤（阶段数不增长）
    assert len(later["steps"]) == len(steps_after)
    assert later["status"] in ("stopped", "completed")


def _poll_terminal(client, headers, *, timeout: float = 20.0) -> dict:
    deadline = time.monotonic() + timeout
    last: dict = {}
    while time.monotonic() < deadline:
        data = client.get("/api/console/demo/status", headers=headers).json()["data"]
        last = data
        if data["status"] in ("stopped", "completed", "error") and (
            # stopped 可能在阶段执行中置位：等到出现"演示已停止"收尾步骤
            data["status"] != "stopped"
            or any(s.get("label") == "演示已停止" for s in data["steps"])
        ):
            return data
        time.sleep(0.1)
    return last
