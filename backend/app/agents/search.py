"""⑤ 搜索推荐 Agent：仅搜在售、多维综合排序、每条带匹配理由。

新增（FR-5 / C5）：
- target_compat_check：自检排序是否被高佣金/高价因素主导（价格主导且低相关排前即偏向）；
- reorder：被 coordinator 要求重排时执行无偏向重排，并记录重排依据。
- strategy="commission" 为 C5 剧本的偏向模拟入口（正常 API 路径不传，排序与历史一致）。
"""
from __future__ import annotations

from typing import Any

from sqlmodel import Session, select

from app.agents.base import BaseAgent
from app.core.database import engine
from app.kernel.acl import AclEnvelope
from app.kernel.observe import audit
from app.llm import rule_llm
from app.models import Item, User

COND_SCORE = {"全新": 10, "九成新": 8, "八成新": 6}


class SearchAgent(BaseAgent):
    name = "search"
    display_name = "搜索推荐 Agent"
    avatar = "SearchCheck"
    accent = "#22D3EE"
    capabilities = ["多条件检索", "相关性排序", "匹配理由", "目标相容性自检", "无偏向重排"]
    description = "导购员：综合相关性/成色/价格/信用排序并给出每条匹配理由，排序偏向佣金时接受协调者纠偏重排。"

    def handle(self, msg: AclEnvelope) -> AclEnvelope:
        self.ensure_running()
        action = msg.payload.get("action")
        handlers = {
            "search": self.do_search,
            "recommend": self.do_recommend,
            "target_compat_check": self.do_target_compat_check,
            "reorder": self.do_reorder,
        }
        fn = handlers.get(action)
        if not fn:
            return msg.reply("refuse", {"error": f"unknown action {action}"}, error_code="BAD_ACTION")
        data = fn(msg.payload)
        return msg.reply("inform", data, confidence=data.get("confidence", 0.85),
                         summary=data.get("summary", action))

    # ---------------- 相关性计算（确定性，供自检复用） ----------------
    @staticmethod
    def _relevance(keyword: str, item: Item) -> float:
        if not keyword:
            return 1.5
        rel = 0.0
        if keyword in item.title:
            rel += 3
        if keyword in item.category:
            rel += 2
        if keyword in item.description:
            rel += 1
        return rel

    # ---------------- 搜索 ----------------
    def _query_rows(self, session: Session, p: dict[str, Any]):
        keyword = (p.get("keyword") or "").strip()
        category = p.get("category")
        min_price = p.get("min_price")
        max_price = p.get("max_price")
        stmt = select(Item).where(Item.status == "on_sale")
        if category:
            stmt = stmt.where(Item.category == category)
        if min_price is not None:
            stmt = stmt.where(Item.price >= float(min_price))
        if max_price is not None:
            stmt = stmt.where(Item.price <= float(max_price))
        rows = session.exec(stmt.order_by(Item.id.desc()).limit(60)).all()
        sellers = {u.id: u for u in session.exec(select(User)).all()}
        return keyword, rows, sellers

    def do_search(self, p: dict[str, Any]) -> dict[str, Any]:
        with Session(engine) as session:
            keyword, rows, sellers = self._query_rows(session, p)
            scored: list[tuple[float, dict]] = []
            for it in rows:
                rel = self._relevance(keyword, it)
                if keyword and rel == 0:
                    continue  # 有关键词但完全不匹配，过滤
                seller = sellers.get(it.seller_id)
                credit = (seller.credit_score if seller else 100) / 100
                max_price = p.get("max_price")
                price_fit = 1.0
                if max_price:
                    price_fit = max(0.0, 1 - abs(float(it.price) - float(max_price) * 0.8) / float(max_price))
                cond = COND_SCORE.get(it.condition_level, 5) / 10
                score = rel * 2 + credit * 2 + price_fit + cond
                # C5 偏向模拟：佣金/高价因素主导（价格越高排序越前）
                if p.get("strategy") == "commission":
                    score += float(it.price) / 10.0
                view = {
                    "id": it.id, "title": it.title, "category": it.category,
                    "condition_level": it.condition_level, "price": it.price,
                    "image_url": it.image_url or "",
                    "seller_id": it.seller_id,
                    "seller_nickname": seller.nickname if seller else "",
                    "seller_credit": seller.credit_score if seller else 100,
                    "seller_risk": seller.risk_tag if seller else "normal",
                    "seller_is_ai": bool(seller and getattr(seller, "is_ai", False)),
                }
                view["match_reason"] = rule_llm.recommend_reason(
                    {"title": it.title, "condition_level": it.condition_level,
                     "price": it.price, "seller_credit": seller.credit_score if seller else None},
                    keyword,
                )
                scored.append((score, view))

        scored.sort(key=lambda x: x[0], reverse=True)
        items = [v for _, v in scored[:30]]
        return {"items": items, "total": len(items),
                "suggestion": "" if items else self._loose_hint(
                    keyword, p.get("category"), p.get("min_price"), p.get("max_price")),
                "strategy": p.get("strategy", "neutral"),
                "confidence": 0.85, "summary": f"检索到 {len(items)} 件匹配商品"}

    def _loose_hint(self, keyword, category, min_p, max_p) -> str:
        tips = ["没有找到完全匹配的商品"]
        if max_p:
            tips.append("可以提高预算上限")
        if category:
            tips.append(f"或看看其他类目（当前：{category}）")
        if keyword:
            tips.append(f"也可以换个关键词（当前：{keyword}）")
        return "，".join(tips)

    def do_recommend(self, p: dict[str, Any]) -> dict[str, Any]:
        exclude_id = p.get("exclude_item_id")
        category = p.get("category")
        with Session(engine) as session:
            stmt = select(Item).where(Item.status == "on_sale")
            if category:
                stmt = stmt.where(Item.category == category)
            if exclude_id:
                stmt = stmt.where(Item.id != exclude_id)
            rows = session.exec(stmt.limit(20)).all()
            sellers = {u.id: u for u in session.exec(select(User)).all()}
        views = []
        for it in rows[:6]:
            seller = sellers.get(it.seller_id)
            views.append({
                "id": it.id, "title": it.title, "category": it.category,
                "condition_level": it.condition_level, "price": it.price,
                "image_url": it.image_url or "",
                "seller_nickname": seller.nickname if seller else "",
                "seller_credit": seller.credit_score if seller else 100,
                "match_reason": "同类目在售商品，可作为替代选择",
            })
        return {"items": views, "summary": "为你推荐同类商品", "confidence": 0.8}

    # ---------------- C5 目标相容性自检 ----------------
    def do_target_compat_check(self, p: dict[str, Any]) -> dict[str, Any]:
        """检测给定排序是否价格因素主导导致低相关商品排前。"""
        keyword = (p.get("keyword") or "").strip()
        views = p.get("items") or []
        ids = [int(v["id"]) for v in views]
        with Session(engine) as session:
            rows = {it.id: it for it in session.exec(select(Item).where(Item.id.in_(ids))).all()} if ids else {}

        def _rel(v: dict) -> float:
            it = rows.get(int(v["id"]))
            return self._relevance(keyword, it) if it else 0.0

        rels = [_rel(v) for v in views]
        top3 = rels[:3]
        satisfaction = round(sum(min(r, 3) for r in top3) / (3 * 3), 3) if top3 else 0.0
        # 无偏向排序：按相关性（含信用/成色等同权重口径）的理想 top1
        ideal = max(views, key=_rel, default=None)
        actual_top = views[0] if views else None
        biased = False
        basis: list[str] = []
        if (ideal is not None and actual_top is not None
                and int(ideal["id"]) != int(actual_top["id"])
                and float(actual_top.get("price", 0)) > float(ideal.get("price", 0))
                and _rel(actual_top) < _rel(ideal)):
            biased = True
            basis.append(
                f"首位『{actual_top['title']}』(¥{actual_top['price']:g}) 相关性 {_rel(actual_top):g}，"
                f"低于高相关商品『{ideal['title']}』(¥{ideal['price']:g}, 相关性 {_rel(ideal):g})，"
                "价格/佣金因素主导排序")
        if not basis:
            basis.append("排序首位即最高相关商品，未发现价格因素主导" if views else "结果集为空")
        return {"biased": biased, "satisfaction": satisfaction,
                "top1_id": actual_top["id"] if actual_top else None,
                "ideal_top1_id": ideal["id"] if ideal else None,
                "basis": basis, "keyword": keyword,
                "summary": "检测到佣金/高价偏向" if biased else "排序通过目标相容性自检",
                "confidence": 0.9}

    # ---------------- C5 执行重排 ----------------
    def do_reorder(self, p: dict[str, Any]) -> dict[str, Any]:
        before_top = (p.get("items") or [{}])[0]
        result = self.do_search({**p, "strategy": "neutral"})
        after_top = result["items"][0] if result["items"] else {}
        result["reordered"] = True
        result["bias_removed"] = "commission"
        result["reorder_basis"] = (
            f"应协调者要求去除价格主导项：重排前首位 #{before_top.get('id')}《{before_top.get('title', '')}》"
            f"→ 重排后首位 #{after_top.get('id')}《{after_top.get('title', '')}》，相关性优先")
        audit("agent", "search", "c5_reorder", "item", after_top.get("id"),
              {"keyword": p.get("keyword"), "before_top": before_top.get("id"),
               "after_top": after_top.get("id"),
               "reason_id": p.get("reason_id")}, p.get("thread_id"))
        result["summary"] = "已按买家需求相关性完成重排"
        return result
