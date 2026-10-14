"""C4-large 货不对板大额纠纷（>50 元，耳机 180 元）：
规则无法直裁 → appeal_human_gate 三级人工门冻结 → 管理员终裁 refund → order+credit 联动。"""
from __future__ import annotations

from sqlmodel import Session, select

from app.models import ConflictEvent, Order, User
from app.scenarios.runner import Scenario


def _session():
    from app.core import database

    return Session(database.engine)


class C4LargeClaimScenario(Scenario):
    code = "C4-large"
    title = "货不对板大额：规则无法直裁，升级三级人工终裁后退款扣信用"
    expectation = "流程挂 appeal_human_gate、裁决书 action=manual、C4 level=3、人工 refund 后订单 refunded 卖家 -15"

    def run(self, client) -> list:
        buyer = self.login(client, "20240004")
        seller_h = self.login(client, "20240002")
        admin = self.login(client, "2400320321")
        item_id = 4  # 索尼耳机 180 元，卖家 20240002

        r = client.post("/api/negotiations", headers=buyer,
                        json={"item_id": item_id, "buyer_reserve": 180})
        nid = r.json()["data"]["id"]
        first = r.json()["data"]["offers"][0]["price"]
        deal = client.post(f"/api/negotiations/{nid}/offers", headers=seller_h,
                           json={"price": first, "confirm": True}).json()["data"]
        oid = deal["order_id"]
        client.post(f"/api/orders/{oid}/pay", headers=buyer)

        appeal = client.post("/api/appeals", headers=buyer, json={
            "order_id": oid,
            "reason": "耳机货不对板，右耳无声且耳罩磨损严重，与描述的几乎全新不符，要求退货退款。",
        }).json()["data"]
        rule = appeal.get("rule") or {}
        tid = appeal.get("thread_id")
        pending = appeal.get("pending_human") or {}

        checks = [
            self.check("大额纠纷挂三级人工门", "status=waiting 且 kind=appeal_final",
                       f"{appeal.get('status')}/{pending.get('kind')}",
                       appeal.get("status") == "waiting" and pending.get("kind") == "appeal_final"),
            self.check("裁决建议为人工", "rule.action=manual 且 direct=False",
                       f"{rule.get('action')}/{rule.get('direct')}",
                       rule.get("action") == "manual" and rule.get("direct") is False),
            self.check("挂起依据含超阈值说明", "basis 提及 50 阈值",
                       "；".join(rule.get("basis", [])),
                       "50" in "；".join(rule.get("basis", []))),
        ]

        with _session() as session:
            order = session.get(Order, oid)
            c4 = session.exec(select(ConflictEvent).where(ConflictEvent.scene == "C4")).all()
        checks.append(self.check("等待终裁期间订单冻结在申诉中", "order.status=appealing",
                                 order.status, order.status == "appealing"))
        checks.append(self.check("C4 level=3 事件落库", "≥1 条 level=3 human_required",
                                 [(e.level, (e.payload or {}).get("human_required")) for e in c4],
                                 any(e.level == 3 and (e.payload or {}).get("human_required") for e in c4)))

        # 管理员终裁退款
        rr = client.post(f"/api/moderation/flows/{tid}/resume", headers=admin,
                         json={"action": "refund", "basis": "证据充分，人工终裁退货退款"})
        checks.append(self.check("人工终裁写回成功", "HTTP 200",
                                 rr.status_code, rr.status_code == 200))
        with _session() as session:
            order_after = session.get(Order, oid)
            seller = session.exec(select(User).where(User.student_no == "20240002")).first()
        checks.append(self.check("终裁后订单退款", "order.status=refunded",
                                 order_after.status, order_after.status == "refunded"))
        checks.append(self.check("卖家信用扣罚 -15", "100 → 85",
                                 seller.credit_score, seller.credit_score == 85))
        return checks
