"""C3 卖家不服审核驳回（决策/规则冲突）：
一级对等协商（moderation dispute，≤3 轮补材料+规则解释）
→ 二级规则库复核（arbitrator review_rejection）
→ 三级人工门（publish 流 human_review_gate，interrupt 冻结上架，管理员终裁写回）。
"""
from __future__ import annotations

from sqlmodel import Session, select

from app.kernel.dispatch import call_agent
from app.models import ConflictEvent, Item, User
from app.scenarios.runner import Scenario


def _session():
    from app.core import database

    return Session(database.engine)


class C3RejectAppealScenario(Scenario):
    code = "C3"
    title = "卖家不服驳回：一级解释补材料 → 二级规则复核 → 三级人工终裁"
    expectation = "C3 事件 level 1/2/3 齐全、一级协商限 3 轮、流程挂 human_review_gate、人工裁决写回商品状态"

    def run(self, client) -> list:
        admin = self.login(client, "2400320321")  # noqa: F841 - 保留登录语义
        with _session() as session:
            seller = session.exec(select(User).where(User.student_no == "20240001")).first()
            seller_id = seller.id

        # Stage 0：商品因描述过短被驳回
        st = call_agent(
            "commodity", "c3-structure",
            {"action": "structure", "seller_id": seller_id, "title": "旧台灯",
             "description": "旧物", "price": 8},
            summary="C3：卖家发布描述过短商品",
        ).payload
        item_id = st["item_id"]
        mod = call_agent(
            "moderation", "c3-moderate",
            {"action": "moderate", "item_id": item_id},
            summary="C3：审核商品",
        ).payload

        # Stage 1：两轮一级对等协商（首轮无补充仍驳回；次轮补入疑似高仿描述 → manual）
        d1 = call_agent(
            "moderation", "c3-dispute-1",
            {"action": "dispute", "item_id": item_id, "round": 1, "supplement": ""},
            perf="arbitrate", summary="C3：卖家发起一级协商（第1轮）",
        ).payload
        d2 = call_agent(
            "moderation", "c3-dispute-2",
            {"action": "dispute", "item_id": item_id, "round": 2,
             "supplement": "高仿精仿一比一运动鞋，质量很好"},
            perf="arbitrate", summary="C3：卖家补材料（第2轮）",
        ).payload
        # 一级协商 3 轮上限保护
        d4 = call_agent(
            "moderation", "c3-dispute-4",
            {"action": "dispute", "item_id": item_id, "round": 4, "supplement": "再次申诉"},
            perf="arbitrate", summary="C3：超过一级协商轮次上限",
        ).payload

        checks = [
            self.check("初次审核驳回", "decision=reject",
                       mod.get("decision"), mod.get("decision") == "reject"),
            self.check("一级第1轮解释维持驳回", "peer_consult/reject",
                       f"{d1.get('stage')}/{d1.get('decision')}",
                       d1.get("stage") == "peer_consult" and d1.get("decision") == "reject"),
            self.check("一级第2轮补材料转存疑", "peer_consult/manual",
                       f"{d2.get('stage')}/{d2.get('decision')}",
                       d2.get("stage") == "peer_consult" and d2.get("decision") == "manual"),
            self.check("一级协商 ≤3 轮限时", "第 4 轮返回 escalated 拒收",
                       d4.get("escalated"), d4.get("escalated") is True),
        ]

        # Stage 2：二级规则库复核 → 升级三级
        rev = call_agent(
            "arbitrator", "c3-review",
            {"action": "review_rejection", "item_id": item_id},
            perf="arbitrate", summary="C3：仲裁 Agent 规则库复核",
        ).payload
        checks.append(self.check("二级规则复核升级人工", "decision=escalate",
                                 rev.get("decision"), rev.get("decision") == "escalate"))

        # Stage 3：重提走发布流 → human_review_gate interrupt
        from app.graph.runner import runner

        flow = runner.start("publish", user_id=seller_id, item_id=item_id)
        pending = flow.get("pending_human") or {}
        checks.append(self.check("三级人工门挂起", "status=waiting 且 kind=item_review",
                                 f"{flow['status']}/{pending.get('kind')}",
                                 flow["status"] == "waiting" and pending.get("kind") == "item_review"))

        with _session() as session:
            c3 = session.exec(select(ConflictEvent).where(ConflictEvent.scene == "C3")).all()
            levels = sorted({e.level for e in c3})
            l1 = [e for e in c3 if e.level == 1]
            l3 = [e for e in c3 if e.level == 3]
        checks.append(self.check("C3 三级轨迹齐全", "level 集合 = {1,2,3}",
                                 levels, levels == [1, 2, 3]))
        checks.append(self.check("一级协商全程留痕", "≥2 条 level=1 且 stage=peer_consult",
                                 len(l1),
                                 len(l1) >= 2 and all(
                                     (e.payload or {}).get("stage") == "peer_consult" for e in l1)))
        checks.append(self.check("升级事件含人工门动作", "level=3 payload.action=appeal_human_gate",
                                 [(e.payload or {}).get("action") for e in l3],
                                 any((e.payload or {}).get("action") == "appeal_human_gate" for e in l3)))

        # 人工终裁：驳回写回
        admin_h = self.login(client, "2400320321")
        rr = client.post(f"/api/moderation/flows/{flow['thread_id']}/resume",
                         headers=admin_h,
                         json={"action": "reject", "basis": "证据不足，人工终裁维持驳回"})
        checks.append(self.check("人工终裁写回成功", "HTTP 200 且 stage=human_reviewed",
                                 f"{rr.status_code}/{rr.json().get('data', {}).get('stage')}",
                                 rr.status_code == 200
                                 and rr.json()["data"]["stage"] == "human_reviewed"))
        with _session() as session:
            item = session.get(Item, item_id)
        checks.append(self.check("商品状态为驳回", "item.status=rejected",
                                 item.status, item.status == "rejected"))
        return checks
