"""AI 虚拟用户议价自动回复编排（FR-203/FR-204/FR-205）。

- 仅当议价对方为 is_ai 账号时调度；每个议价会话同一时刻只允许一个回复线程；
- 后台 daemon 线程：先广播 typing → 2.5–5s 随机延时 → DeepSeek chat_text 拟人回复，
  失败/无 Key 走 rule_llm.chat_reply 确定性兜底；
- 策略出价一律经 negotiation Agent 的 ACL offer 路径（单调让步/保留价/成交/交易流
  hook 全部复用既有逻辑，AI 不可能发出非法出价）；
- 任何异常只写服务端静默日志，绝不向调用方抛错、不打扰用户。
"""
from __future__ import annotations

import logging
import random
import threading
import time
from typing import Any

from sqlmodel import Session, select

from app.core import database as db_mod
from app.kernel.dispatch import call_agent
from app.kernel.events import bus
from app.kernel.hub import hub
from app.llm import rule_llm
from app.llm.client import llm_client
from app.models import Item, Negotiation, NegotiationMessage, Offer, User

logger = logging.getLogger("ai_chat")

# 打字延时（秒），模块级常量便于测试 patch
TYPING_MIN = 2.5
TYPING_MAX = 5.0

_active_lock = threading.Lock()
_active_negs: set[int] = set()


# ---------------------------------------------------------------------------
# 对外调度入口
# ---------------------------------------------------------------------------
def schedule_ai_reply(neg_id: int, incoming_text: str, incoming_user_id: int) -> None:
    """真人发送聊天/出价后调度 AI 回复；对方非 AI / 会话已结束 / 已有回复进行中则直接返回。"""
    try:
        with Session(db_mod.engine) as session:
            neg = session.get(Negotiation, neg_id)
            if neg is None or neg.status != "ongoing":
                return
            if incoming_user_id not in (neg.buyer_id, neg.seller_id):
                return
            ai_uid = neg.seller_id if incoming_user_id == neg.buyer_id else neg.buyer_id
            ai_user = session.get(User, ai_uid)
            if ai_user is None or not ai_user.is_ai:
                return
            ai_id = int(ai_uid)
            text = (incoming_text or "")[:500]
            human_id = int(incoming_user_id)
    except Exception:  # noqa: BLE001 - 调度探测失败绝不影响用户主操作
        logger.exception("schedule_ai_reply probe failed: neg=%s", neg_id)
        return

    with _active_lock:
        if neg_id in _active_negs:
            return  # 同会话串行：防止并发回复叠加
        _active_negs.add(neg_id)

    t = threading.Thread(
        target=_run_ai_reply_safe, args=(neg_id, ai_id, human_id, text),
        name=f"ai-reply-{neg_id}", daemon=True,
    )
    t.start()


# ---------------------------------------------------------------------------
# 消息落库 / 广播（供后台线程与演示导演复用）
# ---------------------------------------------------------------------------
def message_view(row: NegotiationMessage, user: User | None) -> dict[str, Any]:
    return {
        "id": row.id,
        "negotiation_id": row.negotiation_id,
        "from_user_id": row.from_user_id,
        "from_nickname": user.nickname if user else "",
        "from_is_ai": bool(user and user.is_ai),
        "kind": row.kind,
        "content": row.content,
        "created_at": row.created_at.isoformat(),
    }


def add_message(neg_id: int, from_user_id: int | None, content: str,
                *, kind: str = "chat", broadcast: bool = True,
                session: Session | None = None) -> NegotiationMessage:
    """落一条议价消息并可选房间广播；可复用外层会话（随其事务提交）。"""
    content = (content or "")[:500]
    own = session is None
    s = session or Session(db_mod.engine)
    try:
        row = NegotiationMessage(
            negotiation_id=neg_id, from_user_id=from_user_id, kind=kind, content=content,
        )
        s.add(row)
        s.commit()
        s.refresh(row)
        user = s.get(User, from_user_id) if from_user_id is not None else None
        view = message_view(row, user)
    finally:
        if own:
            s.close()
    if broadcast:
        _push(neg_id, {"type": "chat", **view})
    return row


def _push(neg_id: int, payload: dict[str, Any]) -> None:
    loop = bus.loop
    if loop is not None:
        hub.broadcast_threadsafe(loop, str(neg_id), payload)


# ---------------------------------------------------------------------------
# 回复文本生成（DeepSeek → RuleLLM 兜底）
# ---------------------------------------------------------------------------
def generate_reply_text(role: str, ai_user: User, item: Item, neg: Negotiation,
                        offers: list[Offer], incoming: str,
                        planned_price: float | None = None) -> str:
    last_buyer = max((o.price for o in offers if o.from_role == "buyer"), default=None)
    last_seller = min((o.price for o in offers if o.from_role == "seller"), default=None)
    own_count = sum(1 for o in offers if o.from_role == role)
    neg_info = {
        "nash_price": neg.nash_price,
        "buyer_reserve": neg.buyer_reserve,
        "seller_reserve": neg.seller_reserve,
        "round_count": own_count + 1,
        "planned_price": planned_price,
    }
    system_prompt = _build_system_prompt(
        role, ai_user, item, neg, last_buyer, last_seller, own_count + 1, planned_price)
    user_prompt = f"对方发来：{incoming or '（等待你的回应）'}\n请只用一到两句口语化中文回复。"
    text = llm_client.chat_text(system_prompt, user_prompt, temperature=0.8, max_tokens=200)
    if not text:
        text = rule_llm.chat_reply(
            role, item.title, neg_info, incoming, last_buyer, last_seller,
        )
    return (text or "稍等哈，我看一下～").strip().replace("\n", " ")[:500]


def _build_system_prompt(role: str, ai_user: User, item: Item, neg: Negotiation,
                         last_buyer_price: float | None, last_seller_price: float | None,
                         round_no: int, planned_price: float | None = None) -> str:
    from datetime import datetime, timezone

    role_cn = "卖家" if role == "seller" else "买家"
    created = neg.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    elapsed = max(0, int((datetime.now(timezone.utc) - created).total_seconds()))
    remaining_seconds = max(0, neg.deadline_seconds - elapsed)
    remaining_rounds = max(0, neg.max_rounds - round_no + 1)
    action_hint = ""
    if planned_price is not None:
        action_hint = (
            f"\n你本轮已经决定{('让出' if role == 'seller' else '出价')} ¥{planned_price:g}，"
            "回复里要自然地提到这个价格（先说价格再出价），不要说与该价格矛盾的数字。"
        )
    return (
        f"你正在校园二手交易平台的议价聊天里扮演一个真实的中国大学生{role_cn}。\n"
        f"你的身份人设：{ai_user.ai_persona or ai_user.nickname}。\n"
        f"商品：《{item.title}》，描述：{item.description or '（无补充描述）'}，"
        f"标价 ¥{item.price:g}。\n"
        f"买家保留价（最高预算）：¥{neg.buyer_reserve:g}；"
        f"卖家保留价（最低底价）：¥{neg.seller_reserve:g}；纳什参考价：¥{(neg.nash_price or 0):g}。\n"
        f"买家最近出价：{('¥' + format(last_buyer_price, 'g')) if last_buyer_price is not None else '暂无'}；"
        f"卖家最近要价：{('¥' + format(last_seller_price, 'g')) if last_seller_price is not None else '暂无'}。\n"
        f"议价上限 {neg.max_rounds} 轮、总时限 {neg.deadline_seconds} 秒"
        f"（剩余约 {remaining_rounds} 轮 / {remaining_seconds} 秒）。"
        f"{action_hint}\n"
        "要求：\n"
        "1. 真实中国大学生微信聊天语气，一到两句话，可适当使用语气词但不超过 2 个；\n"
        "2. 价格立场必须与你的买卖角色一致：卖家可以小刀但要守住卖家保留价，"
        "买家预算有限、不得超过买家保留价；\n"
        "3. 不要输出 JSON、不要加引号、不要换行；\n"
        "4. 绝不暴露你是 AI/模型/系统或任何 AI 供应商信息，不承诺系统外能力，"
        "内容必须是健康的校园交易语境。"
    )


# ---------------------------------------------------------------------------
# 后台回复线程
# ---------------------------------------------------------------------------
def _run_ai_reply_safe(neg_id: int, ai_uid: int, human_uid: int, incoming: str) -> None:
    try:
        _run_ai_reply(neg_id, ai_uid, human_uid, incoming)
    except Exception:  # noqa: BLE001 - 兜底：任何异常都不打扰用户，仅服务端静默日志
        logger.exception("AI reply failed: neg=%s ai=%s", neg_id, ai_uid)
    finally:
        with _active_lock:
            _active_negs.discard(neg_id)


def _run_ai_reply(neg_id: int, ai_uid: int, human_uid: int, incoming: str) -> None:
    # 1) 正在输入指示
    _push(neg_id, {"type": "typing", "from_user_id": ai_uid, "negotiation_id": neg_id})
    time.sleep(random.uniform(TYPING_MIN, TYPING_MAX))

    with Session(db_mod.engine) as session:
        neg = session.get(Negotiation, neg_id)
        if neg is None or neg.status != "ongoing":
            return
        ai_user = session.get(User, ai_uid)
        if ai_user is None or not ai_user.is_ai:
            return
        item = session.get(Item, neg.item_id)
        offers = session.exec(select(Offer).where(
            Offer.negotiation_id == neg_id).order_by(Offer.id)).all()
        role = "seller" if ai_uid == neg.seller_id else "buyer"
        last_buyer = max((o.price for o in offers if o.from_role == "buyer"), default=None)
        last_seller = min((o.price for o in offers if o.from_role == "seller"), default=None)
        own_count = sum(1 for o in offers if o.from_role == role)
        chat_turns = len(session.exec(select(NegotiationMessage).where(
            NegotiationMessage.negotiation_id == neg_id,
            NegotiationMessage.from_user_id == ai_uid,
            NegotiationMessage.kind == "chat",
        )).all())
        round_hint = max(own_count + 1, chat_turns + 1)

        # 2) 策略出价先算（DeepSeek 路径也以规则函数给价为准，保证合法性）
        planned_price = rule_llm.next_ai_price(
            role, neg.buyer_reserve, neg.seller_reserve, neg.nash_price,
            last_buyer, last_seller, round_hint, neg.max_rounds,
        )
        nash_price, max_rounds = neg.nash_price, neg.max_rounds

        # 3) 拟人文本围绕本轮出价生成（DeepSeek 失败走 RuleLLM）
        text = generate_reply_text(role, ai_user, item, neg, offers, incoming, planned_price)

    # 4) 落库 + 广播聊天消息（先说话再出价）
    add_message(neg_id, ai_uid, text, kind="chat")

    # 5) 经 negotiation Agent 的标准 ACL offer 路径出价（单调/保留价/成交/交易流 hook 全复用）
    if planned_price is None:
        return
    price = planned_price

    reply = call_agent(
        "negotiation", f"ai-offer-{neg_id}-{time.time_ns()}",
        {"action": "offer", "negotiation_id": neg_id, "user_id": ai_uid,
         "price": price, "confirm": True,
         "basis": f"AI {('卖家' if role == 'seller' else '买家')}策略出价（规则约束内，纳什参考 ¥{nash_price:g}）"},
        summary=f"AI {('卖家' if role == 'seller' else '买家')}自动出价 ¥{price:g}，最大 {max_rounds} 轮",
    )
    data = reply.payload
    if not data.get("ok"):
        # 非法/超时/超轮被后端拒收：信任后端裁决，安静放弃本次出价（文本回复已送达）
        logger.info("AI offer rejected by negotiation: neg=%s data=%s", neg_id, data)
        return

    if data.get("status") == "deal":
        deal_price = data.get("deal_price")
        with Session(db_mod.engine) as session:
            ai_user = session.get(User, ai_uid)
            ai_name = ai_user.nickname if ai_user else "AI"
        add_message(
            neg_id, None,
            f"{ai_name} 接受了 ¥{deal_price:g}，议价达成，订单已创建并进入交易流程。",
            kind="system",
        )
        _broadcast_update(neg_id, human_uid, data)


def _broadcast_update(neg_id: int, viewer_id: int, data: dict[str, Any]) -> None:
    """成交后向房间推送与出价路由同构的 update 帧（以真人视角构造 my_role）。"""
    try:
        with Session(db_mod.engine) as session:
            from app.schemas.negotiation import negotiation_view

            neg = session.get(Negotiation, neg_id)
            view = negotiation_view(neg, session, viewer_id)
        view["flow_status"] = data.get("flow_status")
        view["order_id"] = data.get("order_id")
        _push(neg_id, {"type": "update", "detail": view,
                       "status": data.get("status"), "deal_price": data.get("deal_price")})
    except Exception:  # noqa: BLE001
        logger.exception("broadcast update failed: neg=%s", neg_id)
