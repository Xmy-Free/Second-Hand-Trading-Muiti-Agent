# 新增 Trae 开发智能体 — 任务队列

## AC 索引

| AC | 覆盖任务 |
|---|---|
| AC-1 格式合法 | T1、T7 |
| AC-2 与 WBS 对齐 | T2–T7 |
| AC-3 可调度 | T7 |
| AC-4 提示词质量 | T2–T7 |

---

## Task T1: 创建 agents 目录与通用约定
- **Status**: `completed`
- **Priority**: high
- **Depends On**: None
- **Description**: 创建 `.trae/agents/`；确认 frontmatter 命名/工具白名单；6 个文件统一引用 spec.md/tasks.md 与项目铁律。
- **Test Requirements**:
  - `rule` TR-1.1: 目录存在，工具名全部在官方白名单（Bash/Edit/Glob/Grep/Read/Skill/TodoWrite/WebFetch/WebSearch/Write/LSP）；证据：目录与配置文本核对。
- **Completion Evidence**: `.trae/agents/` 已创建；6 文件均引用 `.trae/specs/campus-secondhand-mas/spec.md` 为最高依据；两轮校验脚本（PyYAML 解析）全部 PASS。

## Task T2: mas-architect
- **Status**: `completed`
- **Priority**: high
- **Depends On**: T1
- **Description**: 架构师智能体提示词，覆盖详设文档、ACL 协议、ER/状态机、技术选型核查；可写 docs/ 与 .trae/specs/（仅经要求）。
- **Test Requirements**:
  - `rule` TR-2.1: 提示词含角色、≥4 步工作流、输出物、边界（不写业务代码）；证据：文件内容。
- **Completion Evidence**: `.trae/agents/mas-architect.md`，含 5 步工作流、职责范围、边界（不写 backend/frontend 业务代码），工具 8 项校验 PASS。

## Task T3: backend-dev
- **Status**: `completed`
- **Priority**: high
- **Depends On**: T1
- **Description**: 后端工程师，限定 `backend/` 但排除 `backend/app/{agents,graph,kernel,llm}`；FastAPI/SQLModel/JWT/订单锁/API/WS。
- **Test Requirements**:
  - `rule` TR-3.1: 提示词明确目录边界与"改完即跑测试/无 Key 必须可跑"约束；证据：文件内容。
- **Completion Evidence**: `.trae/agents/backend-dev.md`；评审 Finding 1 整改后显式排除 4 个内核目录、`backend/tests/`、`backend/app/scenarios/`；含无 Key 可跑与 PowerShell 5 约束。

## Task T4: mas-engineer
- **Status**: `completed`
- **Priority**: high
- **Depends On**: T1
- **Description**: 多 Agent 内核工程师，限定 `backend/app/{agents,graph,kernel,llm}` 及 scenarios；固化安全否决、SSOT、三级阶梯、双通道 LLM 等研究铁律。
- **Test Requirements**:
  - `rule` TR-4.1: 提示词显式包含 spec 第 8 章机制与 AC-1/4/5/6/8/11/12 的约束；证据：文件内容。
- **Completion Evidence**: `.trae/agents/mas-engineer.md`；独立评审逐条比对第 8 章（四类检测/三级阶梯/效用数值/加权投票/veto/熔断/纳什价/抢单优先级/双通道）全部覆盖；已补"一级协商 ≤3 轮"与 scenarios/fixtures/ 边界。

## Task T5: frontend-dev
- **Status**: `completed`
- **Priority**: high
- **Depends On**: T1
- **Description**: 前端工程师，限定 `frontend/`；Vue3 全套技术栈、WS 议价室、Element Plus、ECharts；遵循后端 OpenAPI 契约。
- **Test Requirements**:
  - `rule` TR-5.1: 提示词含技术栈、页面清单（spec FR-15）、构建验证步骤；证据：文件内容。
- **Completion Evidence**: `.trae/agents/frontend-dev.md`，含三端页面清单（FR-15）、可解释性展示要求、`npm.cmd run build` 验证步骤；工具 8 项 PASS。

## Task T6: qa-engineer
- **Status**: `completed`
- **Priority**: high
- **Depends On**: T1
- **Description**: 测试工程师，写/改 `backend/tests/` 与 `scenarios/`，覆盖 AC、并发与故障注入、≥10 剧本；只读生产代码（可提 PR 建议）。
- **Test Requirements**:
  - `rule` TR-6.1: 提示词含无 Key 全绿门禁、并发恰一成交断言、剧本 C1–C8 映射；证据：文件内容。
- **Completion Evidence**: `.trae/agents/qa-engineer.md`，含 AC 红线测试矩阵（AC-1/3/4/6/8/11/12）、≥10 剧本覆盖 C1–C8、只读生产代码边界（fixtures/ 只引用）。

## Task T7: docs-writer + 整体校验
- **Status**: `completed`
- **Priority**: medium
- **Depends On**: T2、T3、T4、T5、T6
- **Description**: 文档工程师（README/周报/报告/PPT 素材，作者排版偏好）；随后用脚本 YAML 解析 6 文件、核对 name/description/tools，并输出交付说明（Beta 开关与调用方式）。
- **Test Requirements**:
  - `rule` TR-7.1: 6 文件 YAML frontmatter 全部解析成功且字段合规；证据：校验脚本输出。
  - `rule` TR-7.2: 交付说明含启用路径、调用示例与各智能体一句话用途；证据：最终回复。
- **Completion Evidence**: `.trae/agents/docs-writer.md`（评审 Finding 2 整改：tools 增补 Skill 以支持 ppt/word/html Skill，spec 表格同步）；两轮校验 6/6 PASS；独立评审 Review R1 结论 pass，见 `review.md`；交付说明已在最终回复给出。
