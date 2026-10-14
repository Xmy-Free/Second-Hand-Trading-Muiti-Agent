"""TR-4.1/4.2/4.3（AC-7/AC-8）：完整播种（历史 + 真实演示流）数据覆盖核对。

本模块不用默认 light 夹具：自建 SEED_DEMO_DATA=1 的临时库，lifespan 内执行
run_seeds(light=False) + seed_demo_flows（RuleLLM 强制，无 Key 可跑）。
"""
from __future__ import annotations

import contextlib
import gc
import os
import re
import tempfile
from pathlib import Path

import pytest
from sqlmodel import Session, select

from app.core import database as db_mod
from app.models import Item, Negotiation, Order, User

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_PUBLIC = PROJECT_ROOT / "frontend" / "public"
EXPECTED_CATEGORIES = {
    "教材资料", "数码电子", "生活用品", "运动户外", "服饰鞋包", "美妆个护",
}
ALL_ORDER_STATUSES = {
    "unpaid", "paid", "receiving", "completed",
    "reviewed", "canceled", "refunded", "appealing",
}
IMAGE_URL_RE = re.compile(r"^/images/items/[\w.-]+\.jpg$")


@pytest.fixture(scope="module")
def full_seed_client():
    """完整播种的隔离应用（模块级一次，RuleLLM 模式）。"""
    import app.core.config as cfg_mod
    from app.llm.client import llm_client
    from app.scenarios.runner import isolated_app

    tmpdir = Path(tempfile.mkdtemp(prefix="mas_seedcov_"))
    db_path = str(tmpdir / "seed_full.db")
    cp_path = str(tmpdir / "checkpoints.db")

    old_env = os.environ.get("SEED_DEMO_DATA")
    old_flag = cfg_mod.settings.seed_demo

    client, _app = isolated_app(db_path, cp_path)
    # isolated_app 强制 light；进入 lifespan 前翻回完整播种
    os.environ["SEED_DEMO_DATA"] = "1"
    cfg_mod.settings.seed_demo = True
    llm_client._client = None
    try:
        with client:  # lifespan：init_db/run_seeds(light=False)/seed_demo_flows
            yield client
    finally:
        with contextlib.suppress(Exception):
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
        if old_env is None:
            os.environ.pop("SEED_DEMO_DATA", None)
        else:
            os.environ["SEED_DEMO_DATA"] = old_env
        cfg_mod.settings.seed_demo = old_flag
        llm_client._client = None


def _login(client, student_no: str) -> dict[str, str]:
    resp = client.post(
        "/api/auth/login",
        json={"student_no": student_no, "password": "123456"},
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['data']['token']}"}


def _user_id(session: Session, student_no: str) -> int:
    return int(session.exec(
        select(User).where(User.student_no == student_no)
    ).first().id)


# ---------------- TR-4.2 / AC-8：市场丰富且零无图 ----------------
def test_market_on_sale_rich_with_distinct_sellers_and_categories(
    full_seed_client,
) -> None:
    with Session(db_mod.engine) as session:
        on_sale = session.exec(
            select(Item).where(Item.status == "on_sale")
        ).all()

    assert len(on_sale) >= 30, f"在售商品应 ≥30，实际 {len(on_sale)}"
    sellers = {it.seller_id for it in on_sale}
    assert len(sellers) >= 6, f"在售卖家应 ≥6，实际 {len(sellers)}"
    categories = {it.category for it in on_sale}
    missing = EXPECTED_CATEGORIES - categories
    assert not missing, f"在售类目缺少：{missing}"

    assert all(it.image_url for it in on_sale), "存在 image_url 为空的在售商品"
    for it in on_sale:
        assert IMAGE_URL_RE.match(it.image_url), (
            f"商品 {it.id} image_url 形态非法：{it.image_url}"
        )
        f = FRONTEND_PUBLIC / it.image_url.lstrip("/")
        assert f.exists(), f"商品 {it.id} 图片文件不存在：{f}"


def test_search_agent_marks_ai_seller(full_seed_client) -> None:
    from app.kernel.registry import registry

    search_agent = registry.get("search")
    assert search_agent is not None, "完整播种后 9 Agent 应已注册"
    result = search_agent.do_search({"action": "search", "keyword": ""})
    views = result["items"]
    assert views, "搜索结果不应为空"
    ai_hits = [v for v in views if v.get("seller_is_ai") is True]
    assert ai_hits, "搜索结果中应存在 seller_is_ai=True 的 AI 商品"


# ---------------- TR-4.1 / AC-7：管理员与全账号数据丰满 ----------------
def test_admin_account_has_rich_orders_and_items(full_seed_client) -> None:
    headers = _login(full_seed_client, "2400320321")
    with Session(db_mod.engine) as session:
        admin_id = _user_id(session, "2400320321")
        orders = session.exec(select(Order)).all()
        admin_orders = [o for o in orders
                        if o.buyer_id == admin_id or o.seller_id == admin_id]
        admin_items = session.exec(
            select(Item).where(Item.seller_id == admin_id)
        ).all()
    assert len(admin_orders) >= 3, f"管理员参与订单应 ≥3，实际 {len(admin_orders)}"
    assert len(admin_items) >= 4, f"管理员名下商品应 ≥4，实际 {len(admin_items)}"

    # API 口径与库一致
    api_orders = full_seed_client.get("/api/orders", headers=headers)
    assert api_orders.status_code == 200, api_orders.text
    assert len(api_orders.json()["data"]) >= 3
    api_items = full_seed_client.get("/api/my/items", headers=headers)
    assert api_items.status_code == 200, api_items.text
    assert len(api_items.json()["data"]) >= 4


def test_every_common_student_account_has_data(full_seed_client) -> None:
    with Session(db_mod.engine) as session:
        orders = session.exec(select(Order)).all()
        items = session.exec(select(Item)).all()
        for no in ("20240001", "20240002", "20240003", "20240004", "20240005"):
            uid = _user_id(session, no)
            order_cnt = sum(
                1 for o in orders if o.buyer_id == uid or o.seller_id == uid
            )
            item_cnt = sum(1 for it in items if it.seller_id == uid)
            assert order_cnt + item_cnt >= 2, (
                f"账号 {no} 商品+订单仅 {item_cnt}+{order_cnt}，应 ≥2"
            )


# ---------------- TR-4.3：订单八种状态全库齐全 ----------------
def test_all_eight_order_statuses_present(full_seed_client) -> None:
    with Session(db_mod.engine) as session:
        statuses = set(session.exec(select(Order.status)).all())
    missing = ALL_ORDER_STATUSES - statuses
    assert not missing, f"订单状态缺少：{missing}（实际：{sorted(statuses)}）"


# ---------------- FR-206：AI 摊主在售供给 ----------------
def test_ai_seller_has_at_least_eight_on_sale(full_seed_client) -> None:
    with Session(db_mod.engine) as session:
        ai_id = _user_id(session, "AI10001")
        ai_on_sale = session.exec(
            select(Item).where(
                Item.seller_id == ai_id, Item.status == "on_sale"
            )
        ).all()
    assert len(ai_on_sale) >= 8, f"AI10001 在售应 ≥8，实际 {len(ai_on_sale)}"

    # 附带保证：完整播种议价列表非空（FR-302）
    with Session(db_mod.engine) as session:
        assert session.exec(select(Negotiation).limit(1)).first() is not None
