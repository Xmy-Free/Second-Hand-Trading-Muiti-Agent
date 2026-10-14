"""⑥ 议价谈判 Agent：双边多轮议价（单调让步/纳什参考价/5 轮 120 秒/超时破裂推荐同类）。

响应 JSON 字段与原 trade Agent 完全一致（前端已依赖）。成交后自动拉起 trade 交易流。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlmodel import Session, select

from app.agents.base import BaseAgent
from app.core.config import settings
from app.core.database import engine
from app.kernel.acl import AclEnvelope
from app.kernel.dispatch import call_agent
from app.kernel.observe import record_conflict
from app.llm import rule_llm
from app.models import Item, Negotiation, Offer, User


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _naive_utc() -> datetime:
    return datetime.utcnow()


class NegotiationAgent(BaseAgent):
    name = "negotiation"
    display_name = "议价谈判 Agent"
    avatar = "MessagesSquare"
    accent = "#818CF8"
    capabilities = ["多轮议价主持", "单调让步校验", "纳什参考价", "超时破裂", "成交拉起交易流"]
    description = "中立主持人：组织双边多轮出价，执行单调让步与纳什参考，超轮次/超时破裂并推荐同类商品。"

    def handle(self, msg: AclEnvelope) -> AclEnvelope:
        self.ensure_running()
        action = msg.payload.get("action")
        handlers = {
            "start_negotiation": self.do_start,
            "offer": self.do_offer,
        }
        fn = handlers.get(action)
        if not fn:
            return msg.reply("refuse", {"error": f"unknown action {action}"}, error_code="BAD_ACTION")
        data = fn(msg.payload)
        return msg.reply("inform", data, confidence=data.get("confidence", 0.9),
                         summary=data.get("summary", action))

    # ---------------- 发起会话 ----------------
    def do_start(self, p: dict[str, Any]) -> dict[str, Any]:
        buyer_id, item_id = p["buyer_id"], p["item_id"]
        buyer_reserve = float(p["buyer_reserve"])
        with Session(engine) as session:
            item = session.get(Item, item_id)
            if item is None or item.status != "on_sale":
                return {"ok": False, "error": "商品不存在或不在售", "confidence": 1.0}
            if item.seller_id == buyer_id:
                return {"ok": False, "error": "不能与自己议价", "confidence": 1.0}
            ongoing = session.exec(select(Negotiation).where(
                Negotiation.item_id == item_id, Negotiation.buyer_id == buyer_id,
                Negotiation.status == "ongoing",
            )).first()
            if ongoing:
                return {"ok": False, "error": "已存在进行中的议价会话",
                        "negotiation_id": ongoing.id, "confidence": 1.0}

            seller_reserve = round(item.price * 0.85, 1)
            first_offer = float(p.get("first_offer") or round(buyer_reserve * 0.8, 1))
            if first_offer >= buyer_reserve:
                first_offer = round(buyer_reserve * 0.8, 1)
            nash = round((buyer_reserve + seller_reserve) / 2, 1)

            neg = Negotiation(
                item_id=item_id, buyer_id=buyer_id, seller_id=item.seller_id,
                buyer_reserve=buyer_reserve, seller_reserve=seller_reserve,
                nash_price=nash, max_rounds=settings.neg_max_rounds,
                deadline_seconds=settings.neg_deadline_seconds, status="ongoing",
            )
            session.add(neg)
            session.commit()
            session.refresh(neg)
            session.add(Offer(
                negotiation_id=neg.id, round=1, from_role="buyer", price=first_offer,
                basis=rule_llm.offer_basis("buyer", first_offer, 1),
            ))
            session.commit()
            neg_id = neg.id
            seller = session.get(User, item.seller_id)
        return {"ok": True, "negotiation_id": neg_id, "first_offer": first_offer,
                "nash_price": nash,
                "seller_risk": {"tag": seller.risk_tag, "credit": seller.credit_score},
                "summary": "议价会话已发起，等待卖家回应", "confidence": 0.9}

    # ---------------- 出价 ----------------
    def do_offer(self, p: dict[str, Any]) -> dict[str, Any]:
        neg_id = p["negotiation_id"]
        price = round(float(p["price"]), 1)
        with Session(engine) as session:
            neg = session.get(Negotiation, neg_id)
            if neg is None:
                return {"ok": False, "error": "议价会话不存在", "confidence": 1.0}
            if neg.status != "ongoing":
                return {"ok": False, "error": f"会话已{neg.status}", "status": neg.status,
                        "deal_price": neg.deal_price, "confidence": 1.0}

            if p["user_id"] == neg.buyer_id:
                role = "buyer"
            elif p["user_id"] == neg.seller_id:
                role = "seller"
            else:
                return {"ok": False, "error": "无权参与该议价", "confidence": 1.0}

            # 懒超时
            if _now() > neg.created_at.replace(tzinfo=timezone.utc) + timedelta(seconds=neg.deadline_seconds):
                return self._terminate(session, neg, "超时未达成一致")

            offers = session.exec(select(Offer).where(
                Offer.negotiation_id == neg_id).order_by(Offer.id)).all()
            mine = [o for o in offers if o.from_role == role]
            round_no = len(mine) + 1

            if round_no > neg.max_rounds:
                return self._terminate(session, neg, "已达最大轮次仍未达成一致")

            # 单调让步（违例拒收）
            if mine:
                last = mine[-1].price
                if role == "buyer" and price <= last:
                    return {"ok": False, "error": "买家出价必须高于上一次出价（单调让步）", "confidence": 1.0}
                if role == "seller" and price >= last:
                    return {"ok": False, "error": "卖家要价必须低于上一次要价（单调让步）", "confidence": 1.0}

            # 保留价边界（卖家低于底价 / 买家高于最高价需显式确认）
            if role == "seller" and price < neg.seller_reserve and not p.get("confirm"):
                return {"ok": False, "need_confirm": True,
                        "error": f"该价格低于卖家保留价 ¥{neg.seller_reserve:g}，请确认", "confidence": 1.0}
            if role == "buyer" and price > neg.buyer_reserve and not p.get("confirm"):
                return {"ok": False, "need_confirm": True,
                        "error": f"该价格高于你的保留价 ¥{neg.buyer_reserve:g}，请确认", "confidence": 1.0}

            session.add(Offer(
                negotiation_id=neg_id, round=round_no, from_role=role, price=price,
                basis=p.get("basis") or rule_llm.offer_basis(role, price, round_no, neg.nash_price),
            ))
            session.commit()

            offers = session.exec(select(Offer).where(
                Offer.negotiation_id == neg_id).order_by(Offer.id)).all()
            buyer_best = max((o.price for o in offers if o.from_role == "buyer"), default=None)
            seller_best = min((o.price for o in offers if o.from_role == "seller"), default=None)

            # 成交判定
            deal_price = None
            if role == "buyer" and seller_best is not None and price >= seller_best:
                deal_price = seller_best
            if role == "seller" and buyer_best is not None and price <= buyer_best:
                deal_price = buyer_best

            if deal_price is not None:
                neg.status = "deal"
                neg.deal_price = deal_price
                neg.closed_at = _naive_utc()
                session.commit()
                session.refresh(neg)
                result = self._build_deal(session, neg, deal_price)
                session.expunge(neg)
                hook = self._hook_order(neg_id)
                result.update(hook)
                return result

            # 双方均已出满 max_rounds 仍无交集 → 僵持破裂（C1）
            buyer_cnt = sum(1 for o in offers if o.from_role == "buyer")
            seller_cnt = len(offers) - buyer_cnt
            if buyer_cnt >= neg.max_rounds and seller_cnt >= neg.max_rounds:
                return self._terminate(session, neg, "双方各 5 轮让步后仍未达成一致")

            suggestion = self._next_suggestion(role, offers, neg)
            session.expunge(neg)
            return {"ok": True, "status": "ongoing", "nash_price": neg.nash_price,
                    "next_suggestion": suggestion,
                    "summary": "出价已发送，等待对方回应", "confidence": 0.9}

    def _next_suggestion(self, role: str, offers: list[Offer], neg: Negotiation) -> dict:
        """一级自动协商：朝纳什价收敛的下一步让步建议。"""
        mine = [o for o in offers if o.from_role == role]
        other = [o for o in offers if o.from_role != role]
        if role == "buyer":
            last = mine[-1].price if mine else round(neg.buyer_reserve * 0.8, 1)
            target = round(last + (neg.buyer_reserve - last) * 0.5, 1)
            target = min(target, neg.buyer_reserve)
            if other:
                ask = min(o.price for o in other)
                if target >= ask:
                    return {"price": ask, "would_deal": True, "text": f"接受卖家要价 ¥{ask:g} 即可成交"}
            return {"price": target, "would_deal": False,
                    "text": f"建议第 {len(mine)+1} 轮出价 ¥{target:g}（纳什参考 ¥{neg.nash_price:g}）"}
        last = mine[-1].price if mine else None
        start = last if last is not None else round(neg.seller_reserve / 0.85, 1)
        target = round(start - (start - neg.seller_reserve) * 0.5, 1)
        target = max(target, neg.seller_reserve)
        bids = [o.price for o in offers if o.from_role == "buyer"]
        if bids and target <= max(bids):
            return {"price": max(bids), "would_deal": True, "text": f"接受买家出价 ¥{max(bids):g} 即可成交"}
        return {"price": target, "would_deal": False,
                "text": f"建议让价至 ¥{target:g}（纳什参考 ¥{neg.nash_price:g}）"}

    def _terminate(self, session: Session, neg: Negotiation, reason: str) -> dict[str, Any]:
        neg.status = "terminated"
        neg.closed_at = _naive_utc()
        session.commit()
        rec = record_conflict(
            scene="C1", ctype="goal", level=1, participants=["negotiation", "buyer", "seller"],
            payload={"negotiation_id": neg.id, "nash_price": neg.nash_price,
                     "buyer_reserve_met": False, "reason": reason,
                     "max_rounds": neg.max_rounds},
            result=f"一级协商失败，议价破裂：{reason}；已向买家推荐同类商品",
        )
        item = session.get(Item, neg.item_id)
        rec_items = self._recommend_alt(item.category if item else None, neg.item_id)
        return {"ok": True, "status": "terminated", "terminate_reason": reason,
                "conflict_id": rec["id"], "recommendations": rec_items,
                "summary": "议价破裂，已推荐同类商品", "confidence": 0.9}

    def _recommend_alt(self, category: str | None, exclude_item_id: int) -> list[dict]:
        try:
            reply = call_agent(
                "search", f"c1-alt-{exclude_item_id}",
                {"action": "recommend", "exclude_item_id": exclude_item_id, "category": category},
                summary="议价破裂：为买家推荐同类替代商品",
            )
            return reply.payload.get("items", [])
        except Exception:  # noqa: BLE001 - 推荐失败不影响破裂结论
            return []

    def _build_deal(self, session: Session, neg: Negotiation, deal_price: float) -> dict:
        return {"ok": True, "status": "deal", "deal_price": deal_price,
                "nash_price": neg.nash_price, "item_id": neg.item_id,
                "negotiation_id": neg.id,
                "summary": f"成交！成交价 ¥{deal_price:g}", "confidence": 1.0}

    def _hook_order(self, negotiation_id: int) -> dict:
        """成交后启动交易流（建单预占锁 → 风险 → 投票 → 等待支付），回传建单结果。"""
        from app.graph.runner import runner

        with Session(engine) as session:
            neg = session.get(Negotiation, negotiation_id)
            buyer_id = neg.buyer_id if neg else 0
        try:
            result = runner.start("trade", user_id=buyer_id, negotiation_id=negotiation_id)
            state = result.get("state", {})
            order_info = state.get("order") or {}
            vote = state.get("vote") or {}
            return {
                "order_id": state.get("order_id") or order_info.get("order_id"),
                "flow_status": result.get("status"),
                "final_stage": state.get("stage"),
                "lock_conflict": state.get("stage") == "lock_conflict",
                "conflict": order_info.get("conflict") or ("C6" if vote.get("decision") == "block" else None),
                "conflict_id": order_info.get("conflict_id"),
                "alternatives": order_info.get("alternatives"),
                "arbitration_basis": order_info.get("arbitration_basis"),
                "vote_decision": vote.get("decision"),
                "vote_score": vote.get("score"),
                "error": order_info.get("error"),
            }
        except Exception:  # noqa: BLE001 - 流程异常不应回滚成交事实
            import traceback
            traceback.print_exc()
            return {"order_id": None, "flow_status": "error"}
