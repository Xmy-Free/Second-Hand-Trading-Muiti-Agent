"""统一响应信封 {code, message, data} 与业务异常。"""
from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


def ok(data: Any = None, message: str = "success") -> dict[str, Any]:
    return {"code": 0, "message": message, "data": data}


class BizError(Exception):
    def __init__(self, message: str, code: int = 1, http_status: int = 400) -> None:
        self.message = message
        self.code = code
        self.http_status = http_status
        super().__init__(message)


def register_exception_handlers(app) -> None:  # noqa: ANN001
    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        from app.kernel.dispatch import AgentPausedError

        if isinstance(exc, AgentPausedError):
            return JSONResponse(
                status_code=409,
                content={"code": 409,
                         "message": f"该 Agent 已被管理员暂停，相关服务暂时不可用：{exc.agent_name}",
                         "data": {"agent": exc.agent_name}},
            )
        return JSONResponse(
            status_code=500,
            content={"code": 500, "message": f"服务器内部错误：{exc}"[:200], "data": None},
        )

    @app.exception_handler(BizError)
    async def _biz(_: Request, exc: BizError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.http_status,
            content={"code": exc.code, "message": exc.message, "data": None},
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.status_code, "message": str(exc.detail), "data": None},
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        loc = ".".join(str(x) for x in first.get("loc", []) if x != "body")
        msg = f"{loc}: {first.get('msg', '参数错误')}" if loc else "参数错误"
        return JSONResponse(
            status_code=422,
            content={"code": 422, "message": msg, "data": exc.errors()},
        )
