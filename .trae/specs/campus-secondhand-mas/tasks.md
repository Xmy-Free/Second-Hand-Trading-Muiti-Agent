# 校园二手交易平台 Multi-Agent 系统 — 实施任务队列（WBS 落地）

> 对应 `spec.md`（v1.0）与 `wbs.html`。任务按依赖排序为可独立交付的纵向切片；编码需在需求文档、技术栈、WBS **经人工确认后** 开始。

## AC 覆盖索引

| AC | 覆盖任务 |
|---|---|
| AC-1 安全否决 | T11、T20 |
| AC-2 主链路贯通 | T10–T16、T24、T25、T29 |
| AC-3 并发抢单 | T14、T29 |
| AC-4 议价规则 | T13、T18、T29 |
| AC-5 三级阶梯 | T18、T19、T20、T26 |
| AC-6 SSOT 纠正 | T5、T17 |
| AC-7 八场景≥10 剧本 | T28 |
| AC-8 无 Key 可演 | T6、T29 |
| AC-9 可插拔 | T5、T8 |
| AC-10 轨迹回放 | T7、T26 |
| AC-11 ACL 协议 | T5 |
| AC-12 LLM 故障 | T6、T29 |
| AC-13 前端 rubric | T23–T27 |
| AC-14 可解释 rubric | T11、T12、T13、T16 |
| AC-15 工程质量 rubric | T2、T29、T31 |

---

## Task T1: 详细设计说明书（角色卡片 / ACL 协议 / 状态机 / ER）
- **Status**: `pending`
- **Priority**: high
- **Depends On**: None
- **WBS**: 1.2–1.5
- **Description**:
  - 输出 9 张 Agent 角色卡片：职责、输入/输出契约（Pydantic Schema）、工具、异常码。
  - 定稿 ACL 消息规范（performative 枚举、对话ID、置信度、超时、异常码表）。
  - 输出 ER 关系设计与订单/商品状态机迁移表、冲突检测规则清单、仲裁评分卡与效用/投票参数表（配置化）。
- **Acceptance Criteria Addressed**: AC-11、AC-15
- **Test Requirements**:
  - `rule` TR-1.1: `docs/design.md`（或等价文件）存在且包含 9 张角色卡、ACL 字段表、异常码表、ER 与状态机章节；证据：文件与评审记录。
  - `rule` TR-1.2: 后续任务引用的消息/状态/异常名称均能在该文档找到唯一定义；证据：交叉核对结果。

## Task T2: 前后端工程骨架与配置
- **Status**: `pending`
- **Priority**: high
- **Depends On**: T1
- **WBS**: 2.1
- **Description**:
  - 后端 FastAPI + Uvicorn 骨架、分层目录、健康检查、pydantic-settings（`.env`：LLM 开关/Key/BaseURL、权重、议价轮次/时限、金额阈值）、ruff。
  - 前端 Vue3+TS+Vite+Pinia+Element Plus 骨架、API 封装占位、Vite 代理。
- **Acceptance Criteria Addressed**: AC-15
- **Test Requirements**:
  - `rule` TR-2.1: 后端 `uvicorn` 启动并返回健康检查 200；前端 `npm run dev` 启动并显示占位首页；证据：启动命令输出与页面截图。
  - `rule` TR-2.2: 不配置任何 LLM Key 时应用正常启动且模式标记为 mock；证据：启动日志。

## Task T3: 数据模型与种子数据
- **Status**: `pending`
- **Priority**: high
- **Depends On**: T2
- **WBS**: 2.2、2.4
- **Description**:
  - SQLModel 表：users、items、negotiations、orders、reviews、cases、messages(轨迹)、conflict_events、agent_profiles；SQLite WAL 初始化。
  - 种子脚本：含 2400320321 在内的买卖账号、管理员、多类目商品与历史成交价、初始信用分。
- **Acceptance Criteria Addressed**: AC-2、NFR-7
- **Test Requirements**:
  - `rule` TR-3.1: 全新环境执行初始化后可查询到种子账号与商品，外键与状态字段完整；证据：seed 脚本输出与数据库断言。
  - `rule` TR-3.2: items 含版本号/锁字段，订单状态枚举与 spec 4.3 一致；证据：模型单测。

## Task T4: 认证与角色鉴权
- **Status**: `pending`
- **Priority**: high
- **Depends On**: T3
- **WBS**: 2.3
- **Description**: 注册/登录接口、bcrypt 哈希、JWT 签发与校验依赖、买家/卖家/管理员角色守卫、冻结账号拦截。
- **Acceptance Criteria Addressed**: FR-1、NFR-4
- **Test Requirements**:
  - `rule` TR-4.1: 正确口令获得 JWT 并访问受保护接口；错误口令 401；越权访问管理员接口 403；证据：httpx 接口测试。

## Task T5: Agent 通信内核（黑板 / ACL / 基类 / 注册表）
- **Status**: `pending`
- **Priority**: high
- **Depends On**: T2
- **WBS**: 3.1–3.3
- **Description**:
  - 类型化全局黑板 State（商品池、会话、订单、冲突事件、Agent 健康位）；所有写入经 reducer 保持 SSOT。
  - ACL 消息总线与 Pydantic Schema 校验；Agent 基类（name/capabilities/handle 契约）与注册表（注册/发现/可插拔）。
- **Acceptance Criteria Addressed**: AC-6、AC-9、AC-11
- **Test Requirements**:
  - `rule` TR-5.1: 缺字段/非法 performative 的消息被 Schema 拒绝并返回异常码；证据：消息校验单测。
  - `rule` TR-5.2: 注册一个示例 Agent 后可经注册表发现并被调用，协调者核心代码零改动；证据：可插拔示例测试。
  - `rule` TR-5.3: 注入与黑板冲突的私有状态时以黑板为准纠正，并产生偏差来源记录；证据：C7 雏形单测。

## Task T6: LLM 适配层 + RuleLLM 确定性兜底
- **Status**: `pending`
- **Priority**: high
- **Depends On**: T5
- **WBS**: 3.4
- **Description**:
  - OpenAI 兼容客户端（默认 DeepSeek，可切 BaseURL/模型）；全部输出走 Pydantic 结构化模型。
  - RuleLLM：意图识别、分类成色、审核判定、议价让步、仲裁裁决的确定性规则实现。
  - 调用链：结构化输出 → Schema 校验 → 最多 N 次重试 → 降级 RuleLLM 或抛人工信号。
- **Acceptance Criteria Addressed**: AC-8、AC-12、NFR-6
- **Test Requirements**:
  - `rule` TR-6.1: 未配置 Key 时审核/意图/议价等调用均由 RuleLLM 返回合法结构化结果；证据：无 Key 测试。
  - `rule` TR-6.2: 注入非法 JSON 与超时异常后，系统重试并降级，不抛出未处理异常、不写脏状态；证据：故障注入测试（mock transport）。

## Task T7: 检查点持久化与决策轨迹服务
- **Status**: `pending`
- **Priority**: high
- **Depends On**: T5
- **WBS**: 3.5
- **Description**: 接入 LangGraph Checkpointer（SQLite）；按对话/交易线程持久化每步状态与消息；提供轨迹查询与回放数据接口。
- **Acceptance Criteria Addressed**: AC-10、NFR-8
- **Test Requirements**:
  - `rule` TR-7.1: 一次完成的议价/纠纷可按线程拉取完整逐步消息、结论、置信度与升级路径；证据：轨迹查询测试。

## Task T8: 协调管理 Agent 与主编排图
- **Status**: `pending`
- **Priority**: high
- **Depends On**: T5、T7
- **WBS**: 4.1
- **Description**: LangGraph 主图（发布→审核→上架→搜索→议价→锁定下单→支付交付→评价），条件边、异常分支、Agent 编排与健康监控占位；与专家节点契约对接。
- **Acceptance Criteria Addressed**: AC-9、NFR-5
- **Test Requirements**:
  - `rule` TR-8.1: 使用桩专家节点可走通主图 happy path，状态按预期迁移；证据：图执行单测。

## Task T9: 用户代理 Agent
- **Status**: `pending`
- **Priority**: high
- **Depends On**: T6、T8
- **WBS**: 4.2
- **Description**: 自然语言意图解析、买家/卖家画像与保留价维护、授权区间内自动出价、越界/成交前确认信号（human-in-the-loop）。
- **Acceptance Criteria Addressed**: FR-2、AC-2
- **Test Requirements**:
  - `rule` TR-9.1: 给定典型自然语言样本输出正确意图与结构化字段；超出授权价的出价产生确认请求而非自动发送；证据：Agent 单测。

## Task T10: 商品管理 Agent 与发布服务
- **Status**: `pending`
- **Priority**: high
- **Depends On**: T8、T3
- **WBS**: 4.3（商品部分）
- **Description**: 描述结构化、类目/成色标签、基于历史价的建议区间、商品草稿/上下架与库存状态维护。
- **Acceptance Criteria Addressed**: FR-3、AC-2
- **Test Requirements**:
  - `rule` TR-10.1: 商品发布后生成标准档案并进入`待审核`；建议价区间引用种子历史价；下架未锁定商品成功；证据：服务测试。

## Task T11: 内容审核 Agent（含安全否决）
- **Status**: `pending`
- **Priority**: high
- **Depends On**: T10、T6
- **WBS**: 4.3（审核部分）、5.5（否决）
- **Description**: 违禁词/规则库 + LLM 双判定，输出 通过/驳回/人工复核 + 置信度 + 逐条依据；命中违禁/欺诈输出 veto 冻结；驳回允许补材料重提一次。
- **Acceptance Criteria Addressed**: AC-1、AC-14、NFR-4
- **Test Requirements**:
  - `rule` TR-11.1: 含违禁词样本必被 veto 且商品冻结，任何上游放行不能覆盖（提供对抗调用测试）；证据：C8 测试。
  - `rubric` TR-11.2: 维度=审核结论可解释性（依据条目+置信度）；scale 1–5；1=仅结论 3=部分依据 5=逐条依据清晰；阈值 ≥4；证据：10 条样本审核结果评审。

## Task T12: 搜索推荐 Agent
- **Status**: `pending`
- **Priority**: high
- **Depends On**: T10
- **WBS**: 4.4
- **Description**: 多条件检索仅在售商品；相关性/成色/价格/信用/画像加权排序；输出可展示匹配理由；排序方案接受目标相容性检查（C5 接口预留，T19 接通）。
- **Acceptance Criteria Addressed**: FR-5
- **Test Requirements**:
  - `rule` TR-12.1: 已下架/冻结商品不出现在结果；每条结果携带非空匹配理由；证据：服务测试。

## Task T13: 议价谈判 Agent（双边多轮）
- **Status**: `pending`
- **Priority**: high
- **Depends On**: T9、T6
- **WBS**: 4.5、5.2（纳什/让步）
- **Description**: 双边会话状态机；单调让步、时间压力、纳什参考价计算；轮次/时限控制；成交或破裂（推荐同类）；出价序列全程留痕。
- **Acceptance Criteria Addressed**: AC-4、AC-14
- **Test Requirements**:
  - `rule` TR-13.1: 买家出价序列不下降/卖家要价不上升（违反即拒）；进入价格区间即成交；超轮次/超时即破裂并产生同类推荐；纳什参考价数值与公式一致；证据：多组议价剧本断言。

## Task T14: 交易履约 Agent（锁 / 状态机 / 回滚）
- **Status**: `pending`
- **Priority**: high
- **Depends On**: T13
- **WBS**: 4.6
- **Description**: 成交预占锁（锁令牌+乐观版本+超时点）；抢单三优先裁决（时间→信用→支付）；订单状态机；沙箱支付、超时取消释放、支付失败回滚、交付确认。
- **Acceptance Criteria Addressed**: AC-2、AC-3、NFR-2
- **Test Requirements**:
  - `rule` TR-14.1: 并发两路同时下单同一商品，断言恰一成功、商品`已成交`、败者获得释放与替代推荐，无超卖；证据：asyncio 并发测试。
  - `rule` TR-14.2: 支付超时/失败后订单`已取消`、锁释放、商品回`在售`，可再次成交；非法状态迁移被拒；证据：状态机测试。

## Task T15: 信用评价 Agent
- **Status**: `pending`
- **Priority**: high
- **Depends On**: T14
- **WBS**: 4.7
- **Description**: 双向评价聚合（一单仅一次）、信用分动态规则、风险标签、对审核/议价/订单/仲裁的带置信度风险意见。
- **Acceptance Criteria Addressed**: FR-8、AC-2
- **Test Requirements**:
  - `rule` TR-15.1: 完成订单可双向评价且分数按规则更新；重复评价被拒；高风险用户产生风险标签；证据：服务测试。

## Task T16: 纠纷仲裁 Agent
- **Status**: `pending`
- **Priority**: high
- **Depends On**: T15、T7
- **WBS**: 4.8
- **Description**: 申诉受理、证据包聚合（档案/议价/订单节点/评价/信用）、规则库裁决书（责任+依据条目+执行方案+置信度）、超阈值/涉安全升级标记、联动信用处罚。
- **Acceptance Criteria Addressed**: FR-9、AC-14
- **Test Requirements**:
  - `rule` TR-16.1: 典型货不对板案件生成结构化裁决书且证据包完整；超阈值案件带"升级人工"标记；证据：仲裁单测。
  - `rubric` TR-16.2: 维度=裁决书质量（责任划分/依据/可执行性）；scale 1–5；1=无依据 3=结构完整但依据笼统 5=引用具体证据条目；阈值 ≥4；证据：样例裁决书评审。

## Task T17: 冲突检测引擎（四类检测）
- **Status**: `pending`
- **Priority**: high
- **Depends On**: T8
- **WBS**: 5.1
- **Description**: 规则检测（状态机/锁）、意见检测（置信度接近的冲突结论）、目标检测（提案相容性）、信息检测（SSOT 比对），统一产出 ConflictEvent。
- **Acceptance Criteria Addressed**: AC-6
- **Test Requirements**:
  - `rule` TR-17.1: 四类各至少一个触发用例产出带类型/参与方/置信度的 ConflictEvent；证据：检测单测。

## Task T18: 一级对等协商策略
- **Status**: `pending`
- **Priority**: high
- **Depends On**: T17、T13
- **WBS**: 5.2
- **Description**: ≤3 轮限时自动让步、纳什参考价建议、规则解释与补材料；成功恢复主流程，失败升级二级；覆盖 C1、C3 一级段。
- **Acceptance Criteria Addressed**: AC-4、AC-5
- **Test Requirements**:
  - `rule` TR-18.1: 僵持剧本中一级策略在限额内运行；成功留痕恢复，失败产生升级事件；证据：C1/C3 剧本断言。

## Task T19: 二级协调仲裁（效用函数 + 加权投票）
- **Status**: `pending`
- **Priority**: high
- **Depends On**: T17
- **WBS**: 5.3
- **Description**: 全局效用函数评分（权重配置化，默认 0.25/0.20/0.30/0.15/−0.10）；相关 Agent 票权×置信度投票；出具裁决书；覆盖 C4、C5、C6；分歧过大升级三级。
- **Acceptance Criteria Addressed**: AC-5
- **Test Requirements**:
  - `rule` TR-19.1: C5 剧本中满意度不达标方案被否决并要求重排；C6 中风险票按权重影响结果且分歧过大时暂缓支付并升级；效用计算可复现（同输入同输出）；证据：仲裁单测与数值快照。

## Task T20: 三级人工兜底、冻结与 Agent 熔断
- **Status**: `pending`
- **Priority**: high
- **Depends On**: T18、T19
- **WBS**: 5.4、5.5
- **Description**: LangGraph `interrupt` 挂起三级事件并冻结相关订单/商品；人工裁决恢复图并写回 SSOT、联动信用；异常 Agent 熔断隔离与协调者代管；保证 veto 最高优先。
- **Acceptance Criteria Addressed**: AC-1、AC-5、NFR-4
- **Test Requirements**:
  - `rule` TR-20.1: 三级案件图执行在 interrupt 挂起且资金/商品操作被冻结；注入人工裁决后状态正确恢复并留痕；证据：human-in-the-loop 测试。
  - `rule` TR-20.2: 熔断某专家后其职责被代管，主流程不中断且产生告警事件；证据：熔断测试。

## Task T21: REST API 全量接口
- **Status**: `pending`
- **Priority**: high
- **Depends On**: T11、T12、T14、T15、T16、T20
- **WBS**: 6.1、6.2、6.4–6.6
- **Description**: 商品/审核、搜索、订单/支付/交付、评价/信用、申诉仲裁、管理员（复核/终裁/熔断/审计）接口；统一响应与错误码；OpenAPI 文档。
- **Acceptance Criteria Addressed**: FR-12、AC-2
- **Test Requirements**:
  - `rule` TR-21.1: 每个接口具备成功/未授权/校验失败用例并通过；证据：httpx 接口测试集。

## Task T22: 议价 WebSocket 实时通道
- **Status**: `pending`
- **Priority**: high
- **Depends On**: T21
- **WBS**: 6.3
- **Description**: 议价室 WS：出价/接受/拒绝/系统提示（纳什价、轮次、倒计时、僵局/破裂）、Agent 状态推送；断线重连恢复会话。
- **Acceptance Criteria Addressed**: FR-6
- **Test Requirements**:
  - `rule` TR-22.1: 两客户端经 WS 完成一轮双方出价且顺序与状态一致；超时事件被推送；证据：WS 集成测试。

## Task T23: 前端脚手架 / 登录 / 主布局
- **Status**: `pending`
- **Priority**: high
- **Depends On**: T4
- **WBS**: 7.1
- **Description**: 路由守卫、Pinia 鉴权、三角色布局导航、统一请求拦截、Element Plus 主题。
- **Acceptance Criteria Addressed**: AC-13
- **Test Requirements**:
  - `rule` TR-23.1: 种子账号登录后按角色进入对应首页；令牌失效自动跳登录；证据：页面走查截图。

## Task T24: 卖家端页面
- **Status**: `pending`
- **Priority**: high
- **Depends On**: T21、T22
- **WBS**: 7.2、7.5（卖家部分）、7.6
- **Description**: 自然语言发布（展示结构化结果/建议价）、我的商品（审核状态与依据/驳回补材料）、议价室、订单交付、收到评价、发起申诉与裁决书查看。
- **Acceptance Criteria Addressed**: AC-2、AC-13、AC-14
- **Test Requirements**:
  - `rule` TR-24.1: 卖家可完成发布→查收审核依据→议价→确认交付→查看评价/发起申诉全操作；证据：逐页截图与接口联调记录。

## Task T25: 买家端页面
- **Status**: `pending`
- **Priority**: high
- **Depends On**: T21、T22
- **WBS**: 7.3–7.5
- **Description**: 市场搜索与推荐理由、详情、议价室（纳什参考价/轮次/倒计时/越界确认）、下单与模拟支付、确认收货、我的订单、评价、我的信用。
- **Acceptance Criteria Addressed**: AC-2、AC-4、AC-13
- **Test Requirements**:
  - `rule` TR-25.1: 买家可完成搜索→议价成交→支付→收货→评价→查看信用分；破裂时可见同类推荐；证据：端到端走查截图（AC-2 前端证据）。
  - `rubric` TR-25.2: 维度=议价室信息清晰度（出价序列/纳什价/轮次倒计时/依据）；scale 1–5；阈值 ≥4；证据：界面评审。

## Task T26: 管理员人工工作台
- **Status**: `pending`
- **Priority**: high
- **Depends On**: T21、T20
- **WBS**: 7.7
- **Description**: 待办队列（人工复核/三级终裁/安全事件）、证据包查看、终裁写回、Agent 熔断/接管、审计与轨迹回放视图。
- **Acceptance Criteria Addressed**: FR-12、AC-5、AC-10、AC-13
- **Test Requirements**:
  - `rule` TR-26.1: 三级案件可在工作台完成取证→终裁→写回，订单状态随之变化；任意交易可回放决策轨迹；证据：操作录屏/截图与数据断言。

## Task T27: 黑板监控大屏（P1）
- **Status**: `pending`
- **Priority**: medium
- **Depends On**: T26
- **WBS**: 7.8
- **Description**: ECharts 实时黑板状态、冲突事件流、效用得分构成、信用分布；（含 P1 权重调参面板，见 T30）。
- **Acceptance Criteria Addressed**: NFR-8
- **Test Requirements**:
  - `rule` TR-27.1: 运行剧本时大屏各组件数据随事件更新且与后端状态一致；证据：联调截图。

## Task T28: 冲突剧本库与一键运行器（≥10）
- **Status**: `pending`
- **Priority**: high
- **Depends On**: T20
- **WBS**: 8.1
- **Description**: 剧本 C1–C8 全部覆盖并扩展至 ≥10（议价破裂、并发抢单、审核申诉、货不对板、恶意退款、欺诈拦截、状态不一致、信用vs订单分歧、推荐偏向、人工终裁）；命令行/界面一键运行，输出逐步轨迹与期望对照表。
- **Acceptance Criteria Addressed**: AC-7
- **Test Requirements**:
  - `rule` TR-28.1: `scenarios/` 剧本数 ≥10；一键运行全部通过且每个剧本的"期望处置"断言成立；证据：运行报告（含 8 类场景映射）。

## Task T29: 测试与质量门禁
- **Status**: `pending`
- **Priority**: high
- **Depends On**: T28、T21–T26
- **WBS**: 8.2–8.4
- **Description**: pytest 回归（消息契约、状态机、并发抢单、LLM 故障注入、API、剧本）、无 Key 全链路验证、核心模块覆盖率检查、类型检查。
- **Acceptance Criteria Addressed**: AC-3、AC-8、AC-12、AC-15
- **Test Requirements**:
  - `rule` TR-29.1: 无 API Key 环境下 `pytest` 全绿，并发抢单与故障注入用例通过；证据：CI/本地测试日志。
  - `rubric` TR-29.2: 维度=工程质量（分层/命名/测试可维护性）；scale 1–5；1=不可运行 3=可运行耦合明显 5=分层清晰测试齐备；阈值 ≥4；证据：代码审查记录。

## Task T30: 效用权重对比实验工具（P1）
- **Status**: `pending`
- **Priority**: low
- **Depends On**: T19、T27
- **WBS**: 8.5
- **Description**: 参数化批量运行同一冲突集，输出不同权重组合下的裁决分布与效用对比。
- **Acceptance Criteria Addressed**: 周报问题 2
- **Test Requirements**:
  - `rule` TR-30.1: 对至少两组权重输出可对比的实验结果表；证据：实验输出文件。

## Task T31: 一键启动、README 与答辩演示资产
- **Status**: `pending`
- **Priority**: high
- **Depends On**: T29
- **WBS**: 9.1、9.2、9.4、9.5
- **Description**: Windows 一键启动脚本（后端+前端+初始化种子+自动播种演示账号）、README（环境/启动/演示路径/架构说明）、演示剧本与截图素材。
- **Acceptance Criteria Addressed**: NFR-7、AC-15
- **Test Requirements**:
  - `rule` TR-31.1: 在干净环境按 README 操作可一键启动并用种子账号登录演示；证据：全新环境验证记录。
  - `rubric` TR-31.2: 维度=可复现与文档质量；scale 1–5；阈值 ≥4；证据：第三方按文档走查。

## Task T32: Docker Compose 部署（P1）
- **Status**: `pending`
- **Priority**: low
- **Depends On**: T31
- **WBS**: 9.3
- **Description**: 前端/后端两容器编排（SQLite 卷持久化），`docker compose up` 一键拉起。
- **Acceptance Criteria Addressed**: 开放问题 2
- **Test Requirements**:
  - `rule` TR-32.1: 全新机器 `docker compose up` 后可访问登录并跑通一个剧本；证据：部署验证截图。

---

## 实施顺序提示

1. **第一波（可并行）**：T1 详设；随后 T2→（T3/T4 与 T5/T6/T7 两条线并行）。
2. **第二波**：T8 主编排 → T9–T16 九个 Agent（建议顺序：商品/审核 → 搜索 → 议价 → 履约 → 信用 → 仲裁，用户代理先行）。
3. **第三波**：T17–T20 冲突引擎（研究核心，与 Agent 联调）。
4. **第四波**：T21/T22 API/WS，前端 T23→T24/T25→T26（T27 P1）。
5. **收尾**：T28 剧本 → T29 测试 → T31 交付（T30/T32 视进度）。
6. 每完成一个任务即更新 Status 与 Completion Evidence；队列清空后进入独立 Review。
