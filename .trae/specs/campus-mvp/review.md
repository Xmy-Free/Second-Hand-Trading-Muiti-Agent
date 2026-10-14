# 独立评审报告 · 校园二手交易 Multi-Agent MVP

- 评审日期：2026-10-12
- 评审方式：fresh context 独立代理只读评审（代码走查 + pytest + 冲突剧本 + 对运行中服务 HTTP/WS 实测）
- 需求基线：`.trae/specs/campus-mvp/spec.md`（AC-1 ~ AC-12）
- 总体结论：**pass**

## 一、验证执行

| 验证项 | 命令 | 结果 |
|---|---|---|
| 后端单元/集成测试 | `python -m pytest tests -q` | **32 passed**（ACL 契约/鉴权/E2E 主链路/状态机/抢单/LLM 故障注入/无 Key 模式） |
| 冲突剧本回归 | `python -m app.scenarios.run_all` | C1 6/6、C2 7/7、C6 9/9、C8 7/7，**全部 PASS**，退出码 0 |
| 前端构建 | `npm run build`（vue-tsc 严格模式） | **零 TS 错误** |
| 真实 LLM 模式 | 服务 `/api/health` | llm_mode=llm；发布商品实测由 DeepSeek 完成结构化与审核 |

HTTP 实测覆盖：错误口令 401、越权 403、ACL 四类非法消息拒绝、完整主链路（发布→搜索→议价成交→支付→交付→收货→双评→reviewed）、审计时间线、热得快 veto 全路径封锁（含 approve 不可解除）、高风险买家 C6 加权 -0.55 拦截释放锁、控制台 agents/instances/trace/checkpoints/conflicts/messages、Agent 暂停→409→恢复、WS 实时 message/counter 帧。

## 二、验收点核对

### 规则型（CP）

| AC | 结论 | 关键证据 |
|---|---|---|
| AC-1 安全一票否决不可覆盖 | **PASS** | C8 剧本 7/7；veto 短路先于 LLM；仅 veto_gate 的 unfreeze+basis 可解除且留痕；冻结商品议价/下架/市场全拦截 |
| AC-2 主链路端到端 | **PASS** | test_e2e_main 全步骤；真实 LLM 跑通至 reviewed/dealed，双向信用 +2，审计时间线含 decisions/offers/audits |
| AC-3 并发抢单一致性 | **PASS** | C2 剧本 7/7；条件 UPDATE 乐观锁，恰一单、无超卖、锁释放正确 |
| AC-4 议价规则 | **PASS** | C1 剧本 6/6；单调让步、越界确认、交集成交、纳什价持久化、5 轮破裂+推荐 |
| AC-5 投票与人工闭环 | **PASS** | 实测加权分 -0.55 拦截；interrupt/resume 在 wait_pay/veto/risk/appeal 各门实测；灰区分支代码完整 |
| AC-6 双模式可运行 | **PASS** | 有 Key 走真实 DeepSeek；无 Key 四剧本+4 用例全绿；超时/非法 JSON 重试后降级 |
| AC-7 ACL 消息契约 | **PASS** | 9 个契约单测；performative 枚举/置信度区间/必填字段全部 Pydantic 拦截；出站唯一口 post_message |
| AC-8 LLM 故障无脏状态 | **PASS** | 3 个故障注入用例；无 500、状态合法、无半写入 |
| AC-11 控制台完整有效 | **PASS** | 五区块实测：Agent 总览（计数/暂停）、编排 SVG 节点图、消息总线 WS 实时流、黑板双视图、冲突中心投票明细 |

### 评分型（Rubric，阈值 ≥4）

| AC | 得分 | 依据 |
|---|---|---|
| AC-9 前端旅程可用性 | **5/5** | 三角色页面齐全；议价室 WS/倒计时/纳什徽标/确认框/破裂推荐完整；空/错/载反馈与守卫齐备；代码走查分 |
| AC-10 工程与代码质量 | **5/5** | 分层清晰（agents 零 HTTP 依赖）、配置集中、32 测试+4 剧本、一键启动、Agent 插拔真实可用 |
| AC-12 前端视觉顶尖度 | **4/5** | 完整设计 token、Element 双主题深度定制、深色指挥中心玻璃+霓虹+动效；业务端浅色与控制台深色品牌统一；保留 1 分人工像素余量 |

## 三、评审发现与处置

评审提出 7 项 Minor（无 Critical/Major），其中 4 项已在评审后即时修复并回归：

1. ✅ **已修复**：议价室 WS 增加参与方鉴权（仅买卖双方/管理员，否则 4403）。
2. ✅ **已修复**：C2 替代推荐改经 ACL 调度（`call_agent("trade", action=recommend)`），消息全程留痕。
3. ✅ **已修复**：C6 冲突事件 payload 增加 `kind/human_required`，控制台"前往人工处理"入口按其显示；C8 事件直达复核台。
4. ✅ **已修复**：清理残留调试脚本 `_tmp_t6.py`。

保留项（不阻塞验收）：
- C6 灰区 manual 分支、人工复核 resume、申诉 uphold/refund 的自动化用例可再补强（机制与已测 interrupt/resume 同源）。
- CORS `*` 与 JWT 密钥为开发态便利配置，.env 可覆盖，上线前应收敛。
- naive/aware UTC 时间戳目前以前端按 UTC 解析兜底，后续可统一后端时区输出。

修复后再次回归：**32 pytest passed + C1/C2/C6/C8 全 PASS + 前端 build 零错误**。

## 四、Checkpoint 结论

- [x] 每个 required checkpoint 均有独立/实测证据
- [x] 每个规则型 AC 有通过证据；rubric 全部 ≥4
- [x] 最新回归（修复 Minor 后）测试与剧本全绿
- [x] 前端五区块控制台经浏览器实拍验证（Agent 总览/编排图/消息总线/冲突投票）

**最终：评审通过，项目达到 spec.md 简约版 MVP 的全部验收标准。**
