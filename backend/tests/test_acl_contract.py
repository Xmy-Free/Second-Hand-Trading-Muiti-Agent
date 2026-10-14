"""AC-11 ACL 消息协议统一：合法信封通过，四类非法构造被 Pydantic 拒绝；reply 方向互换。"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.kernel.acl import AclEnvelope


def _valid_kwargs() -> dict:
    return {
        "conversation_id": "conv-neg-1",
        "performative": "propose",
        "sender": "buyer",
        "receiver": "negotiation",
        "summary": "出价",
        "payload": {"price": 18.0},
        "confidence": 0.9,
        "graph_thread_id": "trade-abcd1234",
        "timeout": 30,
    }


def test_valid_envelope_accepted() -> None:
    env = AclEnvelope(**_valid_kwargs())
    assert env.performative == "propose"
    assert env.confidence == 0.9
    assert env.msg_id.startswith("msg-")
    assert env.payload == {"price": 18.0}


def test_default_confidence_and_payload() -> None:
    env = AclEnvelope(
        conversation_id="c", performative="inform", sender="a", receiver="b"
    )
    assert env.confidence == 1.0
    assert env.payload == {}


@pytest.mark.parametrize(
    "bad_kwargs",
    [
        pytest.param({k: v for k, v in _valid_kwargs().items() if k != "conversation_id"},
                     id="missing_conversation_id"),
        pytest.param({**_valid_kwargs(), "performative": "bargain"},
                     id="illegal_performative"),
        pytest.param({**_valid_kwargs(), "confidence": 1.5},
                     id="confidence_above_one"),
        pytest.param({**_valid_kwargs(), "sender": ""},
                     id="empty_sender"),
    ],
)
def test_invalid_envelope_rejected(bad_kwargs: dict) -> None:
    with pytest.raises(ValidationError):
        AclEnvelope(**bad_kwargs)


def test_confidence_below_zero_rejected() -> None:
    with pytest.raises(ValidationError):
        AclEnvelope(**{**_valid_kwargs(), "confidence": -0.1})


def test_reply_swaps_direction_and_preserves_thread() -> None:
    req = AclEnvelope(**_valid_kwargs())
    rep = req.reply("accept", {"ok": True, "deal_price": 18.0},
                    confidence=0.95, summary="同意成交")

    # 收发方向互换
    assert rep.sender == "negotiation"
    assert rep.receiver == "buyer"
    # 同一会话与图线程
    assert rep.conversation_id == req.conversation_id
    assert rep.graph_thread_id == req.graph_thread_id == "trade-abcd1234"
    assert rep.timeout == req.timeout == 30
    # 回复自身言语行为 / 内容 / 置信度
    assert rep.performative == "accept"
    assert rep.payload == {"ok": True, "deal_price": 18.0}
    assert rep.confidence == 0.95
    # reply 生成独立消息 ID
    assert rep.msg_id != req.msg_id


def test_all_nine_performatives_legal() -> None:
    for perf in ("request", "inform", "propose", "accept", "reject",
                 "refuse", "arbitrate", "veto", "interrupt"):
        env = AclEnvelope(conversation_id="c", performative=perf,
                          sender="a", receiver="b")
        assert env.performative == perf
