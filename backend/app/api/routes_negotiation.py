"""议价路由：发起 / 列表 / 详情 / 出价 / 聊天消息 + WebSocket 实时议价室。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.api.deps import current_user, trading_user
from app.core.database import engine, get_session
from app.core.response import BizError, ok
from app.core.security import decode_token
from app.kernel.dispatch import call_agent, is_paused_reply, paused_message
from app.kernel.events import bus
from app.kernel.hub import hub
from app.models import Negotiation, NegotiationMessage, User
from app.schemas.negotiation import negotiation_view
from app.services import ai_chat

router = APIRouter(tags=["negotiation"])


def _guard(reply) -> None:
    if is_paused_reply(reply):
        raise BizError(paused_message(reply), code=409, http_status=409)


class StartIn(BaseModel):
    item_id: int
    buyer_reserve: float = Field(gt=0, le=100000)
    first_offer: float | None = Field(default=None, gt=0)


class OfferIn(BaseModel):
    price: float = Field(gt=0, le=100000)
    confirm: bool = False
    basis: str | None = None


class MessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=500)


@router.post("/negotiations")
def start(body: StartIn, user: User = Depends(trading_user),
          session: Session = Depends(get_session)):
    # FR-2 用户代理：买家发起议价时沉淀保留价画像（ACL 协作留痕，失败不阻断主链路）
    call_agent(
        "user_agent", f"ua-profile-{user.id}",
        {"action": "update_profile", "user_id": user.id,
         "buyer_reserve": body.buyer_reserve},
        summary="用户代理记录买家保留价画像",
    )
    reply = call_agent(
        "negotiation", f"neg-start-{user.id}-{body.item_id}",
        {"action": "start_negotiation", "buyer_id": user.id,
         "item_id": body.item_id, "buyer_reserve": body.buyer_reserve,
         "first_offer": body.first_offer},
        summary=f"发起议价：商品 {body.item_id}",
    )
    _guard(reply)
    data = reply.payload
    if not data.get("ok"):
        raise BizError(data.get("error", "发起失败"))
    neg = session.get(Negotiation, data["negotiation_id"])
    view = negotiation_view(neg, session, user.id)
    _push(str(neg.id), {"type": "started", "detail": view})
    return ok(view, data.get("summary", "议价已发起"))


@router.get("/negotiations")
def list_mine(user: User = Depends(current_user), session: Session = Depends(get_session)):
    rows = session.exec(
        select(Negotiation).where(
            (Negotiation.buyer_id == user.id) | (Negotiation.seller_id == user.id)
        ).order_by(Negotiation.id.desc())
    ).all()
    return ok([negotiation_view(n, session, user.id) for n in rows])


@router.get("/negotiations/{neg_id}")
def detail(neg_id: int, user: User = Depends(current_user),
           session: Session = Depends(get_session)):
    _neg, view = _get_participant(neg_id, user, session)
    return ok(view)


@router.post("/negotiations/{neg_id}/offers")
def make_offer(neg_id: int, body: OfferIn, user: User = Depends(trading_user),
               session: Session = Depends(get_session)):
    neg, view = _get_participant(neg_id, user, session)
    reply = call_agent(
        "negotiation", f"neg-{neg_id}",
        {"action": "offer", "negotiation_id": neg_id, "user_id": user.id,
         "price": body.price, "confirm": body.confirm, "basis": body.basis},
        summary=f"{view['my_role']}出价 ¥{body.price:g}",
    )
    if is_paused_reply(reply):
        raise BizError(paused_message(reply), code=409, http_status=409)
    data = reply.payload
    if not data.get("ok"):
        # need_confirm / 规则拒绝：把信息返回给前端，不记错误状态
        return ok(data, data.get("error", "出价未被接受"))
    session.expire_all()
    neg = session.get(Negotiation, neg_id)
    view = negotiation_view(neg, session, user.id)
    view["server_note"] = data.get("next_suggestion")
    view["recommendations"] = data.get("recommendations")
    view["terminate_reason"] = data.get("terminate_reason")
    view["conflict_id"] = data.get("conflict_id")
    # 成交后交易流建单结果（成功订单号 / C2 锁冲突与替代推荐）
    view["flow_status"] = data.get("flow_status")
    view["lock_conflict"] = data.get("lock_conflict")
    view["conflict"] = data.get("conflict")
    view["alternatives"] = data.get("alternatives")
    view["arbitration_basis"] = data.get("arbitration_basis")
    view["winner"] = data.get("winner")
    if data.get("order_id"):
        view["order_id"] = data["order_id"]
    _push(str(neg_id), {"type": "update", "detail": view,
                        "status": data.get("status"), "deal_price": data.get("deal_price")})
    # FR-203：对方为 AI 时，真人出价后同样触发拟人回复与策略出价（服务内自检 is_ai/互斥）
    if data.get("ok") and data.get("status") == "ongoing":
        ai_chat.schedule_ai_reply(neg_id, f"（对方刚刚出价 ¥{body.price:g}）", user.id)
    return ok(view, data.get("summary", "出价成功"))


# ---------------- 议价室聊天消息（FR-202） ----------------
@router.get("/negotiations/{neg_id}/messages")
def list_messages(neg_id: int, user: User = Depends(current_user),
                  session: Session = Depends(get_session)):
    neg = session.get(Negotiation, neg_id)
    if neg is None:
        raise BizError("议价会话不存在", http_status=404)
    if user.id not in (neg.buyer_id, neg.seller_id) and not user.is_admin:
        raise BizError("无权查看该议价会话", code=403, http_status=403)
    rows = session.exec(
        select(NegotiationMessage).where(
            NegotiationMessage.negotiation_id == neg_id
        ).order_by(NegotiationMessage.id)
    ).all()
    users = {u.id: u for u in session.exec(select(User)).all()}
    return ok([{
        "id": m.id,
        "negotiation_id": m.negotiation_id,
        "from_user_id": m.from_user_id,
        "from_nickname": users[m.from_user_id].nickname if m.from_user_id in users else "",
        "from_is_ai": bool(m.from_user_id in users and users[m.from_user_id].is_ai),
        "kind": m.kind,
        "content": m.content,
        "created_at": m.created_at.isoformat(),
    } for m in rows])


@router.post("/negotiations/{neg_id}/messages")
def send_message(neg_id: int, body: MessageIn, user: User = Depends(trading_user),
                 session: Session = Depends(get_session)):
    neg, _view = _get_participant(neg_id, user, session)
    content = body.content.strip()
    if not content:
        raise BizError("消息内容不能为空")
    if neg.status != "ongoing":
        raise BizError(f"议价会话已{neg.status}，不能继续发消息", code=409, http_status=409)
    row = NegotiationMessage(
        negotiation_id=neg_id, from_user_id=user.id, kind="chat", content=content[:500],
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    view = {
        "id": row.id,
        "negotiation_id": row.negotiation_id,
        "from_user_id": user.id,
        "from_nickname": user.nickname,
        "from_is_ai": bool(user.is_ai),
        "kind": row.kind,
        "content": row.content,
        "created_at": row.created_at.isoformat(),
    }
    _push(str(neg_id), {"type": "chat", **view})
    # 对方为 AI 时调度拟人自动回复（含 typing 指示/策略出价；内部互斥且绝不抛错）
    ai_chat.schedule_ai_reply(neg_id, content, user.id)
    return ok(view, "发送成功")


def _get_participant(neg_id: int, user: User, session: Session) -> tuple[Negotiation, dict]:
    neg = session.get(Negotiation, neg_id)
    if neg is None:
        raise BizError("议价会话不存在", http_status=404)
    if user.id not in (neg.buyer_id, neg.seller_id) and not user.is_admin:
        raise BizError("无权查看该议价会话", code=403, http_status=403)
    return neg, negotiation_view(neg, session, user.id)


def _push(room: str, payload: dict) -> None:
    loop = bus.loop
    if loop:
        hub.broadcast_threadsafe(loop, room, payload)


@router.websocket("/ws/negotiation/{neg_id}")
async def negotiation_ws(ws: WebSocket, neg_id: int, token: str = ""):
    uid = decode_token(token)
    if uid is None:
        await ws.close(code=4401)
        return
    # 参与方鉴权：仅买卖双方与管理员可接入议价室实时流
    with Session(engine) as session:
        neg = session.get(Negotiation, neg_id)
        user = session.get(User, uid)
        allowed = bool(neg and user and (user.is_admin or uid in (neg.buyer_id, neg.seller_id)))
    if not allowed:
        await ws.close(code=4403)
        return
    await hub.connect(str(neg_id), ws)
    try:
        await ws.send_json({"type": "connected", "negotiation_id": neg_id})
        while True:
            await ws.receive_text()  # 客户端心跳/忽略内容
    except WebSocketDisconnect:
        hub.disconnect(str(neg_id), ws)
