"""流程注册入口：各业务流在此挂载到 runner。"""
from __future__ import annotations

from app.graph.runner import runner


def bootstrap_flows() -> None:
    from app.graph.flows import appeal_flow, demo_flow, publish_flow, trade_flow

    runner.register("demo", demo_flow.build)
    runner.register("publish", publish_flow.build)
    runner.register("trade", trade_flow.build)
    runner.register("appeal", appeal_flow.build)
