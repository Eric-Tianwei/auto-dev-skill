# Design 工作流

产出 **`.auto-dev/dag.json`**（source of truth，schema 校验通过）+ `PLAN.md`（人类视图）。**dag.json 未通过校验不进 inquiry/dev。**

dag.json 是机器可读的图结构；PLAN.md 的 mermaid 和节点表从它渲染或与它保持一致。语言描述不覆盖字段——所有边类型、rationale、entry、completion 必须作为字段存在，不能只在 PLAN 正文里"提到"。

## 节点定义四件套

每个节点在开工前必须满足：

1. **Entry assumptions** — 开工前必须已真/已建的前提（通常是父节点的完成 tag）。
2. **Completion condition** — 可验证的测试/行为（不是"实现了 X"，而是"X 测试通过"）。
3. **Scope limit** — 最多改 N 文件；超了就该拆。
4. **Atomicity** — 半成品无价值，要么落地要么不落地。

完成条件是最关键的一项。描述含糊 → 后面失败升级无法判定级别 → 写 NEEDS_REVIEW 要求用户补清。

## 三种边（判定问题）

| 边 | 含义 | 判定问题 | dag.json 字段 |
|----|------|---------|--------------|
| SEQ | B 必须在 A 之后 | "这是真技术依赖还是线性思维习惯？" 习惯 → 改 AND | `type: "SEQ"` + `rationale`（必填） |
| AND | 共父、可并行 | "能不能同时做？接口由父输出定义？" | `type: "AND"` + `and_group` + `rationale` |
| OR  | 同问题的竞争实现 | "只会保留一个、另一个被弃？" | `type: "OR"` + `or_group` + `rationale`；`or_group` 在 `or_groups[]` 里有对应条目 |

**每条边都必须填 rationale。** schema 强制。rationale 是"为什么这个类型"——SEQ 说明依赖是真的不是习惯；AND 说明为何可并行；OR 说明互斥关系。写不出 rationale 说明边类型没想清楚——那就是设计缺陷，必须停下。

## 5 步计划流程

### 1. 粗节点列表
列出所有要做的事，暂不管依赖。

### 2. 分类边
对每对候选节点按上表判定边类型。识别 OR 节点——每个 OR 要清楚"A1 胜/A2 胜"分别的业务触发条件。

### 3. 压缩 SEQ 链
每条 SEQ 边问："真依赖还是习惯？" 习惯改 AND。目标：**无人类 checkpoint 的 SEQ 链 ≤ 3 节点**。

### 4. 拓扑预处理（找 common successor）
对每个 OR 节点：找所有分支都会到达的下游节点 → **移到 `base_branch`（默认 `ai-main`），排在 OR 分支之前**。否则 common successor 在每个 OR 分支里各实现一次，重复且 review 噪声大。

注意：这里的 "base_branch" 是 `.auto-dev/state.json` 里的字段，默认 `ai-main`。`main` 是人类 upstream，AI 不往那里落。

### 5. 节点规范（写到 dag.json，不是 PLAN 正文）
每个节点在 dag.json `nodes[]` 里填完整对象：`entry`（字符串数组）、`completion`（字符串数组，至少 1 项）、`scope.max_files_changed`、`retry_limit`、`escalation.l1_trigger` / `l2_trigger`、`kind`、`branch`、`status="pending"`。

写不出可验证的 `completion` 条目（"实现了 X"不算，必须是可跑可看）→ 停（`design-blocked`）。

### 6. 跑校验

```
python3 scripts/validate_dag.py .auto-dev/dag.json
```

退出码非零 → 照着错误信息修 dag.json，再跑，直到 OK。**不允许带着未通过校验的 dag.json 进 inquiry。**

### 7. 渲染 PLAN.md（视图层）

从 dag.json 生成 PLAN.md 的 mermaid 图 + 节点表 + 每节点规范段（见 `templates/PLAN.md`）。PLAN.md 字段必须与 dag.json 一致；若人类在 PLAN.md 手改了字段，design 重跑时以 dag.json 为准——文字提示必须叠加到 dag.json 再重新渲染。

## 产出

- `.auto-dev/dag.json` — source of truth（schema 通过）。
- `.auto-dev/schema/dag.schema.json` — schema 副本（从 `templates/dag.schema.json` 拷来，首次 design 建立）。
- `PLAN.md` — 视图层：mermaid + 节点表 + 规范段。
- 更新 `.auto-dev/state.json`：`phase=inquiry`，`dag_cursor` 指向首批可开工节点。

## 失败条件（写 NEEDS_REVIEW 停）

- `validate_dag.py` 退出码非零（含：schema 字段缺失、rationale 缺失、AND 缺 `and_group`、OR 缺 `or_group`、OR 边 `or_group` 未在 `or_groups[]`、悬空 edge、环、SEQ 链 > 3 等）。
- 任一节点估不出 scope 上限。
- 任一节点写不出 verifiable completion condition。
- 任一条边写不出 rationale（作者分不清 SEQ/AND/OR 的依据）。
- 需求本身矛盾，无法建出一致的节点集。

停止原因 tag：`design-blocked`（设计问题）或 `dag-schema-invalid`（机器校验失败）。两者都写哪个错误信息被 validator 输出即可。

## 注意

- **一切规划决策都落到 dag.json 字段**。不要在 PLAN.md 正文里"顺便提一下"边类型或约束——文字不是决策，字段才是。
- 不要凭直觉"这个先做那个后做"。每条 SEQ 都要经得起"真依赖"追问，rationale 字段必须写得出具体依赖项。
- 不要预设 OR 胜负。OR 节点本身是中立的 fork，决策留给 inquiry / spike / 人类。
- 不要在 design 阶段写代码或切分支，也不要跑 subagent 做探索（那是 spike 阶段）。
- 允许 `Explore` subagent 做只读代码调研（了解现有结构），但不得落盘任何规划文件。
