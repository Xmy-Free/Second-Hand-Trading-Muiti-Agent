"""C4-small 货不对板小额纠纷（目标冲突，≤50 元）：
arbitrator 证据包 → 规则直裁 refund（结构化裁决书 responsibility=seller/action=refund）
→ order 退款释放 → credit 扣罚卖家信用。
"""
from __future__ import annotations

from sqlmodel import Session, select

from app.models import Appeal, ConflictEvent, Item, Order, User
from app.scenarios.runner import Scenario


def _session():
    from app.core import database

    return Session(database.engine)


class C4SmallClaimScenario(Scenario):
    code = "C4-small"
    title = "货不对板小额：证据包+规则直裁退款并联动信用扣罚"
    expectation = "规则直裁 action=refund/responsibility=seller、订单 refunded、商品回在售、卖家信用 -15、C4 level=2"

    def _deal_and_pay(self, client, buyer_h, seller_h, item_id: int, reserve: float) -> int:
        r = client.post("/api/negotiations", headers=buyer_h,
                        json={"item_id": item_id, "buyer_reserve": reserve})
        nid = r.json()["data"]["id"]
        first = r.json()["data"]["offers"][0]["price"]
        deal = client.post(f"/api/negotiations/{nid}/offers", headers=seller_h,
                           json={"price": first, "confirm": True}).json()["data"]
        oid = deal["order_id"]
        client.post(f"/api/orders/{oid}/pay", headers=buyer_h)
        return oid

    def run(self, client) -> list:
        buyer = self.login(client, "20240004")
        seller_h = self.login(client, "20240001")
        item_id = 1  # 18 元高数教材（成交价为首价 14.4，≤ 直裁阈值 50）

        oid = self._deal_and_pay(client, buyer, seller_h, item_id, 18)

        appeal = client.post("/api/appeals", headers=buyer, json={
            "order_id": oid,
            "reason": "收到的书货不对板，内页大量缺页破损，与描述严重不符，申请退款。",
        }).json()["data"]
        rule = appeal.get("rule") or {}

        checks = [
            self.check("小额规则直裁完成", "流程 done 且无人工挂起",
                       f"{appeal.get('status')}/{appeal.get('stage')}",
                       appeal.get("status") == "done" and appeal.get("stage") == "ruled"),
            self.check("裁决书执行方案=退款", "rule.action=refund 且 direct=True",
                       f"{rule.get('action')}/{rule.get('direct')}",
                       rule.get("action") == "refund" and rule.get("direct") is True),
            self.check("裁决书责任方=卖家", "rule.responsibility=seller",
                       rule.get("responsibility"), rule.get("responsibility") == "seller"),
            self.check("裁决书含逐条依据+置信度", "basis 非空且 confidence>0",
                       f"{len(rule.get('basis', []))} 条/{rule.get('confidence')}",
                       bool(rule.get("basis")) and float(rule.get("confidence", 0)) > 0),
        ]

        with _session() as session:
            order = session.get(Order, oid)
            item = session.get(Item, item_id)
            seller = session.exec(select(User).where(User.student_no == "20240001")).first()
            c4 = session.exec(select(ConflictEvent).where(ConflictEvent.scene == "C4")).all()
            appeal_row = session.exec(select(Appeal).where(Appeal.order_id == oid)).first()
        checks += [
            self.check("订单状态=已退款", "order.status=refunded",
                       order.status, order.status == "refunded"),
            self.check("退款后商品释放回在售", "item.status=on_sale",
                       item.status, item.status == "on_sale"),
            self.check("卖家信用扣罚 -15", "104 → 89",
                       seller.credit_score, seller.credit_score == 89),
            self.check("申诉单已裁决留痕", "appeal.status=ruled 且 ruling=refund",
                       f"{appeal_row.status}/{appeal_row.ruling}",
                       appeal_row.status == "ruled" and appeal_row.ruling == "refund"),
            self.check("C4 二级冲突落库", "≥1 条 level=2 action=refund",
                       [(e.level, (e.payload or {}).get("action")) for e in c4],
                       any(e.level == 2 and (e.payload or {}).get("action") == "refund" for e in c4)),
        ]
        return checks
