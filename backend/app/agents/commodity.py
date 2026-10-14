"""③ 商品管理 Agent：描述结构化、类目成色识别、建议价区间、上下架。

审核职责已拆分给 moderation；本 Agent 只负责商品档案与库存状态。
"""
from __future__ import annotations

from typing import Any

from sqlmodel import Session, select

from app.agents.base import BaseAgent
from app.core.database import engine
from app.kernel.acl import AclEnvelope
from app.kernel.observe import audit
from app.llm import rule_llm
from app.llm.client import llm_client
from app.models import Item

STRUCT_PROMPT = """你是校园二手平台的商品管家。从用户自然语言描述中抽取商品信息，只输出 JSON：
{
  "title": "精炼的商品标题（含品牌/科目，≤24字）",
  "category": "教材资料|数码电子|生活用品|运动户外|服饰鞋包|美妆个护|其他",
  "condition_level": "全新|九成新|八成新|其他",
  "attrs": {"brand": "品牌或null", "price_hint": 数字或null},
  "missing": ["缺失的关键信息，没有则空数组"]
}"""


class CommodityAgent(BaseAgent):
    name = "commodity"
    display_name = "商品管理 Agent"
    avatar = "Package"
    accent = "#34D399"
    capabilities = ["信息结构化", "类目成色识别", "建议定价", "上下架管理"]
    description = "上架管家：把自然语言描述结构化为标准商品档案，给出建议价区间，并管理未锁定商品的上下架。"

    def __init__(self) -> None:
        super().__init__()
        self.set_llm_mode("llm" if llm_client.enabled else "rule")

    def handle(self, msg: AclEnvelope) -> AclEnvelope:
        self.ensure_running()
        action = msg.payload.get("action")
        handlers = {
            "structure": self.do_structure,
            "suggest_price": self.do_suggest_price,
            "off_shelf": self.do_off_shelf,
        }
        fn = handlers.get(action)
        if not fn:
            return msg.reply("refuse", {"error": f"unknown action {action}"}, error_code="BAD_ACTION")
        data = fn(msg.payload)
        return msg.reply("inform", data, confidence=data.get("confidence", 0.9),
                         summary=data.get("summary", "商品档案处理完成"))

    # ---------------- 结构化建档 ----------------
    def do_structure(self, p: dict[str, Any]) -> dict[str, Any]:
        seller_id = p["seller_id"]
        raw_title = (p.get("title") or "").strip()
        desc = (p.get("description") or "").strip()
        declared_price = p.get("price")

        structured, mode = None, self.llm_mode
        if llm_client.enabled and len(desc) >= 8:
            structured, mode = llm_client.chat_json(STRUCT_PROMPT, f"标题：{raw_title}\n描述：{desc}")
        if not structured:
            structured = rule_llm.structure_item(f"{raw_title} {desc}")
            mode = "rule"
        self.set_llm_mode("llm" if mode == "llm" else "rule")

        title = raw_title or structured.get("title", "")[:24]
        category = structured.get("category", "其他")
        condition = structured.get("condition_level", "八成新")
        attrs = structured.get("attrs", {})
        missing = structured.get("missing", [])

        with Session(engine) as session:
            ref = [float(r) for r in session.exec(
                select(Item.price).where(Item.category == category, Item.status == "on_sale")
            ).all() if r]
            hint = attrs.get("price_hint") if isinstance(attrs, dict) else None
            low, high = rule_llm.suggest_price(
                category, ref, declared_price or (float(hint) if hint else None)
            )

            item = Item(
                seller_id=seller_id, title=title or "未命名商品", category=category,
                condition_level=condition, attrs=attrs if isinstance(attrs, dict) else {},
                description=desc, image_url=p.get("image_url", ""),
                price=float(declared_price) if declared_price else round((low + high) / 2, 1),
                price_suggest_min=low, price_suggest_max=high,
                status="pending",
                audit_reason=[{"rule": "structure", "detail": f"结构化引擎：{mode}"}],
            )
            session.add(item)
            session.commit()
            session.refresh(item)
            item_id = item.id

        return {
            "item_id": item_id, "title": title, "category": category,
            "condition_level": condition, "missing": missing,
            "price_suggest_min": low, "price_suggest_max": high, "mode": mode,
            "summary": "商品结构化与建议价完成",
            "confidence": 0.9 if mode == "llm" else 0.8,
        }

    # ---------------- 建议价（独立查询） ----------------
    def do_suggest_price(self, p: dict[str, Any]) -> dict[str, Any]:
        category = p.get("category", "其他")
        with Session(engine) as session:
            ref = [float(r) for r in session.exec(
                select(Item.price).where(Item.category == category, Item.status == "on_sale")
            ).all() if r]
        low, high = rule_llm.suggest_price(category, ref, p.get("declared_price"))
        return {"category": category, "price_suggest_min": low, "price_suggest_max": high,
                "reference_count": len(ref), "summary": f"建议价区间 ¥{low:g}~¥{high:g}",
                "confidence": 0.8}

    # ---------------- 下架（仅未锁定/在售可下架；冻结/锁定一律拒绝） ----------------
    def do_off_shelf(self, p: dict[str, Any]) -> dict[str, Any]:
        item_id = p["item_id"]
        with Session(engine) as session:
            item = session.get(Item, item_id)
            if item is None:
                return {"ok": False, "error": "商品不存在", "confidence": 1.0}
            if item.status == "off_shelf":
                return {"ok": True, "idempotent": True, "status": "off_shelf",
                        "summary": "商品已下架", "confidence": 1.0}
            if item.status != "on_sale":
                return {"ok": False, "status": item.status,
                        "error": f"商品当前状态为 {item.status}，仅未锁定的在售商品可以下架",
                        "confidence": 1.0}
            item.status = "off_shelf"
            audit("agent", "commodity", "item_off_shelf", "item", item.id,
                  {"seller_id": item.seller_id}, p.get("thread_id"), session=session)
            session.commit()
            return {"ok": True, "status": "off_shelf", "item_id": item.id,
                    "summary": "商品已下架", "confidence": 1.0}
