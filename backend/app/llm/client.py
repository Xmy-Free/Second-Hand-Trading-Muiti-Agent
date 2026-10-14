"""DeepSeek（OpenAI 兼容）适配层：结构化 JSON 输出 + 超时/非法格式重试 + 降级信号。"""
from __future__ import annotations

import json
import re
from typing import Any

from openai import OpenAI

from app.core.config import settings

_JSON_FENCE = re.compile(r"```(?:json)?\s*(\{.*\}|\[.*\])\s*```", re.S)


class LLMClient:
    def __init__(self) -> None:
        self._client: OpenAI | None = None
        if settings.llm_enabled:
            self._client = OpenAI(
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url,
                timeout=settings.llm_timeout_seconds,
            )

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def chat_json(self, system_prompt: str, user_prompt: str) -> tuple[dict[str, Any] | None, str]:
        """返回 (data, mode)。成功 mode='llm'；任何失败 data=None、mode='rule'（调用方走规则兜底）。"""
        if not self._client:
            return None, "rule"
        last_err = ""
        for _ in range(settings.llm_max_retry + 1):
            try:
                resp = self._client.chat.completions.create(
                    model=settings.llm_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.3,
                    response_format={"type": "json_object"},
                )
                content = resp.choices[0].message.content or ""
                data = _parse_json(content)
                if isinstance(data, dict):
                    return data, "llm"
                last_err = "LLM 返回非 JSON 对象"
            except Exception as exc:  # noqa: BLE001 - 任何模型异常都降级
                last_err = f"{type(exc).__name__}: {exc}"
        return None, f"rule({last_err[:40]})"

    def chat_text(self, system_prompt: str, user_prompt: str, *,
                  temperature: float = 0.7, max_tokens: int = 300) -> str | None:
        """普通文本补全（议价拟人回复 FR-203）。

        复用同一 OpenAI client/超时/重试配置；未启用或任何异常均返回 None，
        由调用方切 RuleLLM 确定性兜底。禁止打印 api_key 与请求体。
        """
        if not self._client:
            return None
        for _ in range(settings.llm_max_retry + 1):
            try:
                resp = self._client.chat.completions.create(
                    model=settings.llm_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                content = (resp.choices[0].message.content or "").strip()
                if content:
                    return content[:500]
            except Exception:  # noqa: BLE001 - 任何模型异常都静默降级，不落日志
                continue
        return None


def _parse_json(content: str) -> Any:
    content = content.strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    m = _JSON_FENCE.search(content)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            return None
    # 最后手段：截取第一个 { 到最后一个 }
    left, right = content.find("{"), content.rfind("}")
    if 0 <= left < right:
        try:
            return json.loads(content[left : right + 1])
        except json.JSONDecodeError:
            return None
    return None


llm_client = LLMClient()
