"""C5 推荐偏向佣金/高价（目标冲突）：
search 佣金偏向排序 → 高相关低价教材被高价低相关商品压顶
→ coordinator 目标相容性检查（效用比较，U_satisfaction 不达标）→ 要求 reorder
→ search 去偏向重排，相关性首位恢复，C5 冲突全程留痕。
"""
from __future__ import annotations

from sqlmodel import Session, select

from app.kernel.dispatch import call_agent
from app.models import ConflictEvent
from app.scenarios.runner import Scenario


def _session():
    from app.core import database

    return Session(database.engine)


class C5CommissionBiasScenario(Scenario):
    code = "C5"
    title = "推荐佣金偏向：效用比较不达标，协调者要求重排并恢复相关性"
    expectation = "偏向排序首位被高价低相关商品占据、verdict=reorder、U_中性>U_偏向、重排后首位恢复且 C5 落库"

    def run(self, client) -> list:
        keyword = "教材"
        biased = call_agent(
            "search", "c5-search-biased",
            {"action": "search", "keyword": keyword, "strategy": "commission"},
            summary="C5：高佣金策略排序",
        ).payload
        neutral = call_agent(
            "search", "c5-search-neutral",
            {"action": "search", "keyword": keyword},
            summary="C5：中性策略排序",
        ).payload

        b_top = (biased.get("items") or [{}])[0]
        n_top = (neutral.get("items") or [{}])[0]

        verdict = call_agent(
            "coordinator", "c5-check",
            {"action": "target_compat_check", "keyword": keyword,
             "biased": biased.get("items"), "neutral": neutral.get("items")},
            perf="arbitrate", summary="C5：协调者目标相容性仲裁",
        ).payload

        reordered = call_agent(
            "search", "c5-reorder",
            {"action": "reorder", "keyword": keyword,
             "items": biased.get("items"), "reason_id": verdict.get("conflict_id")},
            perf="request", summary="C5：执行无偏向重排",
        ).payload
        r_top = (reordered.get("items") or [{}])[0]

        checks = [
            self.check("偏向排序首位被高价商品占据", "biased 首位价格 > neutral 首位且不是同一商品",
                       f"#{b_top.get('id')} ¥{b_top.get('price')} vs #{n_top.get('id')} ¥{n_top.get('price')}",
                       b_top.get("id") != n_top.get("id")
                       and float(b_top.get("price", 0)) > float(n_top.get("price", 0))),
            self.check("协调者要求重排", "verdict.decision=reorder",
                       verdict.get("decision"), verdict.get("decision") == "reorder"),
            self.check("偏向方案满意度不达标", "satisfaction_biased < 0.8",
                       (verdict.get("diagnosis_biased") or {}).get("satisfaction"),
                       float((verdict.get("diagnosis_biased") or {}).get("satisfaction", 1)) < 0.8),
            self.check("效用比较支持中性方案", "U_neutral > U_biased",
                       f"{verdict.get('utility_neutral', {}).get('u')} > "
                       f"{verdict.get('utility_biased', {}).get('u')}",
                       verdict.get("utility_neutral", {}).get("u", 0)
                       > verdict.get("utility_biased", {}).get("u", 0)),
            self.check("重排后首位恢复高相关商品", "reorder 首位 = neutral 首位",
                       f"#{r_top.get('id')} == #{n_top.get('id')}",
                       r_top.get("id") == n_top.get("id")),
            self.check("重排结果携带依据", "reordered=True 且 reorder_basis 非空",
                       reordered.get("reorder_basis", ""),
                       reordered.get("reordered") is True and bool(reordered.get("reorder_basis"))),
        ]
        with _session() as session:
            c5 = session.exec(select(ConflictEvent).where(ConflictEvent.scene == "C5")).all()
        checks.append(self.check("C5 目标冲突落库", "≥1 条 level=2 且 action=require_reorder",
                                 [(e.level, (e.payload or {}).get("action")) for e in c5],
                                 len(c5) >= 1 and all(
                                     e.level == 2 and (e.payload or {}).get("action") == "require_reorder"
                                     for e in c5)))
        return checks
