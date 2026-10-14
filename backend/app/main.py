"""FastAPI 入口。路由随各任务在 api 包中注册。"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import init_db
from app.core.response import ok, register_exception_handlers
from app.graph.checkpoint import close_checkpointer, init_checkpointer
from app.graph.flows import bootstrap_flows
from app.kernel.events import bus
from app.seeds.seed import run_seeds


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    fresh_seed = run_seeds(light=not settings.seed_demo)
    init_checkpointer()
    bus.bind_loop(asyncio.get_running_loop())
    bootstrap_flows()
    # Agent 注册由 agents.bootstrap 在 T7+ 挂载
    try:
        from app.agents.bootstrap import bootstrap_agents

        bootstrap_agents()
    except ImportError:
        pass
    # 真实演示流程（veto/人工/待支付/风险/申诉等待 + C1/C2/C6/C8 历史）
    # 仅在全新播种时执行一次，重启服务不重复造数据
    if settings.seed_demo and fresh_seed:
        try:
            from app.seeds.seed import seed_demo_flows

            seed_demo_flows()
        except Exception as exc:  # noqa: BLE001 - 演示数据失败不阻断服务
            print(f"[seed_demo_flows] skipped: {type(exc).__name__}: {exc}")
    yield
    close_checkpointer()


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)


@app.get("/api/health")
def health() -> dict:
    from app.llm.client import llm_client

    mode = "llm" if llm_client.enabled else "rule"
    return ok(
        {
            "status": "up",
            "llm_mode": mode,
            "model": settings.llm_model if mode == "llm" else "RuleLLM",
        }
    )


# 路由注册点（后续任务追加）
def _register_routers() -> None:
    try:
        from app.api import api_router

        app.include_router(api_router, prefix="/api")
    except ImportError:
        pass


_register_routers()
