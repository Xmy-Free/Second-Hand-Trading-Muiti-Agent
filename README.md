# 校园二手交易 Multi-Agent 平台（简约版 MVP）

> 1 个协调者 Agent + 3 个专家 Agent · FIPA ACL 消息总线 · LangGraph 编排 + 黑板 SSOT · 三级冲突决策 · 安全一票否决
>
> 后端 FastAPI / LangGraph / SQLite，前端 Vue 3 + Element Plus 深度定制（含深色 Mission Control 多 Agent 控制台）。

## 一、快速启动（Windows）

```powershell
# 项目根目录执行（自动建虚拟环境、装依赖、初始化数据库+种子、拉起前后端并打开浏览器）
powershell -ExecutionPolicy Bypass -File .\start-all.ps1
```

手动启动（两个终端）：

```powershell
# 终端 1：后端
cd backend
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# 终端 2：前端
cd frontend
npm.cmd run dev
```

浏览器打开 <http://localhost:5173>，后端接口文档 <http://localhost:8000/docs>。

## 二、种子账号（密码统一 `123456`）

| 角色 | 学号 | 说明 |
|---|---|---|
| 管理员 / 作者 | `2400320321` | 梁奕琦，可进入 Agent 控制台、复核台、终裁台 |
| 卖家 | `20240001` `20240002` `20240003` | 张学长 / 李学姐 / 王同学 |
| 买家 | `20240004` `20240005` | 信用正常 |
| 高风险买家 | `20240006` | 信用 68，用于演示 C6 风险投票拦截 |

首次启动自动建表并播种 10 件跨类目在售商品、违禁词库、4 个 Agent 注册信息。

## 三、双引擎 LLM 模式

- 在 `backend/.env` 配置 `DEEPSEEK_API_KEY` 即启用真实大模型（商品结构化/审核）；
- **未配置 Key 或调用超时/返回非法 JSON 时自动降级 RuleLLM 规则引擎**，全部功能与剧本均可离线运行，答辩不依赖网络。

## 四、多 Agent 管理控制台（项目核心）

用管理员账号登录后进入「Agent 控制台」（`/console`，深色指挥中心）：

1. **Agent 总览**：4 个 Agent 的能力标签、运行状态灯、llm/rule 引擎徽章、消息/任务实时计数、暂停/恢复；
2. **编排追踪**：主链路 SVG 节点图，已走节点发光、连线流光、当前人工节点呼吸高亮、节点决策时间线；
3. **消息总线**：ACL 消息实时流（performative 彩色徽标 + 收发方向 + 置信度），可过滤、可展开 payload；
4. **黑板快照**：LangGraph State 树形/JSON 双视图；
5. **冲突中心**：C1/C2/C6/C8 事件时间线 + C6 三方加权投票明细仪表。

## 五、五分钟答辩演示动线

1. 管理员账号打开 **Agent 控制台**，讲解 4 个 Agent 注册与职责；
2. 切卖家账号发布「热得快电热棒…」→ 控制台实时观察消息流与节点点亮，商品被 **C8 一票否决冻结**，在复核台看到证据；
3. 发布一件正常商品（可观察 LLM 结构化与建议价）→ 在售；
4. 买家搜索（查看匹配理由）→ 发起议价 → 议价室内多轮出价、纳什参考价、120 秒倒计时；
5. 用高风险买家 `20240006` 成交任意商品 → 控制台冲突中心看到 **C6 三方投票（加权分 -0.55）拦截订单**；
6. 买家完成支付 → 卖家交付 → 买家收货 → 双向评价，信用分实时变化；
7. 在已支付订单发起「货不对板」申诉，小额由协调者规则直裁退款，大额在终裁台人工裁决。

## 六、冲突剧本与测试

```powershell
cd backend
# 4 个冲突场景一键回归（无需 Key）：C1 议价僵持 / C2 并发抢单 / C6 风险投票 / C8 违禁否决
.venv\Scripts\python.exe -m app.scenarios.run_all

# 32 个 pytest：ACL 契约 / 鉴权 / 端到端主链路 / 状态机 / 抢单 / LLM 故障注入 / 无 Key 模式
.venv\Scripts\python.exe -m pytest tests -q
```

## 七、技术结构

```
backend/app/
  agents/      coordinator.py(仲裁/申诉) goods.py(结构化/审核/veto)
               trade.py(搜索/议价/纳什价) order_credit.py(锁/支付/信用) + base 契约
  graph/       LangGraph 四条流程(publish/trade/appeal/demo) + checkpointer + interrupt 人工门
  kernel/      ACL 消息契约 / 事件总线 / 注册表 / 黑板状态 / WS 房间 / 冲突与审计记录
  llm/         DeepSeek 适配(重试降级) + RuleLLM 确定性兜底
  api/         auth items market negotiations orders social appeals moderation console(+WS)
  scenarios/   C1-C4 冲突剧本运行器
frontend/src/
  views/console/   Mission Control 深色控制台（五区块）
  views/           市场/详情/议价室/订单/信用/发布/我的商品/复核台/终裁台
  api/ ws.ts       统一 API 客户端与 WebSocket 组合式封装
```

## 八、可配置阈值（`backend/app/core/config.py` / `.env`）

议价 5 轮 / 120 秒、支付时限 15 分钟、信用初始 100（好评 +2 / 差评 -5 / 责任 -15）、高风险线 80、
投票票权 0.5/0.2/0.3、放行 +0.5 / 拦截 -0.5、申诉直裁阈值 50 元。
