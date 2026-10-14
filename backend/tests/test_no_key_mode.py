"""AC-8/AC-6 无任何 LLM Key 环境（isolated_app 默认强制 RuleLLM）：主链路与审核全部可用。"""
from __future__ import annotations

from app.llm.client import llm_client


def test_rule_mode_forced_without_key(app_client) -> None:
    # isolated_app 已强制 _client=None：RuleLLM 模式，任何调用都不会联网
    assert llm_client.enabled is False
    health = app_client.get("/api/health")
    assert health.status_code == 200


def test_normal_item_published_on_sale(app_client, login_factory) -> None:
    seller = login_factory("20240001")
    resp = app_client.post(
        "/api/items",
        headers=seller,
        json={
            "title": "大学物理实验教材与资料",
            "description": "大物实验教材，数据记录完整，页面干净无涂画，配套资料齐全",
            "price": 15,
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["status"] == "on_sale"
    assert data["category"] == "教材资料"
    assert data["audit_reason"], "规则审核依据应落库"


def test_banned_item_frozen_without_key(app_client, login_factory) -> None:
    seller = login_factory("20240001")
    resp = app_client.post(
        "/api/items",
        headers=seller,
        json={"description": "出热得快电热棒，宿舍烧水大功率神器，30元自提"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["status"] == "frozen", "无 Key 规则引擎必须命中违禁一票否决"
    assert "违禁" in data["reason_text"] or "禁售" in data["reason_text"]

    # 冻结品不进入在售池
    market = app_client.get("/api/market/items", headers=seller).json()["data"]["items"]
    assert data["id"] not in [it["id"] for it in market]


def test_negotiation_deal_and_order_created_without_key(app_client, login_factory) -> None:
    buyer = login_factory("20240004")
    seller = login_factory("20240001")

    # 种子商品 item 1：高数教材 18 元
    start = app_client.post(
        "/api/negotiations",
        headers=buyer,
        json={"item_id": 1, "buyer_reserve": 18},
    )
    assert start.status_code == 200, start.text
    neg = start.json()["data"]
    assert neg["nash_price"] > 0
    first_price = neg["offers"][0]["price"]

    deal = app_client.post(
        f"/api/negotiations/{neg['id']}/offers",
        headers=seller,
        json={"price": first_price, "confirm": True},
    )
    assert deal.status_code == 200, deal.text
    deal_data = deal.json()["data"]
    assert deal_data["status"] == "deal"
    assert deal_data["order_id"], "无 Key 模式下成交必须成功建单"

    order = app_client.get(
        f"/api/orders/{deal_data['order_id']}", headers=buyer
    ).json()["data"]
    assert order["status"] == "unpaid"
    assert order["deal_price"] == first_price

    # 继续走完支付/交付/收货，证明 RuleLLM 下全链路可演示
    assert app_client.post(
        f"/api/orders/{order['id']}/pay", headers=buyer
    ).json()["data"]["status"] == "paid"
    assert app_client.post(
        f"/api/orders/{order['id']}/deliver", headers=seller
    ).json()["data"]["status"] == "receiving"
    assert app_client.post(
        f"/api/orders/{order['id']}/receive", headers=buyer
    ).json()["data"]["status"] == "completed"
