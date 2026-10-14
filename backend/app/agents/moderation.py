"""④ 内容审核 Agent：违禁词规则 + LLM 双判定，三档处置 + 安全一票否决（最高优先）。

- moderate：approve/reject/manual/veto + confidence + 逐条依据；veto 冻结不可被覆盖；
- order_vote：风险加权投票中代表内容安全视角；
- dispute：C3 卖家不服驳回的一级对等协商（限时 ≤ consult_max_rounds 轮，补材料+规则解释）。
"""
from __future__ import annotations

from typing import Any

from sqlmodel import Session

from app.agents.base import BaseAgent
from app.core.config import settings
from app.core.database import engine
from app.kernel.acl import AclEnvelope
from app.kernel.observe import audit, record_conflict
from app.llm import rule_llm
from app.llm.client import llm_client
from app.models import Item, Order

MODERATE_PROMPT = """你是校园二手平台内容审核员。判定商品是否允许在校园内交易，只输出 JSON：
{
  "decision": "approve|reject|manual|veto",
  "confidence": 0.0到1.0的数字,
  "reasons": [{"rule": "规则名", "detail": "中文依据"}]
}
禁止交易：大功率电器、作弊器材、烟酒、管制器具、色情赌博、欺诈高仿。存疑给 manual。仅描述过短给 reject。"""


class ModerationAgent(BaseAgent):
    name = "moderation"
    display_name = "内容审核 Agent"
    avatar = "ShieldAlert"
    accent = "#F87171"
    capabilities = ["违禁审核", "规则模型双判定", "安全一票否决", "风险投票", "一级对等协商"]
    description = "安检员：对商品做违禁/欺诈双判定并给出逐条依据与置信度，命中违禁行使不可被覆盖的一票否决。"

    def __init__(self) -> None:
        super().__init__()
        self.set_llm_mode("llm" if llm_client.enabled else "rule")

    def handle(self, msg: AclEnvelope) -> AclEnvelope:
        self.ensure_running()
        action = msg.payload.get("action")
        if action == "moderate":
            data = self.do_moderate(msg.payload)
            return msg.reply("inform", data, confidence=data.get("confidence", 0.9),
                             summary=f"审核结论：{data['decision']}")
        if action == "order_vote":
            data = self.do_order_vote(msg.payload)
            return msg.reply("arbitrate", data, confidence=data.get("confidence", 0.8),
                             summary=f"内容审核方投票：{data['vote']:+d}")
        if action == "dispute":
            data = self.do_dispute(msg.payload)
            return msg.reply("inform", data, confidence=data.get("confidence", 0.8),
                             summary=f"一级协商（第 {data.get('round')} 轮）：{data.get('decision')}")
        return msg.reply("refuse", {"error": f"unknown action {action}"}, error_code="BAD_ACTION")

    # ---------------- 投票（内容安全视角，原 goods.do_order_vote） ----------------
    def do_order_vote(self, p: dict[str, Any]) -> dict[str, Any]:
        with Session(engine) as session:
            row = session.get(Order, p["order_id"])
            item = session.get(Item, row.item_id) if row else None
            if item is None:
                return {"vote": 0, "confidence": 0.5, "basis": "商品信息缺失，弃权"}
            if item.status == "frozen" or any(
                isinstance(r, dict) and r.get("rule") == "banned_word" for r in (item.audit_reason or [])
            ):
                return {"vote": -1, "confidence": 0.95,
                        "basis": "商品存在违禁审核记录，反对放行交易"}
            if any(isinstance(r, dict) and "human" in str(r.get("rule", "")) for r in (item.audit_reason or [])):
                return {"vote": 0, "confidence": 0.7, "basis": "商品曾人工复核，投弃权票"}
            return {"vote": 1, "confidence": 0.85, "basis": "商品审核记录正常，支持放行"}

    # ---------------- 三档审核（原 goods.do_moderate） ----------------
    def do_moderate(self, p: dict[str, Any]) -> dict[str, Any]:
        item_id = p["item_id"]
        with Session(engine) as session:
            item = session.get(Item, item_id)
            if item is None:
                return {"decision": "reject", "confidence": 1.0,
                        "reasons": [{"rule": "not_found", "detail": "商品不存在"}],
                        "mode": "rule"}
            data = self._run_moderation(session, item, p)
            session.commit()
        return data

    def _run_moderation(self, session: Session, item: Item, p: dict[str, Any]) -> dict[str, Any]:
        item_id = item.id
        # 1) 规则优先（确定性安全底线）
        rule_result = rule_llm.moderate(item.title, item.description)
        if rule_result["decision"] == "veto":
            self._apply(session, item, "veto", rule_result["reasons"], 0.98)
            record_conflict(
                scene="C8", ctype="safety", level=3,
                participants=["moderation", "coordinator"],
                payload={"reasons": rule_result["reasons"], "engine": "rule"},
                result="veto：商品冻结，证据直送人工且不可被覆盖",
                graph_thread_id=p.get("thread_id"), session=session,
            )
            audit(actor_type="agent", actor_id="moderation", action="audit_veto",
                  target_type="item", target_id=item_id,
                  detail={"reasons": rule_result["reasons"]},
                  graph_thread_id=p.get("thread_id"), session=session)
            return {"decision": "veto", "confidence": 0.98,
                    "reasons": rule_result["reasons"], "mode": "rule", "item_id": item_id}

        # 2) LLM 复核（可用时）
        merged_reasons = list(rule_result["reasons"])
        decision, confidence, mode = rule_result["decision"], rule_result["confidence"], "rule"
        if llm_client.enabled:
            llm_r, _llm_mode = llm_client.chat_json(
                MODERATE_PROMPT, f"标题：{item.title}\n类目：{item.category}\n描述：{item.description}"
            )
            if llm_r and llm_r.get("decision") in {"approve", "reject", "manual", "veto"}:
                mode = "llm"
                llm_r.setdefault("confidence", 0.7)
                llm_r.setdefault("reasons", [])
                # 3) 规则与模型冲突且置信度接近 → 人工
                if llm_r["decision"] != rule_result["decision"] and abs(
                    float(llm_r["confidence"]) - rule_result["confidence"]
                ) <= 0.2 and rule_result["decision"] != "approve":
                    decision, confidence = "manual", min(
                        float(llm_r["confidence"]), rule_result["confidence"]
                    )
                    merged_reasons = rule_result["reasons"] + [
                        {"rule": "llm_opinion", "detail": r.get("detail", str(r))}
                        for r in llm_r["reasons"]
                    ]
                else:
                    decision = llm_r["decision"]
                    confidence = float(llm_r["confidence"])
                    merged_reasons = llm_r["reasons"] or rule_result["reasons"]
        self.set_llm_mode("llm" if mode == "llm" else "rule")

        # veto 仍然不可放过（模型说 veto 也接受）
        if decision == "veto":
            self._apply(session, item, "veto", merged_reasons, confidence)
            record_conflict(
                scene="C8", ctype="safety", level=3, participants=["moderation", "coordinator"],
                payload={"reasons": merged_reasons, "engine": mode},
                result="veto：商品冻结（模型判定）", graph_thread_id=p.get("thread_id"),
                session=session,
            )
        elif decision == "approve":
            self._apply(session, item, "approve", merged_reasons, confidence)
        elif decision == "reject":
            self._apply(session, item, "reject", merged_reasons, confidence)
        else:
            self._apply(session, item, "manual", merged_reasons, confidence)

        audit(actor_type="agent", actor_id="moderation", action=f"audit_{decision}",
              target_type="item", target_id=item_id,
              detail={"reasons": merged_reasons, "engine": mode},
              graph_thread_id=p.get("thread_id"), session=session)
        return {"decision": decision, "confidence": confidence,
                "reasons": merged_reasons, "mode": mode, "item_id": item_id}

    def _apply(self, session: Session, item: Item, decision: str,
               reasons: list[dict], confidence: float) -> None:
        status_map = {
            "approve": "on_sale", "reject": "rejected",
            "manual": "manual", "veto": "frozen",
        }
        item.status = status_map[decision]
        item.audit_reason = reasons
        if decision == "reject":
            item.reject_count += 1

    # ---------------- C3 一级对等协商：卖家补材料，限时 ≤3 轮 ----------------
    def do_dispute(self, p: dict[str, Any]) -> dict[str, Any]:
        item_id = p["item_id"]
        round_no = int(p.get("round", 1))
        supplement = (p.get("supplement") or "").strip()
        with Session(engine) as session:
            item = session.get(Item, item_id)
            if item is None:
                return {"ok": False, "error": "商品不存在", "confidence": 1.0}
            if round_no > settings.consult_max_rounds:
                return {"ok": False, "escalated": True, "round": round_no,
                        "decision": item.status,
                        "error": f"一级对等协商已达 {settings.consult_max_rounds} 轮上限，升级二级规则复核",
                        "confidence": 1.0}

            # 补材料写入档案（ACL 全程留痕）
            if supplement:
                item.description = f"{item.description}｜卖家补充：{supplement}"
                item.audit_reason = list(item.audit_reason or []) + [
                    {"rule": "seller_supplement", "detail": f"一级协商第 {round_no} 轮补材料：{supplement}"}]
            data = self._run_moderation(session, item, p)
            record_conflict(
                scene="C3", ctype="rule", level=1,
                participants=["moderation", "seller", "commodity"],
                payload={"item_id": item_id, "round": round_no,
                         "supplement": supplement, "decision": data["decision"],
                         "stage": "peer_consult", "limit": settings.consult_max_rounds,
                         "reasons": data.get("reasons", [])},
                result=f"一级对等协商第 {round_no} 轮：审核结论 {data['decision']}",
                graph_thread_id=p.get("thread_id"), session=session,
            )
            audit(actor_type="agent", actor_id="moderation", action="c3_peer_consult",
                  target_type="item", target_id=item_id,
                  detail={"round": round_no, "decision": data["decision"]},
                  graph_thread_id=p.get("thread_id"), session=session)
            session.commit()
        return {"ok": True, "stage": "peer_consult", "round": round_no, **data}
