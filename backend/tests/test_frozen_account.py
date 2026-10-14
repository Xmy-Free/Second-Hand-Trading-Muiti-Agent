"""FR-1 冻结账号「禁止交易但可申诉」：

- 允许：登录、浏览市场（GET /api/market/items）、对自己参与的 paid/receiving 订单发起申诉；
- 禁止：发布商品、发起议价、支付订单——一律 403 且错误文案包含「冻结」。

冻结账号无法走正常交易入口造单，故 paid/unpaid 订单直接以 SQLModel 落库构造，
模拟其账号被冻结前已经成交的真实订单。
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlmodel import Session, select

from app.core import database
from app.models import Item, Negotiation, Order, User

FROZEN_NO = "20240008"
SELLER_NO = "20240002"


def _seed_participating_orders() -> tuple[int, int]:
    """构造冻结买家参与的一笔 paid（item 4，160 元）与一笔 unpaid（item 3，11 元）订单。"""
    with Session(database.engine) as session:
        buyer = session.exec(select(User).where(User.student_no == FROZEN_NO)).first()
        seller = session.exec(select(User).where(User.student_no == SELLER_NO)).first()
        assert buyer is not None and seller is not None
        assert buyer.status == "frozen", "种子中的 20240008 必须是冻结账号"
        now = datetime.utcnow()

        def _make(item_id: int, price: float, status: str) -> int:
            item = session.get(Item, item_id)
            assert item is not None and item.seller_id == seller.id
            neg = Negotiation(
                item_id=item.id, buyer_id=buyer.id, seller_id=seller.id,
                buyer_reserve=round(price * 1.1, 1), seller_reserve=round(price * 0.9, 1),
                nash_price=price, max_rounds=5, deadline_seconds=120,
                status="deal", deal_price=price,
                created_at=now - timedelta(hours=2), closed_at=now - timedelta(hours=1),
            )
            session.add(neg)
            session.flush()
            item.status = "locked"  # 成交建单预占锁
            order = Order(
                order_no=f"TEST-FROZEN-{item.id}-{status}",
                item_id=item.id, negotiation_id=neg.id,
                buyer_id=buyer.id, seller_id=seller.id,
                deal_price=price, status=status,
                pay_deadline=None if status == "canceled" else now + timedelta(minutes=15),
                created_at=now - timedelta(hours=1), updated_at=now,
            )
            session.add(order)
            session.flush()
            return order.id

        # item 4：索尼耳机（卖家 20240002），paid 且 160 > 直裁阈值 50 → 申诉挂人工门
        paid_id = _make(4, 160.0, "paid")
        # item 3：线代辅导讲义（卖家 20240002），unpaid，用于验证支付拦截
        unpaid_id = _make(3, 11.0, "unpaid")
        session.commit()
        return paid_id, unpaid_id


def test_frozen_account_can_login_browse_appeal_but_cannot_trade(app_client, login_factory) -> None:
    # ① 冻结账号可以登录
    frozen = login_factory(FROZEN_NO)

    # 可以浏览市场（搜索推荐 Agent 对冻结账号照常服务）
    market = app_client.get("/api/market/items", headers=frozen)
    assert market.status_code == 200, market.text
    assert len(market.json()["data"]["items"]) >= 15

    paid_order_id, unpaid_order_id = _seed_participating_orders()

    # 可以对自己参与的 paid 订单发起申诉（160 元超直裁阈值，流程挂纠纷终裁人工门）
    appeal = app_client.post(
        "/api/appeals",
        headers=frozen,
        json={"order_id": paid_order_id,
              "reason": "付款后卖家一直不发货也不回消息，我至今没有收到货，申请平台介入退款。"},
    )
    assert appeal.status_code == 200, appeal.text
    appeal_data = appeal.json()["data"]
    assert appeal_data["status"] == "waiting"
    assert (appeal_data.get("pending_human") or {}).get("kind") == "appeal_final"

    # 「我的申诉」立即可见
    mine = app_client.get("/api/appeals/mine", headers=frozen)
    assert mine.status_code == 200, mine.text
    assert any(a["order_id"] == paid_order_id and a["status"] == "pending"
               for a in mine.json()["data"])

    # 同一订单重复申诉 → 409（幂等冲突，而非放行或 403）
    dup = app_client.post(
        "/api/appeals",
        headers=frozen,
        json={"order_id": paid_order_id, "reason": "重复提交一次申诉用于验证重复拦截逻辑。"},
    )
    assert dup.status_code == 409, dup.text

    # ② 交易类操作一律 403，且错误文案必须点明「冻结」
    publish = app_client.post(
        "/api/items",
        headers=frozen,
        json={"title": "冻结用户的闲置鼠标",
              "description": "九成新静音无线鼠标，功能正常带原装接收器，闲置出。",
              "price": 20},
    )
    assert publish.status_code == 403, publish.text
    assert "冻结" in publish.json()["message"]

    start_neg = app_client.post(
        "/api/negotiations",
        headers=frozen,
        json={"item_id": 1, "buyer_reserve": 20},
    )
    assert start_neg.status_code == 403, start_neg.text
    assert "冻结" in start_neg.json()["message"]

    pay = app_client.post(f"/api/orders/{unpaid_order_id}/pay", headers=frozen)
    assert pay.status_code == 403, pay.text
    assert "冻结" in pay.json()["message"]
