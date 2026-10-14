"""① 协调管理 Agent：编排裁判长。

职责：
- C6 风险加权投票（credit / moderation / coordinator 三方，票权×置信度，平票/灰区升级人工）；
- 6.3 全局效用函数 U（权重配置化，同输入同输出）；
- C5 目标相容性仲裁（推荐佣金偏向 → 效用比较 → 要求 search 重排）；
- C7 SSOT 信息冲突检测与自动纠正（记录偏差来源）；
- 8.4 异常 Agent 熔断后的规则代管（rule_takeover，由 dispatch 异常路径调用）。
"""
from __future__ import annotations

from typing import Any

from sqlmodel import Session

from app.agents.base import BaseAgent
from app.core.config import settings
from app.core.database import engine
from app.kernel.acl import AclEnvelope
from app.kernel.dispatch import call_agent
from app.kernel.observe import audit, record_conflict
from app.models import Item, Order, User

UTIL_DIMS = ("satisfaction", "success", "safety", "fairness", "cost")


class CoordinatorAgent(BaseAgent):
    name = "coordinator"
    display_name = "协调管理 Agent"
    avatar = "Workflow"
    accent = "#818CF8"
    capabilities = ["流程编排", "冲突检测", "加权仲裁", "全局效用评分",
                    "目标相容性检查", "SSOT 纠正", "熔断代管", "人工转接", "注册管理"]
    description = "调度中枢与裁判长：主持加权投票与效用仲裁，检测四类冲突并三级升级，熔断异常 Agent 并规则代管。"

    def handle(self, msg: AclEnvelope) -> AclEnvelope:
        self.ensure_running()
        action = msg.payload.get("action")
        if action == "risk_vote":
            data = self.do_risk_vote(msg.payload)
            return msg.reply("arbitrate", data, confidence=0.95,
                             summary=f"二级仲裁结论：{data['decision']}（加权分 {data['score']:+.2f}）")
        if action == "utility_score":
            data = self.do_utility_score(msg.payload)
            return msg.reply("arbitrate", data, confidence=0.95,
                             summary=f"全局效用 U={data['u']:.3f}")
        if action == "target_compat_check":
            data = self.do_target_compat_check(msg.payload)
            return msg.reply("arbitrate", data, confidence=0.9,
                             summary="目标相容性：要求重排" if data.get("decision") == "reorder"
                             else "目标相容性：方案通过")
        if action == "ssot_reconcile":
            data = self.do_ssot_reconcile(msg.payload)
            return msg.reply("inform", data, confidence=0.99,
                             summary=f"SSOT 自动纠正 {len(data.get('drifts', []))} 处偏差")
        return msg.reply("refuse", {"error": f"unknown action {action}"}, error_code="BAD_ACTION")

    # ---------------- C6 三方加权投票 ----------------
    def do_risk_vote(self, p: dict[str, Any]) -> dict[str, Any]:
        order_id = p["order_id"]
        opinion = p.get("risk_opinion", {})
        with Session(engine) as session:
            order = session.get(Order, order_id)
            buyer = session.get(User, order.buyer_id) if order else None
            buyer_credit = buyer.credit_score if buyer else 100

        # 票 1：信用评价 Agent（风险来源方）
        v_credit = -1 if opinion.get("risk_level") == "high" else (
            0 if opinion.get("risk_level") == "medium" else 1)
        c_credit = float(opinion.get("confidence", 0.8))
        # 票 2：内容审核 Agent（经 ACL 调用，保留多 Agent 协作轨迹；暂停时按弃权）
        try:
            mod_reply = call_agent(
                "moderation", f"vote-moderation-{order_id}",
                {"action": "order_vote", "order_id": order_id},
                perf="arbitrate", summary="邀请内容审核方对风险交易投票",
            )
            v_mod = int(mod_reply.payload.get("vote", 0))
            c_mod = float(mod_reply.payload.get("confidence", 0.7))
            mod_basis = mod_reply.payload.get("basis", "")
        except Exception:  # noqa: BLE001 - Agent 暂停/异常时该票弃权
            v_mod, c_mod, mod_basis = 0, 0.5, "内容审核 Agent 不可用，按弃权处理"
        # 票 3：协调者（平台安全视角）
        if buyer_credit < 70:
            v_coord, c_coord = -1, 0.9
        elif buyer_credit < settings.high_risk_threshold:
            v_coord, c_coord = 0, 0.7
        else:
            v_coord, c_coord = 1, 0.85

        details = [
            {"agent": "credit", "agent_name": "信用评价 Agent",
             "weight": settings.vote_weight_credit, "confidence": c_credit, "vote": v_credit,
             "weighted": round(settings.vote_weight_credit * c_credit * v_credit, 3),
             "basis": opinion.get("basis", [])},
            {"agent": "moderation", "agent_name": "内容审核 Agent",
             "weight": settings.vote_weight_moderation, "confidence": c_mod, "vote": v_mod,
             "weighted": round(settings.vote_weight_moderation * c_mod * v_mod, 3),
             "basis": [mod_basis]},
            {"agent": "coordinator", "agent_name": "协调管理 Agent",
             "weight": settings.vote_weight_coordinator, "confidence": c_coord, "vote": v_coord,
             "weighted": round(settings.vote_weight_coordinator * c_coord * v_coord, 3),
             "basis": [f"平台安全视角：买家信用 {buyer_credit}"]},
        ]
        score = round(sum(d["weighted"] for d in details), 3)
        if score >= settings.vote_pass_score:
            decision = "allow"
            result = f"加权分 {score:+.2f} ≥ +0.5，放行支付"
        elif score <= settings.vote_block_score:
            decision = "block"
            result = f"加权分 {score:+.2f} ≤ -0.5，拦截并取消订单，转人工备案"
        else:
            decision = "manual"
            result = f"加权分 {score:+.2f} 位于灰区，升级三级人工终裁"

        record_conflict(
            scene="C6", ctype="opinion", level=2 if decision != "manual" else 3,
            participants=["coordinator", "credit", "moderation"],
            payload={"order_id": order_id, "risk_opinion": opinion,
                     "details": details, "score": score,
                     "kind": "risk_final" if decision == "manual" else "risk_blocked",
                     "human_required": decision == "manual",
                     "rule": "Σ(票权×置信度×票值)，阈值 ±0.5"},
            result=result, graph_thread_id=p.get("thread_id"),
        )
        return {"decision": decision, "score": score, "details": details, "threshold": 0.5}

    # ---------------- 6.3 全局效用函数（可复现数值快照） ----------------
    def do_utility_score(self, p: dict[str, Any]) -> dict[str, Any]:
        dims = {}
        for name in UTIL_DIMS:
            val = float(p.get(name, 0.0))
            if not 0.0 <= val <= 1.0:
                return {"ok": False, "error": f"维度 {name} 必须位于 [0,1]", "confidence": 1.0}
            dims[name] = val
        weights = {
            "satisfaction": settings.util_w_satisfaction,
            "success": settings.util_w_success,
            "safety": settings.util_w_safety,
            "fairness": settings.util_w_fairness,
            "cost": settings.util_w_cost,
        }
        contributions = {k: round(weights[k] * dims[k], 4) for k in UTIL_DIMS}
        # 成本为负向项
        u = round(contributions["satisfaction"] + contributions["success"]
                  + contributions["safety"] + contributions["fairness"]
                  - contributions["cost"], 4)
        return {"ok": True, "u": u, "dimensions": dims, "weights": weights,
                "contributions": contributions,
                "formula": "U = 0.25·满意度 + 0.20·成交率 + 0.30·安全 + 0.15·公平 − 0.10·成本",
                "summary": f"全局效用 U={u:.3f}", "confidence": 1.0}

    # ---------------- C5 目标相容性仲裁（佣金/高价偏向 → 重排） ----------------
    def do_target_compat_check(self, p: dict[str, Any]) -> dict[str, Any]:
        keyword = p.get("keyword", "")
        biased_views = p.get("biased") or []
        neutral_views = p.get("neutral") or []
        # 经 ACL 请 search 自检两套排序（保留多 Agent 协作轨迹）
        diag_b = call_agent(
            "search", f"c5-check-biased-{keyword}",
            {"action": "target_compat_check", "keyword": keyword, "items": biased_views},
            perf="arbitrate", summary="C5：自检佣金偏向排序",
        ).payload
        diag_n = call_agent(
            "search", f"c5-check-neutral-{keyword}",
            {"action": "target_compat_check", "keyword": keyword, "items": neutral_views},
            perf="arbitrate", summary="C5：自检中性排序",
        ).payload

        sat_b, sat_n = float(diag_b.get("satisfaction", 0)), float(diag_n.get("satisfaction", 0))
        u_b = self.do_utility_score({"satisfaction": sat_b, "success": 0.7, "safety": 0.9,
                                     "fairness": 0.3, "cost": 0.35})
        u_n = self.do_utility_score({"satisfaction": sat_n, "success": 0.7, "safety": 0.9,
                                     "fairness": 0.7, "cost": 0.15})
        reorder = (diag_b.get("biased") is True
                   and sat_b < settings.util_reorder_min_satisfaction
                   and u_n["u"] > u_b["u"])
        data = {
            "decision": "reorder" if reorder else "pass",
            "keyword": keyword,
            "diagnosis_biased": diag_b, "diagnosis_neutral": diag_n,
            "utility_biased": {"u": u_b["u"], "contributions": u_b["contributions"]},
            "utility_neutral": {"u": u_n["u"], "contributions": u_n["contributions"]},
            "threshold": settings.util_reorder_min_satisfaction,
            "basis": [f"偏向方案用户满意度 {sat_b:.3f} < 阈值 {settings.util_reorder_min_satisfaction:g}",
                      f"效用比较：U_偏向={u_b['u']:.3f} < U_中性={u_n['u']:.3f}，要求 search 按需求相关性重排"]
                     if reorder else ["两套排序均通过目标相容性检查"],
            "confidence": 0.9,
        }
        if reorder:
            rec = record_conflict(
                scene="C5", ctype="goal", level=2,
                participants=["coordinator", "search"],
                payload={"keyword": keyword, "satisfaction_biased": sat_b,
                         "satisfaction_neutral": sat_n,
                         "u_biased": u_b["u"], "u_neutral": u_n["u"],
                         "biased_top1": diag_b.get("top1_id"),
                         "ideal_top1": diag_b.get("ideal_top1_id"),
                         "action": "require_reorder",
                         "rule": f"满意度阈值 {settings.util_reorder_min_satisfaction:g} + 全局效用比较"},
                result="推荐方案被高佣金/高价主导，协调者要求重排并记录 C5 目标冲突",
                graph_thread_id=p.get("thread_id"),
            )
            data["conflict_id"] = rec["id"]
        return data

    # ---------------- C7 SSOT 信息冲突检测与自动纠正 ----------------
    def do_ssot_reconcile(self, p: dict[str, Any]) -> dict[str, Any]:
        entity_type = p.get("entity_type", "item")
        entity_id = p.get("entity_id")
        private_view: dict[str, Any] = p.get("private_view") or {}
        source = p.get("source") or "unknown_agent"

        ssot: dict[str, Any] = {}
        if entity_type == "item":
            with Session(engine) as session:
                item = session.get(Item, entity_id)
                if item is None:
                    return {"ok": False, "error": "SSOT 实体不存在", "confidence": 1.0}
                ssot = {"id": item.id, "status": item.status, "price": item.price,
                        "title": item.title, "lock_version": item.lock_version,
                        "seller_id": item.seller_id}
        else:
            return {"ok": False, "error": f"暂不支持的实体类型：{entity_type}", "confidence": 1.0}

        drifts = []
        for key, private_val in private_view.items():
            if key in ssot and ssot[key] != private_val:
                drifts.append({"field": key, "private": private_val,
                               "ssot": ssot[key]})
        if drifts:
            record_conflict(
                scene="C7", ctype="information", level=1,
                participants=[source, "coordinator"],
                payload={"entity_type": entity_type, "entity_id": entity_id,
                         "source": source, "diffs": drifts,
                         "action": "ssot_reconcile"},
                result=f"检测到 {source} 私有视图与黑板 SSOT 偏差 {len(drifts)} 处，已以 SSOT 自动纠正",
                graph_thread_id=p.get("thread_id"),
            )
            audit(actor_type="agent", actor_id="coordinator", action="ssot_reconcile",
                  target_type=entity_type, target_id=entity_id,
                  detail={"source": source, "diffs": drifts, "corrected": ssot},
                  graph_thread_id=p.get("thread_id"))
        return {"ok": True, "entity_type": entity_type, "entity_id": entity_id,
                "source": source, "drifts": drifts, "corrected": ssot,
                "drifted": bool(drifts), "confidence": 1.0,
                "summary": f"SSOT 比对完成，偏差 {len(drifts)} 处"}

    # ---------------- 8.4 熔断后的协调者规则代管 ----------------
    @staticmethod
    def rule_takeover(agent_name: str, payload: dict[str, Any], exc: Exception, *,
                      tripped: bool, failures: int) -> dict[str, Any]:
        """被熔断/异常专家的确定性安全兜底（不产生脏状态，资金类一律保守拒绝/转人工）。"""
        action = payload.get("action", "")
        base = {
            "breaker_takeover": True, "tripped": tripped,
            "consecutive_failures": failures, "agent": agent_name,
            "error": f"{agent_name} 处理异常，协调者规则代管：{type(exc).__name__}",
        }
        if agent_name == "search":
            return {**base, "items": [], "total": 0,
                    "suggestion": "搜索推荐服务暂不可用，请稍后重试",
                    "confidence": 0.3, "summary": "协调者代管：返回空结果集"}
        if agent_name == "moderation" and action == "moderate":
            return {**base, "decision": "manual", "confidence": 0.3,
                    "reasons": [{"rule": "breaker_takeover",
                                 "detail": "审核 Agent 异常，协调者代管：存疑商品一律转人工复核"}],
                    "mode": "rule", "item_id": payload.get("item_id")}
        if agent_name == "credit" and action in ("risk_check", "risk_opinion"):
            return {**base, "ok": True, "risk_level": "medium", "confidence": 0.3,
                    "basis": ["信用 Agent 异常，协调者按保守中风险代管，建议转人工确认"],
                    "factors": ["breaker_takeover"],
                    "credit_score": None, "risk_tag": "unknown"}
        if agent_name == "order" and action == "create_order":
            return {**base, "ok": False,
                    "error": "交易履约服务暂时不可用，未创建任何订单与锁，请稍后重试"}
        if agent_name in ("order", "credit") and action in ("pay", "deliver", "receive",
                                                            "cancel", "apply_ruling", "penalize",
                                                            "review", "mark_appealing"):
            return {**base, "ok": False,
                    "error": f"履约/信用服务暂时不可用，{action} 未执行，资金与订单状态保持不变"}
        if agent_name == "arbitrator":
            return {**base, "suggestion": "manual", "direct": False, "confidence": 0.3,
                    "action": "manual", "responsibility": "none",
                    "basis": ["仲裁 Agent 异常，协调者代管：升级人工终裁"]}
        if agent_name == "negotiation":
            return {**base, "ok": False,
                    "error": "议价服务暂时不可用，未写入任何出价"}
        if agent_name == "commodity":
            return {**base, "ok": False,
                    "error": "商品管理服务暂时不可用，未创建商品档案"}
        return {**base, "ok": False, "error": f"{agent_name}.{action} 服务暂时不可用"}
