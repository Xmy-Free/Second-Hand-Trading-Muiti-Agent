"""C8 违禁品发布（安全冲突）：规则命中 → 一票否决冻结 → 任何路径不可上架。"""
from __future__ import annotations

from sqlmodel import Session, select

from app.models import ConflictEvent, Item
from app.scenarios.runner import Scenario


def _session():
    from app.core import database

    return Session(database.engine)


class C8Scenario(Scenario):
    code = "C8"
    title = "违禁品一票否决：冻结直送人工且不可被覆盖"
    expectation = "违禁品 frozen 且依据可见、veto 待办入队、维持后仍冻结、任何业务路径不可上架"

    def run(self, client) -> list:
        seller = self.login(client, "20240001")
        admin = self.login(client, "2400320321")

        r = client.post("/api/items", headers=seller,
                        json={"description": "出热得快电热棒，宿舍烧水大功率神器，30元"})
        data = r.json()["data"]
        item_id = data["id"]

        checks = [
            self.check("违禁商品被冻结", "status=frozen", data["status"], data["status"] == "frozen"),
            self.check("卖家可见否决依据", "reason_text 含命中违禁词",
                       data["reason_text"], "违禁" in data["reason_text"] or "禁售" in data["reason_text"]),
        ]

        # 管理员复核队列出现 veto 任务
        queue = client.get("/api/moderation/queue", headers=admin).json()["data"]
        veto_task = next((q for q in queue if q["kind"] == "veto_review"), None)
        checks.append(self.check("证据直送人工复核台", "存在 veto_review 待办",
                                 bool(veto_task), veto_task is not None))

        # 尝试"通过上架"式越权：veto 门只接受 maintain/unfreeze；即使 unfreeze 也必须有 basis
        if veto_task:
            # 维持冻结
            client.post(f"/api/moderation/flows/{veto_task['thread_id']}/resume",
                        headers=admin, json={"action": "maintain", "basis": "维持安全否决"})
        with _session() as session:
            item = session.get(Item, item_id)
            c8 = session.exec(select(ConflictEvent).where(ConflictEvent.scene == "C8")).all()
        checks.append(self.check("维持后仍为冻结态", "status=frozen",
                                 item.status, item.status == "frozen"))
        checks.append(self.check("C8 安全事件落库", "≥1 条 level=3",
                                 len(c8), len(c8) >= 1 and c8[0].level == 3))

        # 下架等业务路径对冻结商品不可用
        off = client.post(f"/api/items/{item_id}/off-shelf", headers=seller)
        checks.append(self.check("冻结商品无法走业务路径", "下架接口拒绝（400）",
                                 off.status_code, off.status_code == 400))

        # 市场中不可见
        market = client.get("/api/market/items", headers=seller).json()["data"]
        ids = [i["id"] for i in market["items"]]
        checks.append(self.check("违禁品不进入在售池", "市场列表不含该商品",
                                 item_id in ids, item_id not in ids))
        return checks
