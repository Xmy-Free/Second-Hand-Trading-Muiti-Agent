"""TR-2.1：议价室自由文本消息鉴权、落库与字段契约（FR-202）。"""
from __future__ import annotations

import pytest


@pytest.fixture
def ongoing_negotiation(app_client, login_factory):
    """买家 20240004 对卖家 20240001 的种子商品 1 发起一个进行中议价。"""
    buyer = login_factory("20240004")
    start = app_client.post(
        "/api/negotiations",
        headers=buyer,
        json={"item_id": 1, "buyer_reserve": 20},
    )
    assert start.status_code == 200, start.text
    neg_id = int(start.json()["data"]["id"])
    return {
        "neg_id": neg_id,
        "buyer": buyer,
        "seller": login_factory("20240001"),
        "outsider": login_factory("20240002"),
    }


def test_outsider_cannot_read_or_post_messages(app_client, ongoing_negotiation) -> None:
    neg_id = ongoing_negotiation["neg_id"]
    outsider = ongoing_negotiation["outsider"]

    get_resp = app_client.get(
        f"/api/negotiations/{neg_id}/messages", headers=outsider
    )
    assert get_resp.status_code == 403, get_resp.text

    post_resp = app_client.post(
        f"/api/negotiations/{neg_id}/messages",
        headers=outsider,
        json={"content": "我能插个队吗？"},
    )
    assert post_resp.status_code == 403, post_resp.text


def test_participant_message_persisted_with_full_fields(
    app_client, ongoing_negotiation
) -> None:
    neg_id = ongoing_negotiation["neg_id"]
    buyer = ongoing_negotiation["buyer"]

    content = "学长好，这本书 15 块可以的话我今晚就拍～"
    post_resp = app_client.post(
        f"/api/negotiations/{neg_id}/messages",
        headers=buyer,
        json={"content": content},
    )
    assert post_resp.status_code == 200, post_resp.text
    sent = post_resp.json()["data"]
    assert sent["content"] == content
    assert sent["kind"] == "chat"
    assert sent["from_is_ai"] is False
    assert sent["from_nickname"]

    listing = app_client.get(
        f"/api/negotiations/{neg_id}/messages", headers=buyer
    )
    assert listing.status_code == 200, listing.text
    messages = listing.json()["data"]
    mine = next((m for m in messages if m["id"] == sent["id"]), None)
    assert mine is not None, "发送的消息必须能被 GET 列表拉取"
    for field in ("id", "from_user_id", "from_nickname", "from_is_ai",
                  "kind", "created_at"):
        assert field in mine, f"消息缺少字段：{field}"
    assert mine["negotiation_id"] == neg_id
    assert mine["content"] == content
    assert mine["from_is_ai"] is False

    # 卖家同样可读
    seller_listing = app_client.get(
        f"/api/negotiations/{neg_id}/messages",
        headers=ongoing_negotiation["seller"],
    )
    assert seller_listing.status_code == 200
    assert any(m["id"] == sent["id"] for m in seller_listing.json()["data"])


def test_empty_and_oversized_message_rejected(app_client, ongoing_negotiation) -> None:
    neg_id = ongoing_negotiation["neg_id"]
    buyer = ongoing_negotiation["buyer"]
    url = f"/api/negotiations/{neg_id}/messages"

    empty = app_client.post(url, headers=buyer, json={"content": ""})
    assert empty.status_code == 422, empty.text

    oversized = app_client.post(
        url, headers=buyer, json={"content": "字" * 501}
    )
    assert oversized.status_code == 422, oversized.text
