# 为项目新增 Trae 开发智能体（Subagent）— 需求说明

## 1. 背景与目标

项目已批准 PRD（`.trae/specs/campus-secondhand-mas/spec.md`）进入开发阶段，技术栈为 **FastAPI + LangGraph + SQLModel/SQLite + Vue3/TS/Element Plus**，研究核心是"1 协调者 + 8 专家"的多 Agent 冲突决策机制。

截图显示 Trae "智能体"面板当前"暂无自定义智能体"。需求：**在 Trae 中新增若干个项目级开发智能体**，把后续高频开发工作流（架构设计、后端、多 Agent 内核、前端、测试、文档）固化为可复用角色，由内置 **Agent** 按 `description` 自动委派，实现上下文隔离与专业分工。

## 2. 实现机制（官方文档确认）

- 采用**项目级 Subagent**：配置文件位于 `{project}/.trae/agents/{name}.md`，随仓库走、仅对本项目生效；无需在 UI 手工逐个创建。
- 每个文件 = YAML frontmatter（`name`/`description`/`tools`/`model` 可选）+ Markdown 系统提示词。
- `name` 规则：字母开头，仅含字母/数字/连字符，≤50 字符；`description` 必填，越具体调度越准；`tools` 按最小权限授予。
- 仅内置 **Agent** 可调用 Subagent；前提：设置 → Beta → Subagents →"启用 Subagents 目录"已开启（默认开启）。
- 与截图中"+ 创建"的**用户级自定义智能体**的区别：后者通过 UI 建立、存于用户全局配置、不可随仓库分发；本需求选择项目级文件方式（可移植、可评审、可版本化），更适合开发分工。若你同时需要在"智能体"面板看到用户级智能体，可在确认后按相同提示词在 UI 再建一次（我可给出逐步操作指引）。

## 3. 拟新增的 6 个智能体

| # | 文件名 / name | 职责 | 主要工具（最小权限） |
|---|---|---|---|
| 1 | `mas-architect.md` / `mas-architect` | 架构与详细设计：技术选型、Agent 角色卡、ACL 消息协议、状态机/ER、冲突检测与仲裁规则；维护 spec/design 一致性 | Read, Glob, Grep, Write, Edit, WebSearch, WebFetch, TodoWrite |
| 2 | `backend-dev.md` / `backend-dev` | 后端业务层：FastAPI 路由、SQLModel 模型/迁移、JWT 鉴权、订单状态机/锁、REST 与 WebSocket；限定 `backend/` | Read, Glob, Grep, Write, Edit, Bash, LSP, TodoWrite |
| 3 | `mas-engineer.md` / `mas-engineer` | 多 Agent 研究核心：9 类 Agent 节点、LangGraph 编排图、黑板 SSOT/ACL 总线、冲突检测、三级阶梯、效用/投票/否决/熔断、LLM+RuleLLM 双通道；限定 `backend/app/{agents,graph,kernel,llm}` | Read, Glob, Grep, Write, Edit, Bash, LSP, TodoWrite |
| 4 | `frontend-dev.md` / `frontend-dev` | 前端：Vue3+TS+Vite+Pinia+Element Plus+ECharts，买卖端/管理台/监控大屏、议价 WS；限定 `frontend/` | Read, Glob, Grep, Write, Edit, Bash, LSP, TodoWrite |
| 5 | `qa-engineer.md` / `qa-engineer` | 质量保障：pytest/pytest-asyncio/httpx 测试、并发抢单与 LLM 故障注入、≥10 个冲突剧本、回归门禁；只读生产代码，新增/修改 `tests/` 与 `scenarios/` | Read, Glob, Grep, Write, Edit, Bash, TodoWrite |
| 6 | `docs-writer.md` / `docs-writer` | 文档与答辩材料：README、设计文档、周报、测试报告；图表置顶且完整无滚动条、截图与文字对应、中文、排版精美（遵循作者偏好）；可调用 ppt/word/html 等 Skill | Read, Glob, Grep, Write, Edit, WebSearch, WebFetch, Skill |

共性约束（写入每个提示词）：遵循已批准的 spec.md 与 tasks.md；不改动 `.trae/specs/` 已批准文档（除 `mas-architect` 经明确要求外）；中文沟通；不确定时先提问；安全否决/SSOT/状态机等项目铁律不得违背。

## 4. 非目标

- 不创建用户级（UI）智能体、不配置 MCP Server、不指定固定模型（默认跟随 Agent 对话框所选模型，便于你切换 DeepSeek/GLM 等）。
- 不改变任何业务代码；本任务仅交付 6 个 `.md` 配置文件。

## 5. 验收标准

### AC-1 文件齐备且格式合法 `rule`
- `.trae/agents/` 下存在 6 个文件；每个含合法 YAML frontmatter（`---` 分隔、`name` 符合命名规则、`description` 非空、`tools` 均为官方白名单工具）；证据：目录列表 + YAML 解析通过。

### AC-2 角色与 WBS 对齐 `rule`
- 每个智能体的提示词明确：角色、工作流、代码/文件范围边界、项目铁律引用（spec.md 路径）；后端/内核/前端三者写入互不重叠的目录边界；证据：逐个文件内容核对。

### AC-3 可被发现与调度 `rule`
- 在 Trae 中以与各 `description` 匹配的中文指令（如"给议价 Agent 补单测""写 FastAPI 下单接口"）可由 Agent 路由到对应 Subagent；证据：实际调用验证或 @ 列表可见（受 Beta 开关影响时给出开启指引）。

### AC-4 提示词质量 `rubric`
- 维度：角色清晰度/工作流可执行性/边界明确性；1=模糊空泛，3=可用但边界弱，5=分工清晰、可直接稳定执行；阈值 ≥4；证据：6 份提示词评审。

## 6. 开放问题

1. 智能体数量与分工是否认可上表（6 个）？如需合并（如架构并入后端）或新增（如 code-reviewer、DBA、UI 设计师）请指出。
2. 是否需要为某些智能体指定固定模型（如 mas-engineer 用 DeepSeek-V4-Pro-Official、frontend-dev 用 Doubao-Seed-Code）？默认全部跟随对话框模型。
3. 是否还需要我在 UI"智能体"面板指导创建同名的用户级智能体？（默认不需要。）
