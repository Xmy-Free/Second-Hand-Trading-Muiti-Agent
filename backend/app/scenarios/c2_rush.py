"""C2 并发抢单（资源冲突）：两买家对同一商品成交，预占锁保证恰一单成功。"""
from __future__ import annotations

from sqlmodel import Session, select

from app.models import ConflictEvent, Item, Order
from app.scenarios.runner import Scenario


def _session():
    from app.core import database

    return Session(database.engine)


class C2Scenario(Scenario):
    code = "C2"
    title = "并发抢单：预占锁裁决恰一单成交，失败方获替代推荐"
    expectation = "恰一单成交且商品 locked、败者返回 C2+三优先裁决依据+替代推荐、无超卖"

    def _start(self, client, buyer_h, item_id: int, reserve: float) -> int:
        """商品在售时先行发起议价（两个买家都成功占位）。"""
        r = client.post("/api/negotiations", headers=buyer_h,
                        json={"item_id": item_id, "buyer_reserve": reserve})
        return r.json()["data"]["id"]

    def _accept(self, client, seller_h, nid: int, first_price: float):
        """卖家直接接受买家首价（越过保留价需 confirm）。"""
        return client.post(f"/api/negotiations/{nid}/offers", headers=seller_h,
                           json={"price": first_price, "confirm": True}).json()["data"]

    def run(self, client) -> list:
        b1 = self.login(client, "20240004")
        b2 = self.login(client, "20240005")
        seller = self.login(client, "20240001")
        item_id = 1  # 高数教材 18 元

        # 两路买家在商品仍在售时并发发起议价
        nid1 = self._start(client, b1, item_id, 18)
        nid2 = self._start(client, b2, item_id, 18)
        first1 = client.get(f"/api/negotiations/{nid1}", headers=seller).json()["data"]["offers"][0]["price"]
        first2 = client.get(f"/api/negotiations/{nid2}", headers=seller).json()["data"]["offers"][0]["price"]

        # 卖家依次接受：先成交者成功加锁，后成交者在成交瞬间触发 C2 资源冲突
        d1 = self._accept(client, seller, nid1, first1)
        d2 = self._accept(client, seller, nid2, first2)

        checks = [
            self.check("买家 A 成交建单", "status=deal 且 order_id 存在",
                       f"{d1.get('status')}/{d1.get('order_id')}",
                       d1.get("status") == "deal" and bool(d1.get("order_id"))),
            self.check("买家 B 触发资源冲突", "返回 C2 冲突标识",
                       d2.get("conflict"), d2.get("conflict") == "C2"),
            self.check("失败方获得替代推荐", "alternatives 非空",
                       len(d2.get("alternatives", [])),
                       isinstance(d2.get("alternatives"), list) and len(d2.get("alternatives", [])) > 0),
            self.check("失败返回含三优先裁决依据",
                       "arbitration_basis 含『下单时间→信用分→支付完成』",
                       d2.get("arbitration_basis", ""),
                       "下单时间" in str(d2.get("arbitration_basis", ""))
                       and "信用" in str(d2.get("arbitration_basis", ""))
                       and "支付" in str(d2.get("arbitration_basis", ""))),
        ]

        with _session() as session:
            orders = session.exec(select(Order).where(Order.item_id == item_id)).all()
            item = session.get(Item, item_id)
            c2 = session.exec(select(ConflictEvent).where(ConflictEvent.scene == "C2")).all()
        checks.append(self.check("商品无超卖", "恰好 1 个订单", len(orders), len(orders) == 1))
        checks.append(self.check("商品被锁定/消费", "item.status=locked",
                                 item.status, item.status == "locked"))
        checks.append(self.check("乐观锁版本递增", "lock_version>=1",
                                 item.lock_version, item.lock_version >= 1))
        checks.append(self.check("C2 事件落库", "≥1 条", len(c2), len(c2) >= 1))
        return checks
