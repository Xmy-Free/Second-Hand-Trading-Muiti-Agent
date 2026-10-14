"""TR-3.3（AC-3）：节点脉冲环形缓冲历史接口 GET /api/console/traces。"""
from __future__ import annotations

from app.kernel.observe import emit_node

REQUIRED_FIELDS = ("thread_id", "flow", "node", "status", "ts")


def test_traces_non_empty_reverse_order_and_fields(
    app_client, login_factory
) -> None:
    admin = login_factory("2400320321")
    # 直接发一条真实节点事件（写进程级 deque，与图节点 enter/exit 同路径）
    emit_node(
        thread_id="test-trace-thread-001",
        flow="publish",
        node="pytest_probe",
        status="enter",
        summary="pytest 节点脉冲探针",
    )

    resp = app_client.get("/api/console/traces?limit=40", headers=admin)
    assert resp.status_code == 200, resp.text
    traces = resp.json()["data"]
    assert isinstance(traces, list) and traces, "脉冲历史必须非空"
    assert len(traces) <= 40

    probe = next(
        (t for t in traces if t.get("thread_id") == "test-trace-thread-001"),
        None,
    )
    assert probe is not None, "刚发出的探针事件必须出现在历史中"
    for item in traces:
        for field in REQUIRED_FIELDS:
            assert field in item, f"轨迹元素缺少字段：{field}"

    # 倒序：时间戳（UTC ISO）逐项不增
    stamps = [t["ts"] for t in traces]
    assert stamps == sorted(stamps, reverse=True)

    # 探针应排在很靠前的位置（新事件前插）
    assert traces.index(probe) < len(traces)


def test_traces_forbidden_for_non_admin(app_client, login_factory) -> None:
    student = login_factory("20240001")
    resp = app_client.get("/api/console/traces?limit=40", headers=student)
    assert resp.status_code == 403, resp.text
