# Plan 工作流

合并旧的 design / inquiry / spike。产出：

1. `.auto-dev/dag.json` + `.auto-dev/nodes/<id>.md` —— 全部通过 `auto-dev` CLI 写入
2. 可选 `PLAN.md` —— mermaid 视图，从 dag.json 生成，纯给人看

**图的质量由你自己判断**。validator 只兜底 JSON/拓扑崩塌，不检查语义——边是否合理、deps 是否真实、completion 是否可验证，靠你自己想清楚。没想清楚就不要进 run 阶段。

CLI 调用形式见 SKILL.md 的"CLI 速查"。下文写 `auto-dev` 为简称。

---

## 流程

### 1. 列节点（两阶段法，推荐）

**阶段 1a——只列节点，不想依赖**：

对每个要做的事跑 `auto-dev node add <id> [--branch ...] [--desc ...]`，**`--deps` 留空**。目的是先把分解做完，不要一边分解一边猜依赖。

- `id` 小写 kebab-case。CLI 会从 `templates/node.md` 生成 `.auto-dev/nodes/<id>.md` 骨架并登记到 `dag.json`。
- `--branch` 按惯例：common successor 落在 base_branch（默认 `ai-main`，可省略）；OR 候选首节点 `or/<desc>`；AND 节点 `and/<parent>-<desc>`。

**阶段 1b——填每个节点的 Entry / Completion**：

手动 Edit 每个 `.auto-dev/nodes/<id>.md` 的正文，重点写清：

- `## Entry`：本节点开工前需要的前置（**"needs"**）——比如"JWT 中间件 `validate()` 可用"、"购物车 `addItem` 可用"。这是后面连边的依据。
- `## Completion`：本节点产出什么可验证结果（**"produces"**）——比如"`validate(req,res,next)` 导出"、"tests/X.test.ts 全绿"。
- `## Scope` / `## Retry` / `## Escalation`：按模板填。

`completion` 必须可跑或可看，不能只写"实现了 X"。

**阶段 1c——看一屏连边**：

```
auto-dev nodes
```

输出每节点的 `needs` 和 `produces`。然后对每一对节点判断：*A 的 produces 里是否包含 B 的 needs？* 是就跑 `auto-dev edge add A B`。

两阶段法的好处：连边时脑子里有全局所有节点的信号，不是一边分解一边猜。

> 已经想清楚的节点可以直接 `--deps a,b` 一步到位；但**怀疑依赖关系时就走两阶段**，不要在 `--deps` 里瞎填。

事后调整用 `auto-dev edge add/rm`；删节点用 `auto-dev node rm <id>`（级联删边 + 同步子节点 deps + OR 候选 <2 连带删组）。

### 2. 识别 OR

竞争候选（同问题多方案）：
1. 先用 `node add` 分别建好候选节点（通常 `--branch or/<desc>`）。
2. 跑 `auto-dev or create <group-id> --candidates a,b,c`——CLI 会给每个候选 md 加 `or_candidate_of: <group-id>`。

### 3. Inquiry（可选，唯一允许 AskUserQuestion 的窗口）

对每个 OR 组判型：

- **Type A**（人类已有答案）：用 AskUserQuestion 问驱动选择的**业务/产品约束**（不是"JWT 还是 session"，而是"需要跨服务共享登录吗"）。答完跑 `auto-dev or decide <group-id> <winning-id>`——CLI 自动把败者节点改 `status=abandoned`。
- **Type B**（需要数据）：留给 spike。

进 dev 后立即回到无人值守，不再提问。

### 4. Spike（可选）

对 Type B OR，每个候选派一个 `subagent_type: general-purpose` + `isolation: worktree`，prompt 含：

- 要验证的具体假设、成功/失败判据、预算（N 文件 / M commit / 时间）。
- 禁止改 `.auto-dev/**`、`PLAN.md`、`JOURNAL.md`、`NEEDS_REVIEW.md`、`base_branch`、`upstream_branch`、其他 spike 分支。
- 产出 ≤50 行 `spike/<desc>/RESULT.md` + 分支 tag `spike/result-<desc>`。

全部回来后主循环汇总结论，**停下写 NEEDS_REVIEW（`or-decision-needed`）**，等人类跑 `auto-dev or decide <g> <w>`（或直接告诉你，然后你跑）。

### 5. 校验

```
auto-dev validate
```

退出码 5 → 照错误改，再跑，直到 OK。

**再跑一次 `auto-dev nodes` 做语义自检**：对每个节点，Entry 列表的每一项能不能在某个 dep 节点的 Completion 里找到对应的 produces？找不到就是缺边或写错——补 `edge add` 或改 md。这步 CLI 不强制，但跳过很容易放行"结构对但语义错"的图。

### 6. 进入 dev

```
auto-dev phase set dev
```

CLI 会先内部跑一次 validate；失败就拒绝切换。成功后自动把 `dag_cursor` 设到首个 ready 节点（所有 deps 都 `status=done` 且自身 `pending`）。

---

## 失败条件（停下写 NEEDS_REVIEW）

- `auto-dev validate` 退出 5 → `dag-schema-invalid`。
- 任一节点写不出可验证 completion → `design-blocked`。
- 任一节点估不出 scope → `design-blocked`。
- 需求矛盾 → `design-blocked`。

## 注意

- **规划决策要走 CLI**。不要在节点 md 正文里"顺便提一下"某条 deps 或 OR 关系——字段和事件才是数据。
- 不要在 plan 阶段写代码或切分支（spike 例外，它派 subagent 在 worktree 里跑）。
- 允许 `Explore` subagent 做只读代码调研。
- 不预设 OR 胜负；OR 决策来自 inquiry / spike / 人类。
- 直接编辑 `.auto-dev/dag.json` 合法但会丢事件；偶尔改字段 OK，但成规模的变更走 CLI。
