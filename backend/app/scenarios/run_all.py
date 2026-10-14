"""冲突剧本一键运行器：python -m app.scenarios.run_all

输出 10 个剧本（覆盖 C1–C8）的逐步断言轨迹与期望对照表，全部通过退出码 0。
"""
from __future__ import annotations

import sys

from app.scenarios.c1_stalemate import C1Scenario
from app.scenarios.c2_rush import C2Scenario
from app.scenarios.c3_reject_appeal import C3RejectAppealScenario
from app.scenarios.c4_large_claim import C4LargeClaimScenario
from app.scenarios.c4_small_claim import C4SmallClaimScenario
from app.scenarios.c5_commission_bias import C5CommissionBiasScenario
from app.scenarios.c6_block import C6BlockScenario
from app.scenarios.c6_manual import C6ManualScenario
from app.scenarios.c7_ssot_drift import C7SsotDriftScenario
from app.scenarios.c8_veto import C8Scenario

SCENARIOS = [
    C1Scenario(),
    C2Scenario(),
    C3RejectAppealScenario(),
    C4SmallClaimScenario(),
    C4LargeClaimScenario(),
    C5CommissionBiasScenario(),
    C6BlockScenario(),
    C6ManualScenario(),
    C7SsotDriftScenario(),
    C8Scenario(),
]


def main() -> int:
    print("=" * 86)
    print(" 校园二手交易 Multi-Agent · 冲突剧本回归（C1–C8 共 10 个剧本）")
    print(" 模式：RuleLLM 确定性规则引擎（无需 API Key）")
    print("=" * 86)

    results = []
    all_pass = True
    for sc in SCENARIOS:
        result = sc.execute()
        results.append(result)
        print()
        print(result.line())
        if result.error:
            print("  ERROR:", result.error)
            all_pass = False
            continue
        for c in result.checks:
            mark = "  [v]" if c.passed else "  [x]"
            print(f"{mark} {c.name}")
            print(f"      期望：{c.expect}")
            print(f"      实际：{c.actual}")
            if not c.passed:
                all_pass = False

    # ------------- 汇总表：code / title / 通过条件 / 实际结果 -------------
    print()
    print("=" * 86)
    print(" 汇总表")
    print("-" * 86)
    for r in results:
        actual = (f"PASS（{sum(c.passed for c in r.checks)}/{len(r.checks)}）"
                  if r.passed else f"FAIL（{sum(c.passed for c in r.checks)}/{len(r.checks)}）")
        print(f"{r.code:<10} | {r.title[:30]:<30} | 通过条件：{r.expectation[:28]:<28} | 实际：{actual}")
    print("-" * 86)
    if all_pass:
        print(f" 全部 {len(results)} 个冲突剧本 PASS")
    else:
        print(" 存在 FAIL 剧本，请检查上方 [x] 项")
    print("=" * 86)
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
