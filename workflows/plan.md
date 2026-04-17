# Plan 工作流

合并旧的 design / inquiry / spike。产出三样：

1. `.auto-dev/dag.json` — 编排骨架（节点 id + 边 + OR 组）
2. `.auto-dev/nodes/<id>.md` — 每节点一个文件，frontmatter 规范 + 正文
3. 可选 `PLAN.md` — mermaid 视图，从 dag.json 生成，纯给人看

**图的质量由你自己判断**。validator 只兜底 JSON/拓扑崩塌（字段缺失、悬空 edge、环），不检查语义。边是否合理、deps 是否真实、completion 是否可验证，靠你自己想清楚——没想清楚就不要进 run 阶段。

---

## 流程

### 1. 列节点

对每个要做的事，在 `.auto-dev/nodes/<id>.md` 写一个文件，照 `templates/node.md` 填 frontmatter（`name` / `description` / `deps` / `branch`，可选 `or_candidate_of`）和正文（Entry / Completion / Scope / Retry / Escalation）。

- `id` 小写 kebab-case，与文件名一致。
- `deps` 是字符串数组，列出本节点依赖的父节点 id。
- `branch` 按惯例：
  - common successor 落在 `base_branch`（默认 `ai-main`）。
  - OR 候选首节点：`or/<desc>`。
  - AND 节点：`and/<parent>-<desc>`。
- `completion` 必须可跑或可看，不能只写"实现了 X"。

### 2. 连骨架

在 `.auto-dev/dag.json` 填：

```json
{
  "version": 2,
  "base_branch": "ai-main",
  "upstream_branch": "main",
  "nodes": [{ "id": "<id>", "status": "pending", "completion_tag": null }, ...],
  "edges": [{ "from": "<parent>", "to": "<child>" }, ...],
  "or_groups": []
}
```

边必须和每个节点 md 的 `deps` 保持一致（自检，validator 不强校）。

### 3. 识别 OR

竞争候选（同问题多方案）加入 `or_groups[]`：

```json
{ "id": "auth-strategy", "candidates": ["or-jwt", "or-session"], "decided": null, "rejected": [] }
```

候选节点 md 的 frontmatter 填 `or_candidate_of: auth-strategy`。

### 4. Inquiry（可选，唯一允许 AskUserQuestion 的窗口）

对每个 OR 组判型：
- **Type A**（人类已有答案）：用 AskUserQuestion 问驱动选择的**业务/产品约束**（不是"你更喜欢 JWT 还是 session"，而是"需要跨服务共享登录吗"）。答完直接写 `or_groups[].decided = <winning-id>`，被弃候选加入 `rejected`，被弃候选节点 `status="abandoned"`。
- **Type B**（需要数据）：留给 spike。

进 dev 后立即回到无人值守，不再提问。

### 5. Spike（可选）

对 Type B OR，每个候选派一个 `subagent_type: general-purpose` + `isolation: worktree`，prompt 含：
- 要验证的具体假设、成功/失败判据、预算（N 文件 / M commit / 时间）。
- 禁止改 `.auto-dev/**`、`PLAN.md`、`JOURNAL.md`、`NEEDS_REVIEW.md`、`base_branch`、`upstream_branch`、其他 spike 分支。
- 产出 ≤50 行 `spike/<desc>/RESULT.md` + 分支 tag `spike/result-<desc>`。

全部回来后主循环汇总结论，**停下写 NEEDS_REVIEW（`or-decision-needed`）**，等人类在 dag.json 里写 `decided`。

### 6. 校验

```
python3 scripts/validate_dag.py .auto-dev/dag.json
```

退出码非零 → 照错误修 dag.json，再跑，直到 OK。

### 7. 进入 dev

更新 `.auto-dev/state.json`：`phase=dev`，`dag_cursor` 指向首批可开工节点（所有 `deps` 都 `status=done` 且自身 `pending`）。

---

## 失败条件（停下写 NEEDS_REVIEW）

- `validate_dag.py` 非零 → `dag-schema-invalid`。
- 任一节点写不出可验证 completion → `design-blocked`。
- 任一节点估不出 scope → `design-blocked`。
- 需求矛盾 → `design-blocked`。

## 注意

- **规划决策要落字段**。不要在节点 md 正文里"顺便提一下"某条 deps 或 OR 关系——字段才是数据。
- 不要在 plan 阶段写代码或切分支（spike 例外，它派 subagent 在 worktree 里跑）。
- 允许 `Explore` subagent 做只读代码调研。
- 不预设 OR 胜负；OR 决策来自 inquiry / spike / 人类。
