# 校园二手交易平台 Multi-Agent（简约版 / MVP）— 实施任务队列

> 依据：同目录 `spec.md`。每个任务为可独立验证的垂直切片，按依赖顺序执行；完成定义 = 全部 TR 自检通过 + Completion Evidence。
>
> 执行约定：① 后端 `backend/`（Python 3.11 / FastAPI / SQLModel / LangGraph 1.x），前端 `frontend/`（Vue 3 + TS + Vite + Element Plus 深度定制）；② 阈值集中在 `core/config.py` + `.env`；③ 统一信封 `{code, message, data}`；④ **默认 DeepSeek 真实 LLM（Key 已预置 `.env`），异常自动降级 RuleLLM，移除 Key 也能全跑**；⑤ 后端不做高并发设计，保证功能正确即可；⑥ **前端按 spec FR-11 做到业界顶尖视觉水准**；⑦ **Agent 控制台（FR-10）是与交易主链路同等重要的演示核心**。
>
> 开发分工建议（Trae 自定义智能体）：mas-engineer 负责 agents/graph/kernel/llm；backend-dev 负责 models/services/api；frontend-dev 负责全部前端（含控制台）；qa-engineer 负责剧本与测试。并行任务不得写相同文件。

---

## Task T1: 工程骨架、配置（含预置 Key）、统一响应、前端设计基座

- **Status**: `pending`
- **Priority**: high
- **Depends On**: None
- **Description**:
  - 后端：FastAPI 入口、`core/config.py`（pydantic-settings：JWT、DB 路径、议价 5 轮/120s、支付 15min、信用规则、票权 0.5/0.2/0.3、阈值 ±0.5/0.6、直裁 50 元、`DEEPSEEK_API_KEY/BASE_URL`）、`.env`（**预置作者提供的 Key**）与 `.env.example`、`.gitignore` 确保 `.env` 不入库、SQLite WAL 引擎与会话依赖、统一信封与全局异常、`GET /api/health`（返回 llm_mode）。
  - 前端：Vite+Vue3+TS+Pinia+Router+Element Plus 工程；**设计基座先行**——`src/styles/` 定义 design tokens（色阶/渐变/圆角/间距/阴影/字体阶/动效曲线）、Element Plus 主题深度定制（CSS 变量覆盖）、亮色业务主题 + 深色控制台主题双主题框架、全局动效（过渡/悬停/状态灯呼吸/消息流入 keyframes）、axios 封装、路由与主布局空壳、unplugin-icons(lucide)。
- **Acceptance Criteria Addressed**: AC-10、AC-12
- **Test Requirements**:
  - `rule` TR-1.1：后端启动 `/api/health` 200 且检测到 Key 时 `llm_mode=llm`；前端启动可见带定制主题的布局壳；Evidence：启动输出 + 首页截图。
  - `rule` TR-1.2：删除/注释 Key 后健康检查显示 `llm_mode=rule`，应用仍正常启动；`.env` 不出现在 git 跟踪中；Evidence：配置单测与 `git status` 输出。

## Task T2: 数据模型、建表与种子数据

- **Status**: `pending`
- **Priority**: high
- **Depends On**: T1
- **Description**:
  - 按 spec 第 4 章实现 11 张表（含 `agent_status`），唯一约束（student_no、review 每订单每方向一条）、`item.lock_version`、JSON 默认值。
  - 启动建表 + 幂等种子：作者账号 2400320321、≥3 卖家、≥3 买家（含高风险样本）、≥8 跨类目在售商品（含成交价格口径）、违禁词 ≥20、4 个 Agent 的 `agent_status` 初始记录。
- **Acceptance Criteria Addressed**: AC-2、AC-6
- **Test Requirements**:
  - `rule` TR-2.1：空库初始化后表/种子齐全，高风险样本存在，agent_status 有 4 行；重复播种行数不变；Evidence：初始化输出与断言。

## Task T3: 注册登录与 JWT 鉴权

- **Status**: `pending`
- **Priority**: high
- **Depends On**: T2
- **Description**:
  - `/api/auth/register|login|me`、bcrypt、JWT（uid/is_admin）、当前用户/管理员/冻结拦截依赖。
  - 前端：高完成度登录/注册页（品牌视觉、渐变/玻璃卡片、微动效，作为视觉标杆页）、auth store、路由守卫。
- **Acceptance Criteria Addressed**: AC-2、AC-12
- **Test Requirements**:
  - `rule` TR-3.1：401/403/冻结拦截接口测试通过；种子账号登录走查成功；Evidence：httpx 测试 + 登录页截图。

## Task T4: Agent 通信内核——ACL、黑板、基类、注册表、事件推送总线

- **Status**: `pending`
- **Priority**: high
- **Depends On**: T2
- **Description**:
  - `kernel/acl.py`：ACL Pydantic 模型（全部字段与 performative 枚举、confidence 区间）；`kernel/blackboard.py`：LangGraph 类型化 State；`agents/base.py`：Agent 基类（含 display_name/avatar/capabilities/llm_mode/状态与计数钩子）；`kernel/registry.py`：注册、发现、状态/计数更新、暂停/恢复。
  - `kernel/events.py`：**运行事件推送总线**（内存 pub/sub + 异步广播）——消息事件、节点轨迹事件、计数增量、状态变更、冲突事件，供 `/ws/control` 订阅；事件同时落库（acl_message/conflict_event/audit_log）。
- **Acceptance Criteria Addressed**: AC-7、AC-11、AC-10
- **Test Requirements**:
  - `rule` TR-4.1：非法消息四类构造被拒并有错误码；示例 Agent 注册即可被发现调用；Evidence：pytest。
  - `rule` TR-4.2：发布一条消息事件后，两个测试订阅者均收到且事件已落库；Evidence：pub/sub 测试。

## Task T5: LLM 适配层与 RuleLLM 兜底

- **Status**: `pending`
- **Priority**: high
- **Depends On**: T4
- **Description**:
  - `llm/client.py`：openai SDK 指向 DeepSeek（base_url/key/model 全配置化），结构化输出：超时/非法 JSON 重试 1 次后抛降级异常；调用成功/降级均更新 `agent_status.llm_mode` 与事件。
  - `llm/rule_llm.py`：商品结构化、审核判定（违禁词→veto/高风险→人工/通过+依据置信度）、建议价、议价让步与推荐理由模板。真实与规则输出结构完全一致。
- **Acceptance Criteria Addressed**: AC-6、AC-8
- **Test Requirements**:
  - `rule` TR-5.1：预置 Key 下对真实接口做一次最小连通调用（失败不阻塞，自动跳过并记录）；无 Key/注入超时/非法 JSON 时四类策略均返回合法结构；Evidence：单测输出（标记真实调用为可选）。

## Task T6: LangGraph 主编排图、检查点、节点轨迹与 interrupt

- **Status**: `pending`
- **Priority**: high
- **Depends On**: T4、T5
- **Description**:
  - `graph/builder.py`：主图节点槽位（发布审核流/搜索/议价流/交易支付流/申诉流），SQLite checkpointer；**每个节点进入/退出发布轨迹事件**（thread_id、节点名、状态、IO 摘要、时间）；两个人工 interrupt 点（商品复核、纠纷/风险终裁）及 `Command(resume=...)` 写回契约；流程实例（thread_id 与商品/会话/订单关联）查询服务。
- **Acceptance Criteria Addressed**: AC-5、AC-11
- **Test Requirements**:
  - `rule` TR-6.1：占位节点跑通"请求→interrupt→resume→结束"，轨迹事件序列完整，重启后可按 thread_id 恢复检查点；Evidence：图执行测试。

## Task T7: GoodsAgent——发布、建议价、审核三档与 veto

- **Status**: `pending`
- **Priority**: high
- **Depends On**: T6
- **Description**:
  - `agents/goods.py`：结构化+建议价+审核（approve/reject/manual/veto + 置信度 + 逐条依据），写 item 状态与 C8 事件；驳回重提一次限制；下架（仅未锁定）；消息/计数/状态全部走注册表与事件总线。
  - REST：items 发布/列表/详情/我的/重提/下架；接入主图节点。
- **Acceptance Criteria Addressed**: AC-1、AC-2、AC-8
- **Test Requirements**:
  - `rule` TR-7.1：正常→在售；违禁词→冻结+依据含命中词；高风险词→待人工；第二次重提被拒；冻结商品任何上架途径被拒；Evidence：接口测试（C8 构造）。

## Task T8: TradeAgent（上）——搜索推荐与匹配理由

- **Status**: `pending`
- **Priority**: high
- **Depends On**: T7
- **Description**:
  - 多条件检索在售商品，相关性/成色/价格/信用综合排序，逐条匹配理由，无结果宽松建议；`GET /api/market/items`、`GET /api/market/recommend`。
- **Acceptance Criteria Addressed**: AC-2
- **Test Requirements**:
  - `rule` TR-8.1：过滤、信用权重、理由非空、无结果建议四类断言通过；Evidence：接口测试。

## Task T9: TradeAgent（下）——议价、纳什价、WebSocket 议价室

- **Status**: `pending`
- **Priority**: high
- **Depends On**: T8
- **Description**:
  - 议价服务：建会话（保密保留价）、单调让步校验、交集成交、5 轮/120 秒超时、纳什价、授权区间自动出价、越界/成交"需确认"二次提交、风险提示；offer 落库；僵持一级协商记 C1；全程事件推送。
  - WS `/ws/negotiation/{id}`（JWT、出价/状态/倒计时广播、他人禁连）；REST 发起/详情/历史/确认。
- **Acceptance Criteria Addressed**: AC-4
- **Test Requirements**:
  - `rule` TR-9.1：交集成交/非单调拒绝/僵持 terminated+同类推荐/纳什值正确四类断言；WS 鉴权与广播测试；Evidence：单测。

## Task T10: OrderCreditAgent（上）——锁、状态机、抢单裁决、沙箱支付

- **Status**: `pending`
- **Priority**: high
- **Depends On**: T9
- **Description**:
  - 事务内乐观锁建单（token、pay_deadline）；抢单按"时间→信用→支付完成"裁决唯一成交，其余冲突错误+替代推荐+C2 事件；**仅保证功能正确，不做性能设计**。
  - 状态机全迁移（3.3）、非法迁移拒绝、支付幂等、超时懒判定+定时扫描取消释放、交付/收货；支付前风险钩子（T11 接入，默认 low）。
  - REST：下单/支付/交付/收货/取消/列表。
- **Acceptance Criteria Addressed**: AC-2、AC-3
- **Test Requirements**:
  - `rule` TR-10.1：两路并发恰一单成功且失败方收冲突码与推荐；非法迁移/超时释放/重复支付幂等断言；Evidence：pytest（两路即可，不做压力测试）。

## Task T11: OrderCreditAgent（下）——评价、信用分、风险意见

- **Status**: `pending`
- **Priority**: high
- **Depends On**: T10
- **Description**:
  - 双向评价唯一约束、信用规则（第 4 章）、new/high_risk 标签、订单→已评价；风险意见（level/confidence/basis）供支付钩子与议价提示；裁决扣分接口。
  - REST：评价提交/列表、我的信用。
- **Acceptance Criteria Addressed**: AC-2、AC-5
- **Test Requirements**:
  - `rule` TR-11.1：好评/差评/责任扣分/重复评价/高风险样本意见（high、conf≥0.6、依据非空）断言通过；Evidence：单测。

## Task T12: Coordinator——冲突检测、加权投票、申诉、管理员接口

- **Status**: `pending`
- **Priority**: high
- **Depends On**: T11
- **Description**:
  - 规则检测统一入口；意见检测→三方加权投票（spec 6.3）→放行/拦截取消/转人工 interrupt，明细写 conflict_event 并推送；申诉证据包+规则裁决（≤50 元直裁）/转人工+终裁写回驱动迁移与扣分。
  - REST：moderation 复核队列/通过/维持冻结（veto 无放行路径，解除冻结须理由）、appeals 终裁、`GET /api/audit/orders/{id}` 时间线；agent 暂停/恢复动作（T13 也用）。
- **Acceptance Criteria Addressed**: AC-1、AC-5
- **Test Requirements**:
  - `rule` TR-12.1：构造三种加权分对应三种订单去向；申诉两路径迁移正确；veto 商品放行接口不存在/被拒；审计时间线含审核/出价/投票/裁决；Evidence：接口+状态断言。

## Task T13: 控制台后端——实例/轨迹/检查点/事件查询与 /ws/control

- **Status**: `pending`
- **Priority**: high
- **Depends On**: T12
- **Description**:
  - REST `/api/console/agents`（列表含状态/模式/计数/最近活跃）、`POST /agents/{name}/pause|resume`、`/instances`（在途+历史流程实例，关联订单/会话/商品）、`/instances/{thread_id}/trace`（节点轨迹与 IO 摘要）、`/instances/{thread_id}/checkpoints`、`/conflicts`（筛选+详情含投票明细）、`/messages`（ACL 历史查询过滤）。
  - WS `/ws/control`（管理员鉴权）：订阅 T4 事件总线五类推送，心跳保活。
  - 保证业务执行时各事件齐备（消息、节点进出、计数、agent 状态、冲突）。
- **Acceptance Criteria Addressed**: AC-11
- **Test Requirements**:
  - `rule` TR-13.1：跑一次含 C6 的完整业务后，上述接口返回数据与库记录一致；WS 收到五类事件；暂停的专家处理新业务时返回挂起提示且实例状态可见；Evidence：接口测试 + WS 报文存档。

## Task T14: 前端——卖家端页面（发布/商品/议价/交付/评价）

- **Status**: `pending`
- **Priority**: medium
- **Depends On**: T7、T10
- **Description**:
  - 发布页（自然语言框→结构化卡片动画呈现→建议价徽标→可编辑确认）、我的商品（状态时间线/逐条审核依据/仅一次重提/下架）、卖家议价室（T16 共建组件的本角色视图）、订单交付确认、收到的评价。
  - 严格执行 FR-11：骨架屏、空状态、Toast、卡片层次与微动效；禁止裸用默认 Element 样式。
- **Acceptance Criteria Addressed**: AC-9、AC-12
- **Test Requirements**:
  - `rubric` TR-14.1：各状态正确呈现且依据可读，视觉达到定制设计水准；scale 1–5；anchors 1=毛坯/3=整洁模板化/5=一线产品级；threshold ≥4；Evidence：逐页截图。

## Task T15: 前端——买家端页面（市场/详情/下单/订单/评价/信用/申诉）

- **Status**: `pending`
- **Priority**: medium
- **Depends On**: T8、T11、T12
- **Description**:
  - 市场页（精致筛选栏、商品卡网格、匹配理由标签、无结果插画建议）、详情页、下单与模拟支付页、我的订单（状态步骤条 + 按状态出现操作）、评价页、我的信用（分数环/标签/历史）、申诉入口与表单。
- **Acceptance Criteria Addressed**: AC-9、AC-12
- **Test Requirements**:
  - `rubric` TR-15.1：买家旅程无死路、操作反馈完整、视觉品质；scale 1–5；anchors 同 TR-14.1；threshold ≥4；Evidence：端到端走查截图。

## Task T16: 前端——议价室组件（买卖双视角共用）

- **Status**: `pending`
- **Priority**: high
- **Depends On**: T9
- **Description**:
  - 对话流式布局：双方出价气泡（含依据）、纳什参考价徽标、轮次指示、120s 环形倒计时、对方风险提示条、自动出价开关；越界出价/接受前弹玻璃质感确认框；WS 断线重连提示；破裂结果卡 + 同类商品推荐横滑；消息流入动效。
- **Acceptance Criteria Addressed**: AC-4、AC-9、AC-12
- **Test Requirements**:
  - `rule` TR-16.1：出价→成交全交互可用，归零触发破裂态，确认框拦截越界出价；Evidence：浏览器操作截图与 WS 记录。
  - `rubric` TR-16.2：议价室视觉与动效品质；scale 1–5；threshold ≥4；Evidence：截图评审。

## Task T17: 前端——管理员复核台与终裁台

- **Status**: `pending`
- **Priority**: medium
- **Depends On**: T12
- **Description**:
  - 复核台（存疑+veto 队列、逐条依据与置信度条、通过/维持冻结；解除冻结需理由弹窗）、终裁台（证据包时间线、协调者建议、维持/退款表单），提交后状态即时刷新并留痕提示。
- **Acceptance Criteria Addressed**: AC-5、AC-9
- **Test Requirements**:
  - `rule` TR-17.1：终裁后订单状态与信用分正确变化；veto 商品无放行上架按钮；Evidence：前后状态对比截图。

## Task T18: 前端——多 Agent 管理控制台（深色指挥中心，最高视觉优先级）

- **Status**: `pending`
- **Priority**: high
- **Depends On**: T13
- **Description**:
  - 深色主题"Mission Control"布局（发光状态色、网格/星点背景、玻璃面板），五个区块：
    1. **Agent 总览**：4 张 Agent 卡（图标/职责/能力标签/呼吸状态灯/llm-rule 引擎标/消息任务计数滚动/最近活跃/暂停-恢复开关），全局顶部系统健康条；
    2. **编排追踪**：自定义 SVG 主链路节点图（含冲突与人工分支），实例选择器；已走节点发光点亮+连线流光动画、当前节点呼吸、悬停节点显示 IO 摘要摘要 popover；底部实例节点时间线；
    3. **消息总线**：实时流列表（performative 彩色徽标、sender→receiver 流向、置信度条、时间），过滤器（Agent/performative/conversation），点击展开 payload JSON 视图；新消息滑入动效；
    4. **黑板快照**：State 树形/JSON 双视图切换 + 检查点列表；
    5. **冲突中心**：事件时间线（C1/C2/C6/C8 色标筛选）+ 投票详情卡（三方票值/权重/置信度 + ECharts 加权分仪表条 + 结论）+ 人工待办跳转复核/终裁台。
  - 全部数据走 `/api/console` + `/ws/control`；WS 断连重连与实时角标。
- **Acceptance Criteria Addressed**: AC-11、AC-12
- **Test Requirements**:
  - `rule` TR-18.1：执行业务（含 C6/C8）时五个区块实时反应正确：计数增长、节点点亮路径与实际一致、消息无遗漏可展开、快照与库一致、投票卡数字与 conflict_event 一致；暂停/恢复生效；Evidence：操作录屏/截图 + 接口比对。
  - `rubric` TR-18.2：控制台视觉达到"指挥中心"氛围与一线产品级质感（暗色克制、发光有节、信息密而不乱）；scale 1–5；anchors 1=普通后台表格/3=整洁暗色页/5=令人印象深刻的演示级控制台；threshold ≥4；Evidence：全区块截图评审。

## Task T19: 冲突剧本运行器与 C1–C4 剧本

- **Status**: `pending`
- **Priority**: high
- **Depends On**: T13
- **Description**:
  - `scenarios/runner.py`：种子准备→驱动图/服务→断言→对照表；`run_all.py` 汇总退出码。
  - C1 僵持、C2 两路并发抢单、C6 高风险投票（放行/转人工两分支）、C8 违禁 veto 与覆盖尝试；输出逐步 ACL/节点/事件轨迹（控制台可同步观察）。
- **Acceptance Criteria Addressed**: AC-1、AC-3、AC-4、AC-5、AC-6
- **Test Requirements**:
  - `rule` TR-19.1：`python -m app.scenarios.run_all` 退出码 0，spec 6.5 期望逐条 PASS；无 Key 环境同样通过；Evidence：两次运行输出存档。

## Task T20: 测试套件与质量门禁

- **Status**: `pending`
- **Priority**: high
- **Depends On**: T19
- **Description**:
  - ACL 契约、E2E 主链路全步骤、抢单一致性（两路）、LLM 超时/非法 JSON 注入后一致性、控制台接口/WS 五类事件、鉴权越权、`rule_mode` 全量回归 mark；类型注解与 ruff。
- **Acceptance Criteria Addressed**: AC-2、AC-6、AC-7、AC-8、AC-10、AC-11
- **Test Requirements**:
  - `rule` TR-20.1：有 Key（真实调用可 mock/skip 外部依赖）与清空 Key 两种环境 pytest 全绿；故障注入后表一致性断言通过；Evidence：pytest 输出。
  - `rubric` TR-20.2：agents/kernel/graph/services 分层无越界（agents 不碰 HTTP 层、控制台只读经 kernel）；scale 1–5；threshold ≥4；Evidence：代码审查记录。

## Task T21: 一键启动与 README、答辩演示串场

- **Status**: `pending`
- **Priority**: medium
- **Depends On**: T14、T15、T16、T17、T18、T20
- **Description**:
  - Windows 一键脚本（初始化+种子→uvicorn→vite）；README：环境要求、双模式（有/无 Key）、种子账号（含 2400320321 与管理员）、剧本命令、**5 分钟答辩演示动线**（登录→发布违禁品看 veto 与控制台拦截→正常发布→议价→高风险投票→控制台讲消息流/节点图/黑板→终裁）。
  - 干净目录验证。
- **Acceptance Criteria Addressed**: AC-6、AC-10、AC-11
- **Test Requirements**:
  - `rule` TR-21.1：干净副本按 README 完成一次全流程演示动线；Evidence：执行记录与关键截图。

---

## 任务—验收标准覆盖矩阵

| AC | 覆盖任务 |
|---|---|
| AC-1 veto 不可覆盖 | T7、T12、T19 |
| AC-2 主链路端到端 | T2、T3、T7、T10、T11、T20 |
| AC-3 并发抢单 | T10、T19 |
| AC-4 议价规则 | T9、T16、T19 |
| AC-5 投票与人工闭环 | T6、T11、T12、T17、T19 |
| AC-6 双引擎模式 | T1、T5、T19、T20、T21 |
| AC-7 ACL 契约 | T4、T20 |
| AC-8 LLM 故障无脏状态 | T5、T7、T20 |
| AC-9 前端旅程可用性 | T14、T15、T16、T17 |
| AC-10 工程质量 | T1、T4、T6、T20、T21 |
| AC-11 Agent 管理控制台 | T4、T6、T13、T18、T20、T21 |
| AC-12 顶尖视觉 | T1、T3、T14、T15、T16、T18 |

## 执行波次（自动推进，无需逐波次审批）

1. **波次 1**：T1–T3 → 能登录、有数据、视觉基座确立。
2. **波次 2**：T4–T6 → 消息/黑板/注册表/事件总线/编排图内核。
3. **波次 3**：T7–T12 → 4 Agent 业务能力与冲突机制全通。
4. **波次 4**：T13 → 控制台后端可观测接口。
5. **波次 5（可并行）**：T14+T15+T16+T17+T18 前端各页（文件不重叠，控制台 T18 最高优先）。
6. **波次 6**：T19–T21 → 剧本、测试门禁、一键启动与答辩动线。
