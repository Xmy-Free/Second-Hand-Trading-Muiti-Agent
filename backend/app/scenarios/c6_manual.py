"""C6-manual 灰区分歧（意见冲突）：信用 75 买家成交 → 加权分落入灰区 → manual
→ risk_human_gate 三级人工门（资金暂缓）→ 人工放行后支付完成。"""
from __future__ import annotations

from sqlmodel import Session, select

from app.models import ConflictEvent, Order
from app.scenarios.runner import Scenario


def _session():
    from app.core import database

    return Session(database.engine)


class C6ManualScenario(Scenario):
    code = "C6-manual"
    title = "信用灰区分歧：加权投票 manual 升级 risk_human_gate，人工放行后支付"
    expectation = "vote.decision=manual、流程挂在 risk_human_gate 冻结支付、C6 level=3、人工 approve 后可支付到 paid"

    def run(self, client) -> list:
        grey = self.login(client, "20240007")    # 信用 75 高风险灰区
        seller = self.login(client, "20240001")
        item_id = 1

        r = client.post("/api/negotiations", headers=grey,
                        json={"item_id": item_id, "buyer_reserve": 18})
        nid = r.json()["data"]["id"]
        first = r.json()["data"]["offers"][0]["price"]
        deal = client.post(f"/api/negotiations/{nid}/offers", headers=seller,
                           json={"price": first, "confirm": True}).json()["data"]
        oid = deal["order_id"]

        with _session() as session:
            order = session.get(Order, oid)
            tid = order.graph_thread_id
        from app.graph.runner import runner

        snap = runner.get_state(tid)
        vote = snap["state"].get("vote", {})
        pending = snap.get("pending_human") or {}
        checks = [
            self.check("灰区投票结论 manual", "vote.decision=manual",
                       vote.get("decision"), vote.get("decision") == "manual"),
            self.check("加权分落入 (-0.5, +0.5) 灰区", "-0.5 < score < 0.5",
                       vote.get("score"),
                       isinstance(vote.get("score"), (int, float))
                       and -0.5 < vote["score"] < 0.5),
            self.check("流程挂起三级人工门", "status=waiting 且 kind=risk_final",
                       f"{snap['status']}/{pending.get('kind')}",
                       snap["status"] == "waiting" and pending.get("kind") == "risk_final"),
            self.check("挂起期间支付被冻结", "订单仍 unpaid",
                       order.status, order.status == "unpaid"),
        ]

        with _session() as session:
            c6 = session.exec(select(ConflictEvent).where(ConflictEvent.scene == "C6")).all()
            manual_events = [e for e in c6 if (e.payload or {}).get("human_required")]
        checks.append(self.check("C6 level=3 人工事件落库", "≥1 条 human_required",
                                 len(manual_events),
                                 len(manual_events) >= 1 and all(e.level == 3 for e in manual_events)))

        # 人工终裁放行 → 进入等待支付门 → 再 resume 支付
        r1 = runner.resume(tid, {"action": "approve", "admin_id": "2400320321", "basis": "人工复核放行"})
        snap1 = runner.get_state(tid)
        pending1 = snap1.get("pending_human") or {}
        checks.append(self.check("放行后转入等待支付门", "kind=wait_pay",
                                 pending1.get("kind"),
                                 r1["status"] == "waiting" and pending1.get("kind") == "wait_pay"))
        runner.resume(tid, {"action": "pay", "admin_id": "2400320321", "basis": "买家沙箱支付"})

        with _session() as session:
            order_after = session.get(Order, oid)
        checks.append(self.check("人工放行后支付成功", "订单 paid",
                                 order_after.status, order_after.status == "paid"))
        return checks
