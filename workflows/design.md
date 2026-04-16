# Design 工作流

产出 `PLAN.md`：DAG 本体 + 每节点规范。**不写完不进 dev。**

## 节点定义四件套

每个节点在开工前必须满足：

1. **Entry assumptions** — 开工前必须已真/已建的前提（通常是父节点的完成 tag）。
2. **Completion condition** — 可验证的测试/行为（不是"实现了 X"，而是"X 测试通过"）。
3. **Scope limit** — 最多改 N 文件；超了就该拆。
4. **Atomicity** — 半成品无价值，要么落地要么不落地。

完成条件是最关键的一项。描述含糊 → 后面失败升级无法判定级别 → 写 NEEDS_REVIEW 要求用户补清。

## 三种边（判定问题）

| 边 | 含义 | 判定问题 |
|----|------|---------|
| SEQ | B 必须在 A 之后 | "这是真技术依赖还是线性思维习惯？" 习惯 → 改 AND |
| AND | 共父、可并行 | "能不能同时做？接口由父输出定义？" |
| OR  | 同问题的竞争实现 | "只会保留一个、另一个被弃？" |

## 5 步计划流程

### 1. 粗节点列表
列出所有要做的事，暂不管依赖。

### 2. 分类边
对每对候选节点按上表判定边类型。识别 OR 节点——每个 OR 要清楚"A1 胜/A2 胜"分别的业务触发条件。

### 3. 压缩 SEQ 链
每条 SEQ 边问："真依赖还是习惯？" 习惯改 AND。目标：**无人类 checkpoint 的 SEQ 链 ≤ 3 节点**。

### 4. 拓扑预处理（找 common successor）
对每个 OR 节点：找所有分支都会到达的下游节点 → **移到 main，排在 OR 分支之前**。否则 common successor 在每个 OR 分支里各实现一次，重复且 review 噪声大。

### 5. 节点规范
每个节点按 `templates/NODE.md` 写 entry/completion/scope/retry/escalation。这是 DESIGN 的最终产物，没有它不进 dev。

## 产出

- `PLAN.md`：mermaid DAG 图 + 节点表（id / 类型 / 父 / 子 / 状态 / 分支 / 完成 tag）。
- 每节点一段规范（直接内嵌在 PLAN 的节点表后，或单开 `nodes/<id>.md`）。
- 更新 `.auto-dev/state.json`：`phase=inquiry`，`dag_cursor` 指向首批可开工节点。

## 失败条件（写 NEEDS_REVIEW 停）

- 任一节点估不出 scope 上限。
- 任一节点写不出 verifiable completion condition。
- DAG 有环（违反 acyclic）或悬空节点。
- 需求本身矛盾，无法建出一致的节点集。

停止原因 tag：`design-blocked`。

## 注意

- 不要凭直觉"这个先做那个后做"。每条 SEQ 都要经得起"真依赖"追问。
- 不要预设 OR 胜负。OR 节点本身是中立的 fork，决策留给 inquiry / spike / 人类。
- 不要在 design 阶段写代码或切分支，也不要跑 subagent 做探索（那是 spike 阶段）。
- 允许 `Explore` subagent 做只读代码调研（了解现有结构），但不得落盘任何规划文件。
