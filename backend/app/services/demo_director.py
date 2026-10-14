"""一键全自动演示导演（FR-101/FR-102）。

模块级单例 director：asyncio.Lock 保证同时只有一个演示；8 个阶段全部走真实
runner/call_agent 链路（发布审核→veto 支线→语义搜索→AI 双边议价→成交建单→
支付→交付收货→互评）。同步图/ACL 调用一律 run_in_executor，严禁阻塞事件循环；
每阶段 start/done 经 bus 推送 demo_phase，控制台 WS 与节点脉冲实时联动。
"""
from __future__ import annotations

import asyncio
import logging
import random
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from sqlmodel import Session, select

from app.core import database as db_mod
from app.kernel.dispatch import call_agent
from app.kernel.events import bus
from app.llm import rule_llm
from app.models import AuditLog, Item, Negotiation, Order, User
from app.services import ai_chat

logger = logging.getLogger("demo_director")

AI_SELLER_NO = "AI10001"
AI_BUYER_NO = "AI10002"
NORMAL_IMAGE = "/images/items/item-mouse.jpg"
BANNED_TITLE = "热得快电热棒 大功率3000W"
BANNED_DESC = "出个热得快电热棒，宿舍烧水很快，大功率3000W，带电源线，25元出。"

PHASES: list[tuple[str, str]] = [
    ("publish_normal", "AI 摊主发布普通商品并通过审核上架"),
    ("publish_banned", "违禁品发布触发安全 veto 冻结支线"),
    ("search", "AI 买家自然语言意图解析与语义搜索"),
    ("negotiate", "AI 买家与 AI 卖家多轮议价"),
    ("deal", "最后一拍成交：建单预占锁与风险检查"),
    ("pay", "自动沙箱支付"),
    ("fulfill", "卖家面交交付与买家确认收货"),
    ("review", "双方五星信用评价"),
]


class DemoRunningError(RuntimeError):
    def __init__(self, phase: str) -> None:
        self.phase = phase
        super().__init__(f"演示正在运行中：{phase}")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class DemoDirector:
    """演示状态机：idle | running | completed | stopped | error。"""

    # 节奏间隔（秒），测试可 patch 为 0
    pace_min: float = 1.5
    pace_max: float = 3.0

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._task: asyncio.Task | None = None
        self._stop_requested = False
        self.run_id: str = ""
        self.status: str = "idle"
        self.phase: str = ""
        self.phase_index: int = 0
        self.steps: list[dict[str, Any]] = []
        self.result: dict[str, Any] | None = None
        self.message: str = ""

    # ---------------- 对外管控 ----------------
    async def start(self, admin_id: int) -> dict[str, Any]:
        async with self._lock:
            if self.status == "running" and self._task and not self._task.done():
                raise DemoRunningError(self.phase)
            self.run_id = f"demo-{uuid.uuid4().hex[:10]}"
            self.status = "running"
            self.phase = PHASES[0][0]
            self.phase_index = 0
            self.steps = []
            self.result = None
            self.message = ""
            self._stop_requested = False
            self._task = asyncio.create_task(self._run(admin_id))
            return {"run_id": self.run_id, "status": "running"}

    def stop(self) -> dict[str, Any]:
        if self.status == "running":
            self._stop_requested = True
            self.status = "stopped"
            self.message = "管理员手动停止演示"
        return {"run_id": self.run_id, "status": "stopped"}

    def snapshot(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "phase": self.phase,
            "phase_index": self.phase_index,
            "phase_count": len(PHASES),
            "steps": list(self.steps),
            "result": self.result,
            "message": self.message,
        }

    # ---------------- 运行主体 ----------------
    async def _run(self, admin_id: int) -> None:
        loop = asyncio.get_running_loop()
        ctx: dict[str, Any] = {"admin_id": admin_id}
        try:
            for index, (phase, label) in enumerate(PHASES, start=1):
                if self._stop_requested or self.status == "stopped":
                    self._finish_stopped()
                    return
                self.phase = phase
                self.phase_index = index
                self._emit(phase, label, "start", index,
                           thread_id=ctx.get("trade_thread") or ctx.get("veto_thread_id"))
                handler = self._handlers()[phase]
                summary, thread_id = await loop.run_in_executor(
                    None, self._exec_phase, handler, ctx)
                ctx["last_summary"] = summary
                if thread_id:
                    ctx["last_thread"] = thread_id
                self._emit(phase, label, "done", index,
                           thread_id=thread_id, summary=summary)
                if index < len(PHASES):
                    await self._pace()

            self.status = "completed"
            self.result = {
                "item_id": ctx.get("item_id"),
                "kept_item_id": ctx.get("kept_item_id"),
                "item_title": ctx.get("item_title"),
                "negotiation_id": ctx.get("negotiation_id"),
                "order_id": ctx.get("order_id"),
                "conflict_ids": [],
                "veto_thread_id": ctx.get("veto_thread_id"),
            }
        except Exception as exc:  # noqa: BLE001 - 异常不致死服务，traceback 仅服务端
            logger.exception("demo director failed")
            self.status = "error"
            self.message = f"{type(exc).__name__}: {exc}"[:200]
            label = dict(PHASES).get(self.phase, self.phase)
            try:
                self._emit(self.phase, label, "error", self.phase_index,
                           summary="演示阶段异常，已安全中止（详见服务端日志）")
            except Exception:  # noqa: BLE001
                logger.exception("emit error phase failed")

    def _exec_phase(self, handler: Callable[[dict[str, Any]], tuple[str, str | None]],
                    ctx: dict[str, Any]) -> tuple[str, str | None]:
        return handler(ctx)

    async def _pace(self) -> None:
        if self.pace_max <= 0:
            await asyncio.sleep(0)
            return
        await asyncio.sleep(random.uniform(self.pace_min, self.pace_max))

    def _finish_stopped(self) -> None:
        self.status = "stopped"
        self._emit(self.phase, "演示已停止", "done", self.phase_index,
                   summary="管理员停止了演示，已保留此前产生的全部数据")

    def _emit(self, phase: str, label: str, state: str, index: int,
              thread_id: str | None = None, summary: str | None = None) -> None:
        step = {
            "phase": phase, "label": label, "state": state, "index": index,
            "count": len(PHASES), "ts": _now_iso(),
            "thread_id": thread_id, "summary": summary or "",
        }
        self.steps.append(step)
        bus.publish("demo_phase", {"run_id": self.run_id, **step})

    def _handlers(self) -> dict[str, Callable[[dict[str, Any]], tuple[str, str | None]]]:
        return {
            "publish_normal": self._phase_publish_normal,
            "publish_banned": self._phase_publish_banned,
            "search": self._phase_search,
            "negotiate": self._phase_negotiate,
            "deal": self._phase_deal,
            "pay": self._phase_pay,
            "fulfill": self._phase_fulfill,
            "review": self._phase_review,
        }

    # ---------------- 阶段实现（同步，线程位执行） ----------------
    def _users(self) -> tuple[int, int, str]:
        with Session(db_mod.engine) as session:
            seller = session.exec(select(User).where(User.student_no == AI_SELLER_NO)).first()
            buyer = session.exec(select(User).where(User.student_no == AI_BUYER_NO)).first()
            if seller is None or buyer is None:
                raise RuntimeError("AI 演示账号未播种（AI10001/AI10002）")
            return int(seller.id), int(buyer.id), seller.student_no

    def _phase_publish_normal(self, ctx: dict[str, Any]) -> tuple[str, str | None]:
        from app.graph.runner import runner

        seller_id, _buyer_id, _ = self._users()
        tag = f"{random.choice('ABCDEFGHJK')}{random.randint(1, 99)}"
        title = f"95新罗技M330无线静音鼠标 {tag}"
        desc = ("95新罗技无线静音鼠标，按键几乎静音，图书馆/宿舍用不打扰别人，"
                "含原装接收器和一节新电池，外观很新，无拆修。")
        r = runner.start("publish", user_id=seller_id,
                         title=title, description=desc, price=45.0)
        tid = r["thread_id"]
        # 模型与规则意见相左时可能停在人工复核门：演示中以管理员身份审批通过
        if r["status"] == "waiting" and (r.get("pending_human") or {}).get("kind") == "item_review":
            r = runner.resume(tid, {"action": "approve",
                                    "admin_id": str(ctx["admin_id"]),
                                    "basis": "一键演示：商品合规，人工复核通过"})
        item_id = int(r["state"]["item_id"])
        # 再发布一件不参与本次成交的新品：演示结束后市场仍留有演示生成的在售商品（AC-1）
        tag2 = f"{random.choice('ABCDEFGHJK')}{random.randint(1, 99)}"
        keep_title = f"95新罗技K380蓝牙办公键盘 便携静音 {tag2}"
        r2 = runner.start("publish", user_id=seller_id,
                          title=keep_title,
                          description=("95新罗技K380蓝牙键盘，轻薄便携，按键静音适合图书馆，"
                                       "两节七号电池续航很久，成色新无拆修。"),
                          price=58.0)
        keep_tid = r2["thread_id"]
        if r2["status"] == "waiting" and (r2.get("pending_human") or {}).get("kind") == "item_review":
            r2 = runner.resume(keep_tid, {"action": "approve",
                                          "admin_id": str(ctx["admin_id"]),
                                          "basis": "一键演示：商品合规，人工复核通过"})
        keep_item_id = int(r2["state"]["item_id"])
        with Session(db_mod.engine) as session:
            item = session.get(Item, item_id)
            if item is None:
                raise RuntimeError("演示商品建档失败")
            if item.status != "on_sale":
                raise RuntimeError(f"普通商品未正常上架，当前状态：{item.status}")
            item.image_url = NORMAL_IMAGE
            kept = session.get(Item, keep_item_id)
            if kept is None or kept.status != "on_sale":
                raise RuntimeError("演示留库商品未正常上架")
            kept.image_url = "/images/items/item-keyboard.jpg"
            ctx_item_title = item.title
            session.commit()
        ctx["item_id"] = item_id
        ctx["kept_item_id"] = keep_item_id
        ctx["item_title"] = ctx_item_title
        return f"《{ctx_item_title}》审核通过已上架（¥45，真实商品图已补齐），另有一件留库新品在售", tid

    def _phase_publish_banned(self, ctx: dict[str, Any]) -> tuple[str, str | None]:
        from app.graph.runner import runner

        seller_id, _buyer_id, _ = self._users()
        with Session(db_mod.engine) as session:
            existing = session.exec(select(Item).where(
                Item.seller_id == seller_id,
                Item.title.like("%热得快%"),
                Item.status == "frozen",
            ).order_by(Item.id.desc())).first()
            item_id = int(existing.id) if existing else None

        if item_id is not None:
            tid = self._find_veto_thread(item_id)
            ctx["veto_thread_id"] = tid
            ctx["banned_item_id"] = item_id
            return f"引用既有 frozen 违禁品实例（item {item_id}，veto 待办保留）", tid

        r = runner.start("publish", user_id=seller_id,
                         title=BANNED_TITLE, description=BANNED_DESC, price=25.0)
        tid = r["thread_id"]
        item_id = int(r["state"]["item_id"])
        if r["status"] != "waiting" or (r.get("pending_human") or {}).get("kind") != "veto_review":
            raise RuntimeError("违禁品未按预期停在 veto_review 门")
        with Session(db_mod.engine) as session:
            item = session.get(Item, item_id)
            if item is None or item.status != "frozen":
                raise RuntimeError("违禁品未被安全否决冻结")
        # 故意不 resume：作为控制台 veto 人工待办保留
        ctx["veto_thread_id"] = tid
        ctx["banned_item_id"] = item_id
        return "安全 veto 已冻结商品，流程停在人工终裁门（待办保留，不 resume）", tid

    def _phase_search(self, ctx: dict[str, Any]) -> tuple[str, str | None]:
        _seller_id, buyer_id, _ = self._users()
        intent = call_agent(
            "user_agent", f"demo-intent-{buyer_id}-{time.time_ns()}",
            {"action": "parse_intent", "user_id": buyer_id,
             "text": "想收一个无线鼠标，预算 50 元以内"},
            summary="演示：AI 买家自然语言购买意图结构化",
        )
        if intent.payload.get("intent") != "search":
            raise RuntimeError(f"意图解析异常：{intent.payload.get('intent')}")
        reply = call_agent(
            "search", f"demo-search-{buyer_id}-{time.time_ns()}",
            {"action": "search", "keyword": "鼠标", "max_price": 50, "user_id": buyer_id},
            summary="演示：语义检索在售鼠标并按相关性排序",
        )
        items = reply.payload.get("items", [])
        hit = next((it for it in items if it.get("id") == ctx.get("item_id")), None)
        if hit is None:
            raise RuntimeError("演示商品未出现在搜索结果中")
        return f"意图识别成功，搜索到 {len(items)} 件在售鼠标，命中演示商品《{hit.get('title')}》", None

    def _phase_negotiate(self, ctx: dict[str, Any]) -> tuple[str, str | None]:
        _seller_id, buyer_id, _ = self._users()
        item_id = ctx["item_id"]
        # 买家保留价设在可成交区间（标价 45：卖家保留价 38.3，纳什 42.2）
        buyer_reserve, first_offer = 46.0, 36.0
        started = call_agent(
            "negotiation", f"demo-neg-start-{item_id}-{time.time_ns()}",
            {"action": "start_negotiation", "buyer_id": buyer_id, "item_id": item_id,
             "buyer_reserve": buyer_reserve, "first_offer": first_offer},
            summary="演示：AI 买家发起议价",
        ).payload
        if not started.get("ok"):
            raise RuntimeError(f"发起议价失败：{started.get('error')}")
        neg_id = int(started["negotiation_id"])
        ctx["negotiation_id"] = neg_id
        nash = float(started["nash_price"])

        with Session(db_mod.engine) as session:
            neg = session.get(Negotiation, neg_id)
            sr, br = neg.seller_reserve, neg.buyer_reserve
            item = session.get(Item, item_id)
            item_title = item.title
            seller_id = int(neg.seller_id)

        ai_chat.add_message(neg_id, buyer_id,
                            "学长好，这个鼠标我想收，36 行吗，学生党预算不多～",
                            kind="chat", broadcast=False)
        # 合法的 2-3 轮让步序列（单调 + 保留价内），最后一拍留给 deal 阶段
        s1 = round(nash + max(1.0, (nash - sr) * 0.2), 1)
        b2 = round(first_offer + (nash - first_offer) * 0.55, 1)
        s2 = round(nash, 1)
        sequence = [
            (seller_id, s1, "seller", "卖家第一轮要价"),
            (buyer_id, b2, "buyer", "买家第二轮加价"),
            (seller_id, s2, "seller", "卖家让至纳什参考价"),
        ]
        last_buyer, last_seller = first_offer, None
        for uid, price, role, _label in sequence:
            last_seller = price if role == "seller" else last_seller
            last_buyer = price if role == "buyer" else last_buyer
            reply_text = rule_llm.chat_reply(
                role, item_title,
                {"nash_price": nash, "buyer_reserve": br, "seller_reserve": sr},
                _label, last_buyer, last_seller,
            )
            ai_chat.add_message(neg_id, uid, reply_text, kind="chat", broadcast=False)
            resp = call_agent(
                "negotiation", f"demo-offer-{neg_id}-{time.time_ns()}",
                {"action": "offer", "negotiation_id": neg_id, "user_id": uid,
                 "price": price, "confirm": True},
                summary=f"演示：AI {('卖家' if role == 'seller' else '买家')}出价 ¥{price:g}",
            ).payload
            if not resp.get("ok") or resp.get("status") != "ongoing":
                raise RuntimeError(f"演示议价序列异常：{resp.get('status')} {resp.get('error')}")
        ctx["final_buyer_price"] = s2  # 买家下一拍应价即成交
        return f"议价进行 3 轮：买 {first_offer:g}→{b2:g}，卖 {s1:g}→{s2:g}（纳什 ¥{nash:g}）", None

    def _phase_deal(self, ctx: dict[str, Any]) -> tuple[str, str | None]:
        _seller_id, buyer_id, _ = self._users()
        neg_id = ctx["negotiation_id"]
        deal_price = ctx["final_buyer_price"]
        ai_chat.add_message(neg_id, buyer_id, f"行吧，{deal_price:g} 成交，什么时候方便面交？",
                            kind="chat", broadcast=False)
        resp = call_agent(
            "negotiation", f"demo-deal-{neg_id}-{time.time_ns()}",
            {"action": "offer", "negotiation_id": neg_id, "user_id": buyer_id,
             "price": deal_price, "confirm": True},
            summary=f"演示：买家应价 ¥{deal_price:g} 成交",
        ).payload
        if resp.get("status") != "deal":
            raise RuntimeError(f"议价未按预期成交：{resp.get('status')} {resp.get('error')}")
        order_id = resp.get("order_id")
        if not order_id:
            raise RuntimeError("成交后交易流未建单")
        with Session(db_mod.engine) as session:
            order = session.get(Order, int(order_id))
            if order is None:
                raise RuntimeError("订单不存在")
            if order.status != "unpaid":
                raise RuntimeError(f"建单后状态异常：{order.status}")
            tid = order.graph_thread_id
        from app.graph.runner import runner

        snap = runner.get_state(tid)
        if snap["status"] != "waiting" or (snap.get("pending_human") or {}).get("kind") != "wait_pay":
            raise RuntimeError("交易流未按预期停在等待支付门")
        ctx["order_id"] = int(order_id)
        ctx["trade_thread"] = tid
        ai_chat.add_message(neg_id, None,
                            f"议价达成，成交价 ¥{resp.get('deal_price'):g}，订单已创建并预占商品。",
                            kind="system", broadcast=False)
        return f"成交 ¥{resp.get('deal_price'):g}：预占锁建单成功，普通信用买家进入待支付门", tid

    def _phase_pay(self, ctx: dict[str, Any]) -> tuple[str, str | None]:
        from app.graph.runner import runner

        tid = ctx["trade_thread"]
        order_id = ctx["order_id"]
        runner.resume(tid, {"action": "pay", "admin_id": str(ctx["admin_id"]),
                            "basis": "一键演示：沙箱自动支付", "user_id": self._users()[1]})
        with Session(db_mod.engine) as session:
            order = session.get(Order, order_id)
            if order.status != "paid":
                raise RuntimeError(f"支付后状态异常：{order.status}")
        return "沙箱支付完成，订单进入待收货", tid

    def _phase_fulfill(self, ctx: dict[str, Any]) -> tuple[str, str | None]:
        seller_id, buyer_id, _ = self._users()
        order_id = ctx["order_id"]
        d = call_agent(
            "order", f"demo-deliver-{order_id}",
            {"action": "deliver", "order_id": order_id, "user_id": seller_id,
             "actor_type": "user"},
            summary="演示：AI 卖家确认校内面交交付",
        ).payload
        if not d.get("ok"):
            raise RuntimeError(f"交付失败：{d.get('error')}")
        r = call_agent(
            "order", f"demo-receive-{order_id}",
            {"action": "receive", "order_id": order_id, "user_id": buyer_id,
             "actor_type": "user"},
            summary="演示：AI 买家确认收货",
        ).payload
        if not r.get("ok") or r.get("status") != "completed":
            raise RuntimeError(f"收货失败：{r.get('status')} {r.get('error')}")
        return "面交交付与买家确认收货完成，订单已完成", ctx.get("trade_thread")

    def _phase_review(self, ctx: dict[str, Any]) -> tuple[str, str | None]:
        seller_id, buyer_id, _ = self._users()
        order_id = ctx["order_id"]
        reviews = [
            (buyer_id, seller_id, "鼠标成色和描述一致，面交很准时，好评！"),
            (seller_id, buyer_id, "买家沟通礼貌，付款爽快，欢迎下次再来～"),
        ]
        for from_id, _to_id, content in reviews:
            resp = call_agent(
                "credit", f"demo-review-{order_id}-{from_id}",
                {"action": "review", "order_id": order_id, "from_user_id": from_id,
                 "score": 5, "content": content},
                summary="演示：交易双方五星互评",
            ).payload
            if not resp.get("ok"):
                raise RuntimeError(f"评价失败：{resp.get('error')}")
        with Session(db_mod.engine) as session:
            order = session.get(Order, order_id)
            final_status = order.status
        return f"双向五星评价完成，订单状态：{final_status}，全链路演示结束", ctx.get("trade_thread")

    # ---------------- 工具 ----------------
    def _find_veto_thread(self, item_id: int) -> str | None:
        """在近期 publish 流程实例中找到指向该 frozen 商品的等待中 veto 门。"""
        from app.graph.runner import runner

        try:
            with Session(db_mod.engine) as session:
                rows = session.exec(select(AuditLog).where(
                    AuditLog.action == "flow_start"
                ).order_by(AuditLog.id.desc()).limit(30)).all()
                tids = [r.graph_thread_id for r in rows
                        if (r.detail or {}).get("flow") == "publish" and r.graph_thread_id]
            for tid in tids:
                try:
                    snap = runner.get_state(tid)
                except KeyError:
                    continue
                pending = snap.get("pending_human") or {}
                payload = pending.get("payload") or {}
                if (snap["status"] == "waiting" and pending.get("kind") == "veto_review"
                        and payload.get("item_id") == item_id):
                    return tid
        except Exception:  # noqa: BLE001 - 引用失败不影响阶段事件推送
            logger.exception("find veto thread failed")
        return None


director = DemoDirector()
