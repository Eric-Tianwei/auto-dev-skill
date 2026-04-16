# Inquiry 工作流

**此阶段是主循环中唯一允许 `AskUserQuestion` 的窗口。** 进 dev 后立即回到无人值守。

目标：用有限几个问题，把"人类已知答案"的 OR 节点（Type A）提前折叠为决策，给 spike 阶段只留真正需要探索的 OR 节点（Type B）。

## OR 分型

| 型 | 特征 | 处理 |
|----|------|------|
| Type A | 人类已有答案，只是还没说 | **问一下就塌缩**，不用 spike |
| Type B | 人类自己也不确定，需看数据 | 问没用，排到 spike 队列 |

判型在 dag.json 的 `or_groups[].or_type` 字段里显式标记（同时每个 OR_HEAD 节点的 `or_type` 字段保持一致）。判不清时默认 Type B（保守）。

## 核心翻译规则

**不问技术选型，问驱动技术选型的业务/产品约束。**

```
错: "用 JWT 还是 session？"          ← 人可能答不了、答了也不负责
对: "需要跨多个子域/服务共享登录吗？"  ← 人一定知道，且答案直接决定 JWT vs session
```

流程：
1. 列出 OR 的两个（或多个）竞争选项 A1 / A2。
2. 想清楚："哪个业务约束成立则 A1 明显赢？哪个成立则 A2 赢？"
3. **问那个约束**，不问选项。

## 问题优先级：downstream-impact 打分

```
Score(Q) = 这个问题的任一答案能折叠的 OR 节点数量
```

先问高分问题。一个问题如果最好情况下都折叠不了任何 OR 节点 → 不问。

## 自适应提问

**禁止一次性 batch 问所有问题。** 节奏：

1. 评估当前剩余 OR，算每个问题的 impact 分数。
2. 用 `AskUserQuestion` 问 **1–2 个** 最高分问题。
3. 根据答案重新评估剩余 OR（通常会折叠一批并让部分问题失效）。
4. 回第 1 步，直到停止条件。

## 停止条件

任一触发即结束 inquiry：
- 所有 Type A OR 已折叠。
- 剩余 OR 全是 Type B（没有约束型问题能塌缩它们）。
- 连问 3 个问题无新折叠（diminishing returns）。

## 产出

写入 `INQUIRY.md`（见 `templates/INQUIRY.md`）：

```markdown
## Collapsed OR Nodes
| OR 节点 | 问题 | 答案 | 决策 | 理由 |
|---------|------|------|------|------|

## Remaining OR Nodes (→ spike)
| OR 节点 | 为何不确定 | Spike scope |
|---------|-----------|-------------|

## Updated DAG
（改动落在 dag.json，PLAN.md 视图同步）
```

**更新 dag.json**（source of truth）：
- 被塌缩的 OR：`or_groups[].decided` 设为获胜 OR_HEAD 的 id；被弃候选 id 加入 `or_groups[].rejected`；被弃的 OR_HEAD 节点 `status="abandoned"`；获胜的保持 `"pending"` 等进 dev。
- 改完跑 `python3 scripts/validate_dag.py .auto-dev/dag.json`，非零 → 停（`dag-schema-invalid`）。

再同步 PLAN.md 的节点表 / OR 候选对照，更新 `.auto-dev/state.json`：
- 仍有 `or_type == "B"` 且未 decided 的 or_group → `phase=spike`
- 无 → `phase=dev`

## 注意

- 问题必须是**人类不用翻代码就能答**的。需要人类研究才能答的 → 改做 spike。
- 不要问"你更喜欢 A 还是 B"。偏好不是约束。
- Inquiry 总问题数的软上限：6。超了说明 design 里 OR 过多或 Type 判错。
- 此阶段禁止写代码、切分支。允许改动仅限：dag.json（折叠 OR / 更新 or_groups）、PLAN.md（同步视图）、INQUIRY.md、state.json。
