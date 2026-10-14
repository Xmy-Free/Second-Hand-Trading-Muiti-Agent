# 校园二手交易 Multi-Agent（简约版 MVP）— 实施任务队列

> 依据：同目录 `spec.md`。T1–T21 已全部实施完成，独立评审通过（见 `review.md`，AC-1~AC-12 全部达标）。

---

## ✅ 实施完成总结（2026-10-12）

| 波次 | 任务 | 完成证据 |
|---|---|---|
| 波次 1 | T1–T3 工程骨架/视觉基座/认证 | `/api/health` 双模式；种子 7 账号+10 商品+4 Agent；登录页玻璃视觉；JWT/401/403 测试 |
| 波次 2 | T4–T6 ACL/黑板/注册表/事件总线/编排图/interrupt | ACL Pydantic 契约（9 performative）；4 条 LangGraph 流（publish/trade/appeal/demo）+ SQLite checkpointer；进程内 pub/sub 事件总线 |
| 波次 3 | T7–T12 四 Agent 与业务 API | 三档审核/veto、搜索带理由、议价 5 轮+纳什价、乐观锁订单、信用评价、C6 三方加权投票、申诉规则裁决+人工终裁 |
| 波次 4 | T13 控制台后端 | `/api/console/*` + `/ws/control`：agents/暂停恢复/instances/trace/checkpoints/conflicts/messages |
| 波次 5 | T14–T18 前端五区块+业务页 | vue-tsc 零错误；市场/详情/议价室/订单/信用/发布/我的商品/复核台/终裁台 + Mission Control 控制台五区块 |
| 波次 6 | T19–T21 剧本/测试/启动 | `run_all` C1 6/6、C2 7/7、C6 9/9、C8 7/7；pytest 32 passed；`start-all.ps1` + README + 答辩动线 |

回归命令（`backend/`）：`.venv\Scripts\python.exe -m app.scenarios.run_all`、`.venv\Scripts\python.exe -m pytest tests -q`。

评审后 Minor 修复：议价 WS 参与方鉴权（4403）、C2 替代推荐改走 ACL、C6 事件附 kind/human_required、清理调试脚本。修复后 32 测试 + 4 剧本仍全绿。

---

## 任务清单（原始定义，全部 Status: completed）

- **T1** 后端工程骨架、统一响应、配置、SQLite(WAL)、健康检查
- **T2** 前端工程基座：Vite/Vue3/TS/Pinia/Element Plus 深度定制 + 设计 Token（浅/深双主题）
- **T3** 注册登录/JWT/角色鉴权 + 种子数据（7 账号、10 商品、违禁词、4 Agent）
- **T4** Agent 通信内核：AclEnvelope/基类/黑板/注册表/事件总线
- **T5** LLM 适配层 DeepSeek + RuleLLM 兜底（商品结构化/建议价/审核/议价让步）
- **T6** LangGraph 主编排：主图、节点轨迹装饰器、checkpoint、interrupt/resume
- **T7** GoodsAgent：结构化+建议价+三档审核+安全否决 + 发布审核流 + items API
- **T8** TradeAgent（搜索/推荐）
- **T9** TradeAgent（纳什价/多轮议价/WebSocket 议价室）
- **T10** OrderCreditAgent（锁/状态机/抢单/支付）
- **T11** OrderCreditAgent（双向评价/信用分/风险意见）
- **T12** Coordinator：C6 加权投票 + 申诉证据包/规则裁决 + 管理员接口
- **T13** 控制台后端：agents/暂停恢复/instances/trace/checkpoints/conflicts/messages + `/ws/control`
- **T14** 卖家端：发布页（AI 结果卡/建议价区间）、我的商品（状态/依据/重提/下架/评价）
- **T15** 买家端：市场（筛选+理由）、商品详情、下单/模拟支付/我的订单/评价/信用
- **T16** 议价室共用组件：出价气泡/纳什徽标/环形倒计时/风险提示/WS/越界确认
- **T17** 管理员：复核台（veto 维持/证据解除）、纠纷终裁台（证据包+裁决）
- **T18** 多 Agent 管理控制台（最高优先深色页）：五区块
- **T19** 冲突剧本运行器 C1–C4 + `python -m app.scenarios.run_all`
- **T20** pytest：ACL/鉴权/E2E/抢单/状态机/LLM 故障注入/无 Key 回归（32 用例）
- **T21** 一键启动脚本 + README（双模式/种子/剧本命令/5 分钟答辩动线）

## AC 覆盖矩阵

| AC | 覆盖任务 |
|---|---|
| AC-1 veto | T7、T17、T19(C8)、T20 |
| AC-2 主链路 | T7–T11、T14–T17、T20(e2e) |
| AC-3 抢单 | T10、T19(C2)、T20 |
| AC-4 议价 | T9、T16、T19(C1)、T20 |
| AC-5 投票人工 | T11、T12、T17、T19(C6) |
| AC-6 双模式 | T1、T5、T19、T20 |
| AC-7 ACL | T4、T20 |
| AC-8 LLM 故障 | T5、T20 |
| AC-9 前端旅程 | T14–T17 |
| AC-10 工程质量 | T1–T21 |
| AC-11 控制台 | T13、T18 |
| AC-12 视觉 | T1、T14–T18 |
