"""AC-12 LLM 故障不产生脏状态：传输层注入超时/非法结构，经重试后 RuleLLM 兜底，发布不崩、状态合法。

不直接替换 chat_json，而是伪造其底层 OpenAI 客户端（llm_client._client），
从而真实驱动 client.chat_json 的「重试 → 降级 rule」逻辑。
"""
from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
from openai import APITimeoutError
from sqlmodel import Session

from app.core import database
from app.llm.client import llm_client
from app.models import Item

LEGAL_STATUSES = {"on_sale", "manual", "pending", "draft", "rejected"}
PUBLISH_BODY = {
    "title": "高等数学教材",
    "description": "九成新高等数学教材笔记完整不影响使用",
    "price": 25,
}


class _FakeCompletions:
    def __init__(self, behavior: str, counter: list[int]) -> None:
        self._behavior = behavior
        self._counter = counter

    def create(self, **kwargs):
        self._counter[0] += 1
        if self._behavior == "timeout":
            raise APITimeoutError(
                request=httpx.Request("POST", "https://api.deepseek.com/v1/chat/completions")
            )
        message = SimpleNamespace(content='{"bad": "no decision"}')
        choice = SimpleNamespace(message=message)
        return SimpleNamespace(choices=[choice])


class _FakeChat:
    def __init__(self, behavior: str, counter: list[int]) -> None:
        self.completions = _FakeCompletions(behavior, counter)


class _FakeOpenAI:
    """仅实现 chat_json 用到的 chat.completions.create 路径。"""

    def __init__(self, behavior: str, counter: list[int]) -> None:
        self.chat = _FakeChat(behavior, counter)


@pytest.mark.parametrize("behavior", ["timeout", "bad_structure"])
def test_publish_survives_llm_fault(app_client, login_factory, behavior: str) -> None:
    seller = login_factory("20240001")
    counter = [0]
    # 启用 LLM 分支：enabled 仅取决于 _client 是否为 None
    llm_client._client = _FakeOpenAI(behavior, counter)
    assert llm_client.enabled

    resp = app_client.post("/api/items", headers=seller, json=PUBLISH_BODY)

    # 不允许 500：故障必须被吞掉并降级
    assert resp.status_code != 500, f"LLM 故障不得导致 500：{resp.text}"
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["status"] in LEGAL_STATUSES

    # 确实走进了 LLM 调用（结构化+审核两处）；超时分支还经历了重试
    assert counter[0] >= 2
    if behavior == "timeout":
        assert counter[0] >= 4, "超时后应按 llm_max_retry 重试"

    # 数据库无异常残留：商品记录存在且审核依据落库
    with Session(database.engine) as session:
        item = session.get(Item, data["id"])
        assert item is not None
        assert item.title == "高等数学教材"
        assert item.audit_reason, "审核依据必须写入 audit_reason"
        assert item.status in LEGAL_STATUSES


def test_timeout_falls_back_to_rule_and_on_sale(app_client, login_factory) -> None:
    """超时故障下端到端结果：规则审核放行，商品正常在售（可继续后续交易）。"""
    seller = login_factory("20240001")
    llm_client._client = _FakeOpenAI("timeout", [0])

    resp = app_client.post("/api/items", headers=seller, json=PUBLISH_BODY)
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "on_sale"

    buyer = login_factory("20240004")
    search = app_client.get("/api/market/items?keyword=教材", headers=buyer)
    ids = [it["id"] for it in search.json()["data"]["items"]]
    assert resp.json()["data"]["id"] in ids, "兜底放行的商品应进入在售池"
