"""C7 Agent 私有视图与黑板 SSOT 不一致（信息冲突）：
构造 search Agent 缓存的商品私有视图（状态/价格漂移）→ coordinator ssot_reconcile
以 SSOT 自动纠正、列出字段差并记录偏差来源；一致视图不产生新事件。
"""
from __future__ import annotations

from sqlmodel import Session, select

from app.kernel.dispatch import call_agent
from app.models import AuditLog, ConflictEvent, Item
from app.scenarios.runner import Scenario


def _session():
    from app.core import database

    return Session(database.engine)


class C7SsotDriftScenario(Scenario):
    code = "C7"
    title = "状态不一致：SSOT 自动纠正私有视图偏差并记录来源"
    expectation = "检出 status/price/title 三处漂移并以 SSOT 纠正、C7 事件含 source=search、审计含 source、一致视图不新增事件"

    def run(self, client) -> list:
        item_id = 1
        with _session() as session:
            item = session.get(Item, item_id)
            ssot_status, ssot_price = item.status, item.price

        before = call_agent(
            "coordinator", "c7-reconcile-drift",
            {"action": "ssot_reconcile", "entity_type": "item", "entity_id": item_id,
             "source": "search",
             "private_view": {"id": item_id, "status": "locked", "price": 999.0,
                              "title": "漂移缓存"}},
            perf="arbitrate", summary="C7：search 上报私有缓存视图",
        ).payload

        drift_fields = sorted({d["field"] for d in before.get("drifts", [])})
        checks = [
            self.check("检出三处状态漂移", "drift fields = price/status/title",
                       drift_fields, drift_fields == ["price", "status", "title"]),
            self.check("以黑板 SSOT 自动纠正", f"corrected.status={ssot_status} 且 price={ssot_price}",
                       f"{before.get('corrected', {}).get('status')}/"
                       f"{before.get('corrected', {}).get('price')}",
                       before.get("corrected", {}).get("status") == ssot_status
                       and float(before.get("corrected", {}).get("price", -1)) == float(ssot_price)),
            self.check("纠正结果记录偏差来源", "source=search",
                       before.get("source"), before.get("source") == "search"),
        ]

        # 一致视图不报冲突
        call_agent(
            "coordinator", "c7-reconcile-clean",
            {"action": "ssot_reconcile", "entity_type": "item", "entity_id": item_id,
             "source": "search",
             "private_view": {"id": item_id, "status": ssot_status, "price": ssot_price}},
            perf="arbitrate", summary="C7：一致视图复核",
        )

        with _session() as session:
            c7 = session.exec(select(ConflictEvent).where(ConflictEvent.scene == "C7")).all()
            audits = session.exec(select(AuditLog).where(
                AuditLog.action == "ssot_reconcile")).all()
        checks.append(self.check("C7 信息冲突落库", "恰 1 条（一致视图不新增）",
                                 len(c7), len(c7) == 1))
        checks.append(self.check("C7 事件含 source 字段", "payload.source=search",
                                 (c7[0].payload or {}).get("source") if c7 else None,
                                 bool(c7) and (c7[0].payload or {}).get("source") == "search"))
        checks.append(self.check("C7 事件含字段级差异", "payload.diffs 记录 private/ssot",
                                 (c7[0].payload or {}).get("diffs") if c7 else None,
                                 bool(c7) and len((c7[0].payload or {}).get("diffs", [])) == 3))
        checks.append(self.check("审计日志含偏差来源", "audit.detail.source=search",
                                 [(a.detail or {}).get("source") for a in audits],
                                 any((a.detail or {}).get("source") == "search" for a in audits)))
        return checks
