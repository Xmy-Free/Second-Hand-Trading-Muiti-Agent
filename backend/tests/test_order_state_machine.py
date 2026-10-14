"""订单状态机与预占锁：非法迁移拦截、重复支付幂等、支付超时取消释放、并发抢单恰一单（C2）。"""
from __future__ import annotations

from datetime import datetime

from sqlmodel import Session, select

from app.core import database
from app.models import Item, Order


def _make_deal(app_client, login_factory, buyer_no: str = "20240004",
               item_id: int = 1, reserve: float = 18.0) -> dict:
    """买家对指定商品发起议价，卖家 confirm 接受首价，返回成交视图。"""
    buyer = login_factory(buyer_no)
    seller = login_factory("20240001")
    start = app_client.post(
        "/api/negotiations",
        headers=buyer,
        json={"item_id": item_id, "buyer_reserve": reserve},
    )
    assert start.status_code == 200, start.text
    neg = start.json()["data"]
    first_price = neg["offers"][0]["price"]
    deal = app_client.post(
        f"/api/negotiations/{neg['id']}/offers",
        headers=seller,
        json={"price": first_price, "confirm": True},
    )
    assert deal.status_code == 200, deal.text
    data = deal.json()["data"]
    data["_buyer_headers"] = buyer
    return data


def test_receive_before_pay_is_illegal_transition(app_client, login_factory) -> None:
    deal = _make_deal(app_client, login_factory)
    order_id = deal["order_id"]
    buyer = deal["_buyer_headers"]

    resp = app_client.post(f"/api/orders/{order_id}/receive", headers=buyer)
    assert resp.status_code == 400
    assert "非法" in resp.json()["message"]
    # 订单仍停留在待支付，未被污染
    detail = app_client.get(f"/api/orders/{order_id}", headers=buyer).json()["data"]
    assert detail["status"] == "unpaid"


def test_deliver_before_pay_is_illegal_transition(app_client, login_factory) -> None:
    deal = _make_deal(app_client, login_factory)
    order_id = deal["order_id"]
    seller = login_factory("20240001")

    resp = app_client.post(f"/api/orders/{order_id}/deliver", headers=seller)
    assert resp.status_code == 400
    assert "非法" in resp.json()["message"]


def test_duplicate_pay_is_idempotent(app_client, login_factory) -> None:
    deal = _make_deal(app_client, login_factory)
    order_id = deal["order_id"]
    buyer = deal["_buyer_headers"]

    first = app_client.post(f"/api/orders/{order_id}/pay", headers=buyer)
    assert first.status_code == 200
    assert first.json()["data"]["status"] == "paid"

    second = app_client.post(f"/api/orders/{order_id}/pay", headers=buyer)
    assert second.status_code == 200, second.text
    assert second.json()["data"]["status"] == "paid"

    with Session(database.engine) as session:
        paid_orders = session.exec(
            select(Order).where(Order.item_id == 1, Order.status == "paid")
        ).all()
        assert len(paid_orders) == 1


def test_pay_timeout_cancels_order_and_releases_item(app_client, login_factory) -> None:
    deal = _make_deal(app_client, login_factory)
    order_id = deal["order_id"]
    buyer = deal["_buyer_headers"]

    # 直接把支付截止时间改到过去，模拟懒超时
    with Session(database.engine) as session:
        order = session.get(Order, order_id)
        order.pay_deadline = datetime(2000, 1, 1)
        session.add(order)
        session.commit()

    resp = app_client.post(f"/api/orders/{order_id}/pay", headers=buyer)
    assert resp.status_code == 200, resp.text
    # resume 交易流后沙箱支付节点识别超时：订单取消
    assert resp.json()["data"]["status"] == "canceled"

    with Session(database.engine) as session:
        assert session.get(Order, order_id).status == "canceled"
        # 商品锁释放，回到在售池可被其他人购买
        assert session.get(Item, 1).status == "on_sale"
        locked = session.exec(
            select(Order).where(Order.item_id == 1, Order.status != "canceled")
        ).all()
        assert locked == []


def test_concurrent_rush_exactly_one_order_with_alternatives(app_client, login_factory) -> None:
    """两路买家对同一商品先各发起议价，卖家依次接受：恰一单成交，败者 C2 冲突 + 替代推荐。"""
    b1 = login_factory("20240004")
    b2 = login_factory("20240005")
    seller = login_factory("20240001")
    item_id = 1

    def _start(headers: dict) -> tuple[int, float]:
        r = app_client.post(
            "/api/negotiations",
            headers=headers,
            json={"item_id": item_id, "buyer_reserve": 18},
        )
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        return data["id"], data["offers"][0]["price"]

    nid1, first1 = _start(b1)
    nid2, first2 = _start(b2)

    def _accept(nid: int, price: float) -> dict:
        r = app_client.post(
            f"/api/negotiations/{nid}/offers",
            headers=seller,
            json={"price": price, "confirm": True},
        )
        assert r.status_code == 200, r.text
        return r.json()["data"]

    d1 = _accept(nid1, first1)
    d2 = _accept(nid2, first2)

    # 先到先得：第一单成交
    assert d1["status"] == "deal"
    assert d1["order_id"]
    # 后者在成交瞬间被预占锁裁决
    assert d2["conflict"] == "C2"
    assert d2["alternatives"], "失败方必须获得非空替代推荐"

    with Session(database.engine) as session:
        orders = session.exec(select(Order).where(Order.item_id == item_id)).all()
        assert len(orders) == 1, "同一商品不得超卖：恰好一个订单"
        assert session.get(Item, item_id).status == "locked"
