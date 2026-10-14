"""多 Agent 管理控制台：Agent 总览/暂停恢复、流程实例、轨迹、检查点、冲突、消息总线 + /ws/control。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlmodel import Session, select

from app.api.deps import admin_user
from app.core.database import engine, get_session
from app.core.response import BizError, ok
from app.core.security import decode_token
from app.graph.checkpoint import get_checkpointer
from app.graph.runner import runner
from app.kernel.events import bus
from app.kernel.observe import iter_recent_traces
from app.kernel.registry import registry
from app.models import AclMessage, AuditLog, ConflictEvent, User
from app.services.demo_director import DemoRunningError, director

router = APIRouter(prefix="/console", tags=["console"])


# ---------------- Agent 总览 ----------------
@router.get("/agents")
def agents(_: User = Depends(admin_user)):
    return ok(registry.list_status())


@router.post("/agents/{name}/{action}")
def agent_control(name: str, action: str, admin: User = Depends(admin_user)):
    if registry.get(name) is None:
        raise BizError("Agent 不存在", http_status=404)
    if action == "pause":
        registry.pause(name)
    elif action == "resume":
        registry.resume(name)
    else:
        raise BizError("action 仅支持 pause/resume")
    return ok(registry.list_status(), f"{name} 已{'暂停' if action == 'pause' else '恢复'}")


# ---------------- 流程实例 ----------------
@router.get("/instances")
def instances(flow: str = "", _: User = Depends(admin_user),
              session: Session = Depends(get_session)):
    rows = session.exec(
        select(AuditLog).where(AuditLog.action == "flow_start").order_by(AuditLog.id.desc())
    ).all()
    out: list[dict] = []
    seen: set[str] = set()
    for row in rows:
        tid = row.graph_thread_id
        if not tid or tid in seen:
            continue
        detail = row.detail or {}
        if flow and detail.get("flow") != flow:
            continue
        seen.add(tid)
        stage, status, pending, decisions_cnt = detail.get("flow"), "unknown", None, 0
        try:
            snap = runner.get_state(tid)
            status = snap["status"]
            stage = snap["state"].get("stage")
            pending = snap["pending_human"]
            decisions_cnt = len(snap["state"].get("decisions", []))
        except KeyError:
            continue
        out.append({
            "thread_id": tid,
            "flow": detail.get("flow"),
            "stage": stage,
            "status": status,
            "user_id": detail.get("user_id"),
            "business": detail.get("business", {}),
            "pending_human": pending,
            "decision_count": decisions_cnt,
            "created_at": row.created_at.isoformat(),
        })
    return ok(out)


@router.get("/instances/{thread_id}/trace")
def instance_trace(thread_id: str, _: User = Depends(admin_user)):
    try:
        return ok(runner.get_state(thread_id))
    except KeyError as exc:
        raise BizError(str(exc), http_status=404) from exc


@router.get("/instances/{thread_id}/checkpoints")
def instance_checkpoints(thread_id: str, _: User = Depends(admin_user)):
    saver = get_checkpointer()
    items: list[dict] = []
    try:
        for tpl in saver.list({"configurable": {"thread_id": thread_id}}):
            values = tpl.checkpoint.get("channel_values", {}) if isinstance(
                tpl.checkpoint, dict) else {}
            items.append({
                "checkpoint_id": tpl.config["configurable"].get("checkpoint_id"),
                "stage": values.get("stage"),
                "next": list(tpl.metadata.get("next", ())) if tpl.metadata else [],
            })
    except Exception:  # noqa: BLE001 - 检查点读取为增强能力，失败不应阻塞控制台
        items = []
    return ok({"count": len(items), "items": items})


# ---------------- 冲突中心 ----------------
@router.get("/conflicts")
def conflicts(scene: str = "", limit: int = 100, _: User = Depends(admin_user),
              session: Session = Depends(get_session)):
    stmt = select(ConflictEvent)
    if scene:
        stmt = stmt.where(ConflictEvent.scene == scene)
    rows = session.exec(stmt.order_by(ConflictEvent.id.desc()).limit(limit)).all()
    return ok([{
        "id": r.id, "scene": r.scene, "type": r.type, "level": r.level,
        "participants": r.participants, "payload": r.payload, "result": r.result,
        "graph_thread_id": r.graph_thread_id, "created_at": r.created_at.isoformat(),
    } for r in rows])


# ---------------- 消息总线历史 ----------------
@router.get("/messages")
def messages(conversation_id: str = "", sender: str = "", performative: str = "",
             limit: int = 100, _: User = Depends(admin_user),
             session: Session = Depends(get_session)):
    stmt = select(AclMessage)
    if conversation_id:
        stmt = stmt.where(AclMessage.conversation_id == conversation_id)
    if sender:
        stmt = stmt.where(AclMessage.sender == sender)
    if performative:
        stmt = stmt.where(AclMessage.performative == performative)
    rows = session.exec(stmt.order_by(AclMessage.id.desc()).limit(limit)).all()
    return ok([{
        "id": r.id, "conversation_id": r.conversation_id, "performative": r.performative,
        "sender": r.sender, "receiver": r.receiver, "payload": r.payload,
        "confidence": r.confidence, "error_code": r.error_code,
        "graph_thread_id": r.graph_thread_id, "created_at": r.created_at.isoformat(),
    } for r in reversed(rows)])


# ---------------- 实时推送 WS ----------------
@router.websocket("/ws/control")
async def control_ws(ws: WebSocket, token: str = ""):
    uid = decode_token(token)
    if uid is None:
        await ws.close(code=4401)
        return
    with Session(engine) as session:
        admin = session.get(User, uid)
        if admin is None or not admin.is_admin:
            await ws.close(code=4403)
            return
    await ws.accept()
    try:
        await ws.send_json({"type": "connected", "data": {"msg": "console stream online"}})
        async for event in bus.stream():
            await ws.send_json(event)
    except WebSocketDisconnect:
        pass


# ---------------- 一键全自动演示（FR-101/FR-102） ----------------
@router.post("/demo/start")
async def demo_start(admin: User = Depends(admin_user)):
    try:
        data = await director.start(admin.id)
    except DemoRunningError as exc:
        raise BizError(
            f"演示正在运行中（当前阶段：{exc.phase}），请勿重复启动",
            code=409, http_status=409,
        ) from exc
    return ok(data, "一键演示已启动")


@router.get("/demo/status")
def demo_status(_: User = Depends(admin_user)):
    return ok(director.snapshot())


@router.post("/demo/stop")
def demo_stop(_: User = Depends(admin_user)):
    return ok(director.stop(), "已请求停止演示")


# ---------------- 节点脉冲历史（FR-104，进程内环形缓冲） ----------------
@router.get("/traces")
def traces(limit: int = 40, _: User = Depends(admin_user)):
    return ok(iter_recent_traces(limit))
