"""API 路由聚合。"""
from fastapi import APIRouter

from app.api import (
    routes_appeals,
    routes_auth,
    routes_console,
    routes_items,
    routes_market,
    routes_moderation,
    routes_negotiation,
    routes_orders,
    routes_social,
)

api_router = APIRouter()
api_router.include_router(routes_auth.router)
api_router.include_router(routes_items.router)
api_router.include_router(routes_market.router)
api_router.include_router(routes_negotiation.router)
api_router.include_router(routes_orders.router)
api_router.include_router(routes_social.router)
api_router.include_router(routes_appeals.router)
api_router.include_router(routes_moderation.router)
api_router.include_router(routes_console.router)
