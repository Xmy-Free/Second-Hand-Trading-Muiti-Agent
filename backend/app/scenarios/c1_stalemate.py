"""C1 议价僵持（目标冲突）：保留价无交集 + 5 轮不让步 → 纳什参考 → 超时破裂 + 同类推荐。"""
from __future__ import annotations

from sqlmodel import Session, select

from app.models import ConflictEvent
from app.scenarios.runner import Scenario


def _session():
    from app.core import database

    return Session(database.engine)


class C1Scenario(Scenario):
    code = "C1"
    title = "议价僵持：一级自动协商失败后破裂并推荐同类"
    expectation = "5 轮无交集后会话 terminated、纳什价已计算、返回同类推荐、C1 事件落库"

    def run(self, client) -> list:
        buyer = self.login(client, "20240004")
        seller = self.login(client, "20240001")  # item 1 的卖家
        item_id = 1
        r = client.post("/api/negotiations", headers=buyer,
                        json={"item_id": item_id, "buyer_reserve": 10, "first_offer": 5})
        neg = r.json()["data"]
        nid = neg["id"]
        checks = [
            self.check("纳什参考价已计算", "nash_price 为正数且已持久化",
                       neg["nash_price"], isinstance(neg["nash_price"], (int, float)) and neg["nash_price"] > 0),
        ]

        # 买家 r1=5；卖家 5 轮高价 100→60，始终高于买家保留价
        seller_prices = [100, 90, 80, 70, 60]
        buyer_prices = [5, 7, 8, 9, 10]
        # r1 买家首价已存在；补齐 r1 卖家与 r2-r5
        last = {}
        for i in range(5):
            if i == 0:
                last = client.post(f"/api/negotiations/{nid}/offers", headers=seller,
                                   json={"price": seller_prices[i], "confirm": True}).json()["data"]
            else:
                client.post(f"/api/negotiations/{nid}/offers", headers=buyer,
                            json={"price": buyer_prices[i]})
                last = client.post(f"/api/negotiations/{nid}/offers", headers=seller,
                                   json={"price": seller_prices[i], "confirm": True}).json()["data"]

        checks.append(self.check("5 轮后会话破裂", "status=terminated",
                                 last.get("status"), last.get("status") == "terminated"))
        checks.append(self.check("返回同类替代推荐", "recommendations 非空列表",
                                 len(last.get("recommendations", [])),
                                 isinstance(last.get("recommendations"), list) and len(last.get("recommendations", [])) > 0))
        checks.append(self.check("破裂原因可读", "含超轮次/未达成说明",
                                 last.get("terminate_reason", ""),
                                 bool(last.get("terminate_reason"))))

        # 非单调出价被拒绝
        bad = client.post(f"/api/negotiations/{nid}/offers", headers=buyer, json={"price": 1}).json()["data"]
        checks.append(self.check("终止会话拒绝新出价", "返回会话已终止错误",
                                 bad.get("error", ""), "terminated" in str(bad.get("error", ""))))

        with _session() as session:
            c1 = session.exec(select(ConflictEvent).where(ConflictEvent.scene == "C1")).all()
        checks.append(self.check("C1 冲突事件落库", "≥1 条 C1 记录",
                                 len(c1), len(c1) >= 1))
        return checks
