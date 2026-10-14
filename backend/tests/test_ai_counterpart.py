"""TR-1.2/2.2/2.3（AC-4/AC-5/AC-6 规则路径）：AI 虚拟用户拟人回复与策略出价。

- 纯函数单测：rule_llm.next_ai_price 买卖双方序列单调、不越保留价、交集应价成交；
- rule_llm.chat_reply 结构合法（非空、不泄漏 system/prompt/JSON 痕迹）；
- llm_client.chat_text 无 client 时返回 None；
- 端到端（app_client + RuleLLM 路径）：AI10002 买家对 AI10001 卖家在售商品议价，
  发文本消息 → AI 卖家聊天回复落库（from_is_ai=True）；
  多轮让步驱动至成交 → Negotiation.status == "deal" 且真实建单，
  库内 Offer 验证 AI 出价严格单调、守住保留价、末拍等于买家最新价。
"""
from __future__ import annotations

import time

import pytest
from sqlmodel import Session, select

from app.core import database as db_mod
from app.llm import rule_llm
from app.llm.client import llm_client
from app.models import Item, Negotiation, NegotiationMessage, Offer, Order, User
from app.services import ai_chat

BR, SR, NASH = 60.0, 51.0, 55.5


# ---------------------------------------------------------------------------
# TR-1.2：next_ai_price 纯函数序列性质
# ---------------------------------------------------------------------------
def test_next_ai_price_buyer_strictly_increasing_within_reserve() -> None:
    # 卖家坚持要价 62（高于买家保留价，无法成交），买家连续 5 轮向纳什价收敛
    prices: list[float] = []
    lb: float | None = None
    for round_no in range(1, 6):
        p = rule_llm.next_ai_price(
            "buyer", BR, SR, NASH, lb, 62.0, round_no, 5
        )
        if p is not None:
            prices.append(p)
            lb = p
    assert len(prices) >= 3
    assert all(b < a for b, a in zip(prices, prices[1:])), "买家出价必须严格递增"
    assert all(p <= BR for p in prices), "买家出价不得越过买家保留价"
    assert prices[-1] == pytest.approx(min(NASH, BR), abs=0.05)


def test_next_ai_price_seller_strictly_decreasing_within_reserve() -> None:
    # 买家坚持出价 45（低于卖家保留价，无法成交），卖家连续 5 轮向纳什价收敛
    prices: list[float] = []
    ls: float | None = None
    for round_no in range(1, 6):
        p = rule_llm.next_ai_price(
            "seller", BR, SR, NASH, 45.0, ls, round_no, 5
        )
        if p is not None:
            prices.append(p)
            ls = p
    assert len(prices) >= 3
    assert all(a > b for a, b in zip(prices, prices[1:])), "卖家要价必须严格递减"
    assert all(p >= SR for p in prices), "卖家要价不得低于卖家保留价"
    assert prices[-1] == pytest.approx(max(NASH, SR), abs=0.05)


def test_next_ai_price_crosses_at_counterpart_latest_price() -> None:
    # 交互式模拟：买家 40 开盘 → 双方让步 → 交集时返回对方最新价（可成交）
    lb, ls = 40.0, None
    buyer_seq, seller_seq = [40.0], []
    deal_price: float | None = None
    for turn in range(1, 8):
        if turn % 2 == 0:
            # 买家回合（已出 1 价，round_count 跟随其出价数 +1）
            r = len(buyer_seq) + 1
            p = rule_llm.next_ai_price("buyer", BR, SR, NASH, lb, ls, r, 5)
            if p is None:
                continue
            buyer_seq.append(p)
            lb = p
        else:
            r = len(seller_seq) + 1
            p = rule_llm.next_ai_price("seller", BR, SR, NASH, lb, ls, r, 5)
            if p is None:
                continue
            seller_seq.append(p)
            ls = p
        # 成交判定：回到己方价格越过对方要价/出价
        if ls is not None and lb >= ls:
            deal_price = ls
            break
        if ls is not None and ls <= lb:
            deal_price = lb
            break
    assert deal_price is not None, "区间内应能成交"
    assert deal_price == pytest.approx(seller_seq[-1], abs=0.05)
    assert deal_price <= BR and deal_price >= SR
    assert all(b < a for b, a in zip(buyer_seq, buyer_seq[1:]))
    assert all(a > b for a, b in zip(seller_seq, seller_seq[1:]))


# ---------------------------------------------------------------------------
# TR-1.2：chat_reply 结构合法 + chat_text 无 client 返回 None
# ---------------------------------------------------------------------------
def test_chat_reply_is_clean_human_like_text() -> None:
    neg_info = {"nash_price": NASH, "buyer_reserve": BR, "seller_reserve": SR,
                "round_count": 2}
    text = rule_llm.chat_reply("seller", "罗技无线鼠标", neg_info, "45 卖吗", 45.0, None)
    assert isinstance(text, str) and text.strip()
    assert "{" not in text and "}" not in text, "规则回复不得夹带 JSON"
    lowered = text.lower()
    assert "system" not in lowered and "prompt" not in lowered, "不得泄漏系统提示痕迹"


def test_chat_text_returns_none_without_client(monkeypatch) -> None:
    monkeypatch.setattr(llm_client, "_client", None)
    assert llm_client.chat_text("system prompt", "user prompt") is None


# ---------------------------------------------------------------------------
# TR-2.2/2.3：端到端规则路径
# ---------------------------------------------------------------------------
@pytest.fixture
def rule_ai_env(monkeypatch):
    """强制 RuleLLM 文本路径 + 打字延时归零（AI 后台线程仍真实出价/落库）。"""
    monkeypatch.setattr(llm_client, "_client", None)
    monkeypatch.setattr(llm_client, "chat_text", lambda *a, **k: None)
    monkeypatch.setattr(ai_chat, "TYPING_MIN", 0.0)
    monkeypatch.setattr(ai_chat, "TYPING_MAX", 0.0)


def _wait_until(predicate, timeout: float = 10.0, interval: float = 0.1):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        last = predicate()
        if last:
            return last
        time.sleep(interval)
    pytest.fail(f"条件在 {timeout}s 内未满足（最后值：{last!r}）")


def _ai_seller_item_id() -> int:
    """选 AI10001 名下最贵在售商品（显示器 ¥450，保留价 382.5），保证多轮让步空间。"""
    with Session(db_mod.engine) as session:
        seller = session.exec(
            select(User).where(User.student_no == "AI10001")
        ).first()
        item = session.exec(
            select(Item).where(
                Item.seller_id == seller.id, Item.status == "on_sale"
            ).order_by(Item.price.desc())
        ).first()
        assert item is not None, "轻量播种应包含 AI10001 的在售商品"
        assert item.price >= 440, f"测试前置：需要高价商品支撑多轮议价，实际 {item.price}"
        return int(item.id)


def test_ai_chat_reply_persisted_and_negotiation_deals_with_order(
    app_client, login_factory, rule_ai_env
) -> None:
    buyer_headers = login_factory("AI10002")
    item_id = _ai_seller_item_id()

    # 买保留价 420 / 首价 350：首价低于卖家保留价（标价 *0.85），AI 不会秒接受，
    # 从而真实展开多轮让步。
    start = app_client.post(
        "/api/negotiations",
        headers=buyer_headers,
        json={"item_id": item_id, "buyer_reserve": 420, "first_offer": 350},
    )
    assert start.status_code == 200, start.text
    neg_view = start.json()["data"]
    neg_id = int(neg_view["id"])

    # AC-4：发送一条文本消息 → 轮询 until AI 回复落库
    sent = app_client.post(
        f"/api/negotiations/{neg_id}/messages",
        headers=buyer_headers,
        json={"content": "学长好，这个我诚心想要，学生党预算有限能便宜点不？"},
    )
    assert sent.status_code == 200, sent.text

    def _ai_chat_msg():
        with Session(db_mod.engine) as session:
            rows = session.exec(
                select(NegotiationMessage).where(
                    NegotiationMessage.negotiation_id == neg_id,
                    NegotiationMessage.kind == "chat",
                )
            ).all()
            ai = session.exec(
                select(User).where(User.student_no == "AI10001")
            ).first()
            ai_rows = [m for m in rows if m.from_user_id == ai.id and m.content.strip()]
            return ai_rows[0] if ai_rows else None

    ai_msg = _wait_until(_ai_chat_msg)
    assert ai_msg.content.strip()

    # REST 拉取也必须能看到 AI 消息且字段齐备
    listing = app_client.get(
        f"/api/negotiations/{neg_id}/messages", headers=buyer_headers
    ).json()["data"]
    ai_views = [m for m in listing if m["from_is_ai"] is True]
    assert ai_views, "GET messages 应包含 from_is_ai=True 的 AI 回复"
    view = ai_views[0]
    for field in ("id", "from_user_id", "from_nickname", "from_is_ai",
                  "kind", "created_at"):
        assert field in view

    # AC-5：多轮驱动买家让步，每轮等 AI 卖家真实出价落库后再推进
    def _seller_offer_count() -> int:
        with Session(db_mod.engine) as session:
            return len(session.exec(
                select(Offer).where(
                    Offer.negotiation_id == neg_id, Offer.from_role == "seller"
                )
            ).all())

    def _neg_status() -> str:
        with Session(db_mod.engine) as session:
            return session.get(Negotiation, neg_id).status

    for price in (360.0, 370.0, 380.0):
        seen = _seller_offer_count()
        resp = app_client.post(
            f"/api/negotiations/{neg_id}/offers",
            headers=buyer_headers,
            json={"price": price, "confirm": True},
        )
        assert resp.status_code == 200, resp.text
        _wait_until(lambda: _seller_offer_count() > seen)

    # 最后一拍：买家加价越过卖家最新要价（达卖家保留价即被 AI 应价成交）
    with Session(db_mod.engine) as session:
        neg = session.get(Negotiation, neg_id)
        sr = float(neg.seller_reserve)
        last_seller = min(
            (o.price for o in session.exec(
                select(Offer).where(
                    Offer.negotiation_id == neg_id, Offer.from_role == "seller"
                )).all()),
            default=None,
        )
    assert last_seller is not None
    deal_bid = round(max(sr, last_seller - 1.0), 1)  # 命中"达到保留价即应价"分支
    # 若上一拍 AI 已经应价成交则无需再出价
    with Session(db_mod.engine) as session:
        still_ongoing = session.get(Negotiation, neg_id).status == "ongoing"
    if still_ongoing:
        seen = _seller_offer_count()
        resp = app_client.post(
            f"/api/negotiations/{neg_id}/offers",
            headers=buyer_headers,
            json={"price": deal_bid, "confirm": True},
        )
        assert resp.status_code == 200, resp.text
        _wait_until(lambda: _seller_offer_count() > seen
                    or _neg_status() == "deal")

    # 终态：deal + 真实订单
    _wait_until(lambda: _neg_status() == "deal")
    assert _neg_status() == "deal"

    with Session(db_mod.engine) as session:
        neg = session.get(Negotiation, neg_id)
        seller_offers = session.exec(
            select(Offer).where(
                Offer.negotiation_id == neg_id, Offer.from_role == "seller"
            ).order_by(Offer.id)
        ).all()
        buyer_offers = session.exec(
            select(Offer).where(
                Offer.negotiation_id == neg_id, Offer.from_role == "buyer"
            ).order_by(Offer.id)
        ).all()
        order = session.exec(
            select(Order).where(Order.negotiation_id == neg_id)
        ).first()

        prices = [float(o.price) for o in seller_offers]
        assert len(prices) >= 2, "AI 卖家至少应有两次策略出价"
        assert all(a > b for a, b in zip(prices, prices[1:])), \
            "AI 卖家出价必须严格单调递减"
        assert all(p >= neg.seller_reserve for p in prices), \
            "AI 卖家出价不得低于保留价"
        assert all(float(o.price) <= neg.buyer_reserve for o in buyer_offers)
        # 成交末拍等于买家最新出价
        assert prices[-1] == pytest.approx(float(neg.deal_price), abs=0.05)
        assert prices[-1] == pytest.approx(
            max(float(o.price) for o in buyer_offers), abs=0.05
        )

        assert order is not None, "AI 议价成交后必须真实建单"
        assert order.status == "unpaid"
        assert order.deal_price == pytest.approx(float(neg.deal_price), abs=0.05)
