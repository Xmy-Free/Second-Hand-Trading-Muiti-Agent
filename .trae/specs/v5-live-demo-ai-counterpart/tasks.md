# V5 增量：AI 虚拟用户 · 一键全自动演示 · 数据与视觉补齐 — 实施计划

> 并行策略：T1–T4 为后端切片（同一子 Agent 串行/分组，避免内核文件争用）；T5–T7 前端切片可与 T2/T3/T4 按既定 API 契约并行；T8 测试在功能切片完成后；T9 独立评审由全新上下文执行。图片素材（≥10 张新商品图）由主控在 T4 期间用图像生成工具产出，子 Agent 只引用文件名。

## API 契约（前后端先行约定，T5/T6 依赖）

- `POST /api/console/demo/start`（admin）→ `{run_id, status:"running"}`，运行中再调返回 409 + 当前 phase
- `GET  /api/console/demo/status`（admin）→ `{status: running|completed|stopped|error, phase, phase_index, phase_count, steps:[{phase,label,status,ts}], result?}`
- `POST /api/console/demo/stop`（admin）→ `{status:"stopped"}`
- WS `/api/console/ws/control` 新增帧：`{type:"demo_phase", data:{run_id, phase, label, state:"start|done|error", index, count, thread_id?, summary?}}`
- `GET  /api/console/traces?limit=40` → `[{thread_id,flow,node,status,summary,ts}]`（环形缓冲）
- `GET  /api/negotiations/{id}/messages`（参与方/admin）→ `[{id,from_user_id,from_nickname,from_is_ai,kind:"chat|system",content,created_at}]`
- `POST /api/negotiations/{id}/messages` `{content}` → 同上单条；WS 房间广播 `{type:"chat",...}` 与 `{type:"typing",from_user_id}`
- AI 用户：`User.is_ai:boolean`、`User.ai_persona:string`；user 视图与议价视图透传 `is_ai/ai_persona`

---

## Task 1: 数据模型与 AI 能力底座
- **Status**: `pending`
- **Priority**: high
- **Depends On**: None
- **Description**:
  - User 增加 `is_ai: bool=False`、`ai_persona: str=""`（SQLModel，SQLite 自动建列；兼容既有库由 init_db 幂等 ALTER 或依赖全新播种）。
  - 新增 `NegotiationMessage` 表：id / negotiation_id(FK) / from_user_id(FK) / kind(chat|system) / content(≤500) / created_at。
  - `llm/client.py` 新增 `chat_text(system, user) -> str|None`（普通对话，超时/异常返回 None；复用重试配置），Key 与异常均不打日志。
  - `rule_llm.py` 新增 AI 议价兜底：`chat_reply(role, item, neg, incoming, last_offers) -> str`（口语化短句，依据纳什价/轮次）与 `next_ai_price(role, neg, offers) -> float|None`（朝保留价单调收敛，返回 None 表示本轮不出价）。
  - 预置 AI 账号写入种子：`AI10001 AI校园摊主`（卖家，persona 数码/教材爽快摊主）、`AI10002 AI同学小北`（买家），均 is_ai=True、可登录密码 123456。
- **Acceptance Criteria Addressed**: AC-4, AC-5, AC-6
- **Test Requirements**:
  - `rule` TR-1.1: `is_ai/ai_persona/NegotiationMessage` 建表成功，种子后可查到 2 个 AI 账号；pytest 证据
  - `rule` TR-1.2: `chat_text` 在无 client 时返回 None；`rule_llm.next_ai_price` 输出序列对买家严格递增、对卖家严格递减且不越保留价；单测断言
- **Notes**: 不得改动 9 Agent 注册名与既有 ACL 契约。

## Task 2: 议价室聊天与 AI 自动回复编排
- **Status**: `pending`
- **Priority**: high
- **Depends On**: Task 1
- **Description**:
  - 新增 `app/services/ai_chat.py`：`maybe_schedule_ai_reply(neg_id, incoming_user_id)`——仅当对方为 is_ai 时，在后台线程中：先 WS 推 `typing`（2–6 秒随机延时），调用 DeepSeek `chat_text`（system prompt 含人设/商品/双方价格/纳什价/轮次/时限，要求一句话口语回复、价格立场一致），失败走 RuleLLM；按策略需要时经 negotiation Agent 合法出价（`do_offer` 同款路径，禁绕规则），成交自动拉起交易流；聊天与系统提示（"AI 接受了 ¥X"）落 NegotiationMessage 并房间广播。
  - routes_negotiation 增加消息列表/发送 REST；发送后触发 AI 回复调度；WS 心跳保持现状。
  - 议价视图/用户视图 schema 透传 is_ai；AI 账号的动作在审计中标 `ai=True` 扩展字段（不破坏既有结构）。
  - 并发与异常保护：AI 回复任务互斥（每个 neg 同一时刻一个回复协程）、异常仅落系统消息不抛出。
- **Acceptance Criteria Addressed**: AC-4, AC-5, AC-6
- **Test Requirements**:
  - `rule` TR-2.1: 非参与方发消息 403；参与方发送后消息可被 GET 拉取；pytest
  - `rule` TR-2.2: monkeypatch 无 LLM 时，向 AI 发送消息后 NegotiationMessage 出现 AI 回复（≤8s）；AI 出价满足单调/保留价；pytest
  - `rule` TR-2.3: 与 AI 的议价可走到 deal 且产生订单（规则路径）；pytest
- **Notes**: 后台线程注意使用 engine 独立 Session；WS 广播走 bus.loop。

## Task 3: 一键演示导演服务与脉冲历史
- **Status**: `pending`
- **Priority**: high
- **Depends On**: Task 1, Task 2
- **Description**:
  - 新增 `app/services/demo_director.py`：单例演示运行器（asyncio.Lock + 运行状态机）。阶段剧本（全程真实 runner/call_agent，带 1.5–4s asyncio 节奏，图调用放 `run_in_executor` 防阻塞循环）：
    1) AI 卖家自然语言发布普通商品（publish flow，approve 直通在售，赋真实图片）；
    2) AI 卖家再发一件违禁品（热得快类，veto 支线，进入冻结/veto 门）；
    3) AI 买家 user_agent.parse_intent + search 语义检索；
    4) 对在售商品发起议价 2–3 轮（user_agent.auto_bid/negotiation，卖家侧为 AI 时走 AI 出价）；
    5) 成交 → trade flow 自动建单；
    6) 风险检查（选择普通信用买家走 wait_pay；演示内自动 resume pay）；
    7) resume 支付 → deliver → receive；
    8) credit 双向评价；
    每阶段 publish `demo_phase`；结束写 result（商品 id/订单号/冲突 id）。
  - routes_console 增加 demo start/status/stop（admin）与 GET traces；node_trace 环形缓冲（deque maxlen=120）挂在 EventBus 旁路（订阅一次或在 emit_node 同时写入）。
- **Acceptance Criteria Addressed**: AC-1, AC-2, AC-3
- **Test Requirements**:
  - `rule` TR-3.1: 隔离 app 中 POST demo/start 返回 running；重复 start 409；stop 后无新阶段；pytest（测试中把节奏延时 patch 为 0）
  - `rule` TR-3.2: 演示 completed 后库内新增 ≥1 on_sale 商品（带图）、≥1 frozen 商品、≥1 已支付/完成订单；pytest
  - `rule` TR-3.3: GET traces 返回按时间倒序事件且非空；非 admin 403；pytest
- **Notes**: 演示中 AI 文本回复在测试环境走 RuleLLM；禁止 print 异常栈，错误进入 status.error。

## Task 4: 种子数据丰富化与素材补齐
- **Status**: `pending`
- **Priority**: high
- **Depends On**: Task 1
- **Description**:
  - 主控生成 ≥10 张新商品图（text_to_image square_hd），存入 frontend/public/images/items/（如 item-skincare/item-snacks/item-calculator2/item-chair/item-ukulele/item-monitor/item-backpack/item-watercup/item-textbook2/item-earbuds2 等），全部电商实拍风。
  - seed.py 扩充：① 管理员 2400320321 作为买家 3 单（unpaid/receiving/reviewed，含议价/评价/审计）、卖家 4–6 件商品（on_sale×3+、dealed）；② AI 卖家 ≥6 件在售带图商品覆盖多类目；③ 其他账号均衡补商品/订单，使在售 ≥30、卖家账号 ≥6、全库订单 8 状态齐全、每个常用账号登录有数据；④ 修复现有无图商品（id40 补图/下架，41/42 类测试品不进入市场即可）；⑤ 所有新商品必须引用真实存在图片。
  - 保持幂等（fresh_seed 才执行 demo flows）与现有 8 实例/5 等待门断言口径；若演示导演的播种期演示不再需要旧 seed_demo_flows 的重复部分，可保留旧流程但保证 instances 数量只增不减。
- **Acceptance Criteria Addressed**: AC-7, AC-8
- **Test Requirements**:
  - `rule` TR-4.1: 全新播种后 管理员订单≥3 商品≥4；20240001–20240005 每个账号 商品+订单总数≥2；pytest
  - `rule` TR-4.2: 市场在售≥30、distinct seller_id≥6、覆盖全部 6+类目；所有 image_url 非空且对应文件存在；pytest
  - `rule` TR-4.3: 订单 8 状态（unpaid/paid/receiving/completed/reviewed/canceled/refunded/appealing）全库各≥1；pytest
- **Notes**: 图片由主控提前生成好，子 Agent 仅写种子引用。

## Task 5: 前端「一键演示」控制台体验
- **Status**: `pending`
- **Priority**: high
- **Depends On**: Task 3（可先按契约并行 mock）
- **Description**:
  - ConsoleView 头部增加世界顶级质感的「▶ 一键演示」主按钮（运行中变为进度态/可停止）；WS 处理 `demo_phase`：阶段时间线浮层（或右栏抽屉）显示 8 阶段进度、当前阶段呼吸高亮、自动切换「编排追踪」并跟随 thread_id 刷新实例、脉冲/消息/冲突在运行期间自动刷新；结束弹出结果总结卡（商品/订单/冲突数量 + 跳转按钮）。
  - AgentOverview 挂载时调用 GET traces 填充脉冲历史；空态仅在真无事件时出现。
  - 遵循 frontend-skill：克制动效（阶段推进过渡、脉冲进入）、信息密度优先、深浅双主题均验证。
- **Acceptance Criteria Addressed**: AC-3, AC-10
- **Test Requirements**:
  - `rule` TR-5.1: `npm run build` 零 TS 错误；无 console 红色错误
  - `rubric` TR-5.2: 演示观看体验；1-5；anchors 见 AC-10；阈值 ≥4；证据为浏览器实拍
- **Notes**: 只改 frontend；WS 帧类型扩展在 useConsoleData.ts。

## Task 6: 议价室 AI 聊天界面
- **Status**: `pending`
- **Priority**: high
- **Depends On**: Task 2（可先按契约并行）
- **Description**:
  - NegotiationRoomView 增加：文本聊天输入框与发送（Enter 发送）、聊天消息气泡（区别于出价气泡与系统居中提示）、历史消息 GET 首屏渲染、WS `chat/typing` 实时处理；对方 AI 显示昵称旁 AI 徽章、「AI 在线」绿点、「AI 正在输入…」气泡动效；自己的 AI 行为（自动出价）以系统提示衔接。
  - 议价列表/市场/卖家信息处对 is_ai 用户显示小型 AI 徽章；全局头像/徽章体系统一。
- **Acceptance Criteria Addressed**: AC-4, AC-11
- **Test Requirements**:
  - `rule` TR-6.1: build 通过；与 AI 的议价室可发送文本并看到回复气泡（实拍）
  - `rubric` TR-6.2: 对话体验；1-5；anchors 见 AC-11；阈值 ≥4；证据为实拍
- **Notes**: 严格区分 chat/offer/system 三类气泡，不破坏既出价流程。

## Task 7: 市场与全站视觉收尾
- **Status**: `pending`
- **Priority**: medium
- **Depends On**: Task 4
- **Description**:
  - 市场页商品卡零无图（图片 404/空时优雅降级不允许出现破图图标）、在售 ≥30 时分页/懒加载流畅；类目筛选与多卖家信息呈现；商品详情、我的商品/订单、首页、登录页按 frontend-skill 做细节级抛光（间距/字阶/hover/空状态）；控制台双主题回归。
- **Acceptance Criteria Addressed**: AC-8, AC-10, AC-11
- **Test Requirements**:
  - `rule` TR-7.1: 市场首屏与两屏滚动内图片全部 naturalWidth>0（浏览器脚本断言）；build 通过
  - `rubric` TR-7.2: 全站视觉一致性；1-5；3=完成度尚可但有粗糙处，5=世界顶尖、无破图/错位/冗余；阈值 ≥4；实拍
- **Notes**: 不新增无关营销页。

## Task 8: 全量回归与浏览器 E2E
- **Status**: `pending`
- **Priority**: high
- **Depends On**: Task 1-7
- **Description**:
  - 新增 pytest：test_demo_director / test_ai_counterpart / test_negotiation_chat / test_console_traces / test_seed_coverage（TR 已列明）。
  - 运行全量 pytest（≥46）、10 剧本 run_all、npm build；清库全新启动（配置 Key 与无 Key 两种模式至少各验证一次 AI/演示路径）。
  - 浏览器 E2E 实拍：一键演示全链路、AI 议价聊天收回复、管理员我的订单/商品、市场 30+ 商品零破图、双主题。
- **Acceptance Criteria Addressed**: AC-1..AC-9
- **Test Requirements**:
  - `rule` TR-8.1: 三条命令全绿输出留档
  - `rule` TR-8.2: E2E 实拍 AC-1/AC-4/AC-7/AC-8 各有截图证据
- **Notes**: qa-engineer 负责新增测试与回归；主控负责 E2E 实拍。

## Task 9: 独立评审（Review Phase）
- **Status**: `pending`
- **Priority**: high
- **Depends On**: Task 8
- **Description**: 全新上下文的独立评审者依据 spec.md/tasks.md 与运行证据逐条复核 AC-1–AC-11，产出 review.md；fail 项回炉为 Issue 后重新实现与复审，直至 pass。
- **Acceptance Criteria Addressed**: 全部
- **Test Requirements**:
  - `rule` TR-9.1: review.md 存在且最新 Review result=pass，每个 rule AC 有独立证据、rubric 有评分与理由
- **Notes**: 实现者自验不算独立证据。
