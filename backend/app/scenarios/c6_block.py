"""C6-block 信用风险分歧（意见冲突）：高风险买家（68 分）成交 → credit/moderation/coordinator
三方加权投票 → block 拦截取消订单并释放锁。"""
from __future__ import annotations

from sqlmodel import Session, select

from app.models import ConflictEvent, Item, Order
from app.scenarios.runner import Scenario


def _session():
    from app.core import database

    return Session(database.engine)


class C6BlockScenario(Scenario):
    code = "C6-block"
    title = "信用风险意见冲突：三方加权投票拦截高风险交易"
    expectation = "vote.decision=block、credit/moderation/coordinator 三票明细完整、订单 canceled、商品回在售"

    def run(self, client) -> list:
        risky = self.login(client, "20240006")   # 信用 68 高风险
        seller = self.login(client, "20240001")
        admin = self.login(client, "2400320321")
        item_id = 1

        r = client.post("/api/negotiations", headers=risky,
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
        details = vote.get("details", [])

        vote_decision = vote.get("decision")
        checks = [
            self.check("投票被触发并给出拦截结论", "vote.decision=block（流程终态 canceled）",
                       f"decision={vote_decision}, final_stage={snap['state'].get('stage')}",
                       vote_decision == "block"),
            self.check("三方投票明细完整", "3 票（信用评价/内容审核/协调者）",
                       len(details), len(details) == 3),
            self.check("含票权/置信度/票值/加权分",
                       "每票含 weight/confidence/vote/weighted",
                       sorted(details[0].keys()) if details else [],
                       bool(details) and all(
                           {"weight", "confidence", "vote", "weighted"} <= set(d) for d in details)),
            self.check("投票方为新三方注册名", "agents = credit/moderation/coordinator",
                       sorted(d.get("agent") for d in details),
                       sorted(d.get("agent") for d in details) == ["coordinator", "credit", "moderation"]),
            self.check("信用评价方投反对票", "credit vote=-1",
                       [d["vote"] for d in details if d["agent"] == "credit"],
                       any(d["agent"] == "credit" and d["vote"] == -1 for d in details)),
        ]
        score = vote.get("score")
        checks.append(self.check("加权分计算正确", "score 为各 weighted 之和（±0.01）",
                                 score,
                                 isinstance(score, (int, float)) and
                                 abs(score - round(sum(d["weighted"] for d in details), 3)) < 0.01))

        with _session() as session:
            order_after = session.get(Order, oid)
            item_after = session.get(Item, item_id)
            c6 = session.exec(select(ConflictEvent).where(ConflictEvent.scene == "C6")).all()
            participants = c6[0].participants if c6 else []
        checks.append(self.check("高风险订单被拦截", "订单 canceled",
                                 order_after.status, order_after.status == "canceled"))
        checks.append(self.check("拦截后商品锁释放回在售", "item.status=on_sale",
                                 item_after.status, item_after.status == "on_sale"))
        checks.append(self.check("C6 事件落库且参与方为新名", "≥1 条且含 credit/moderation",
                                 participants,
                                 len(c6) >= 1 and "credit" in participants and "moderation" in participants))

        conf = client.get("/api/console/conflicts?scene=C6", headers=admin).json()["data"]
        checks.append(self.check("控制台冲突中心可见 C6", "列表非空且含 details",
                                 len(conf), len(conf) >= 1 and conf[0]["payload"].get("details")))
        return checks
