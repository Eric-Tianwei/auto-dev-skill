---
name: auto-dev
version: 2.0.0
description: Long-running autonomous AI coding loop for bypass-permissions sessions. Drives development from a DAG-based plan (SEQ/AND/OR nodes) rather than a flat task list. Handles topological preprocessing of common successors, a pre-dev inquiry phase that collapses OR nodes by asking humans about constraints (not technical choices), parallel spikes for unresolved OR branches via git worktrees, per-node Plan/Dev/Test cycles with three-level failure escalation (L0 retry / L1 redesign parent / L2 abandon branch), and a git topology kept isomorphic to the DAG (or/*, and/*, spike/* branches; node/*, decision/*, spike/result-* tags). Use when the user wants an unattended Claude Code session to plan and build a multi-node feature across hours with minimal interruptions.
---

# auto-dev

用于在 `--dangerously-skip-permissions` 下持续数小时无人值守开发。计划以 DAG 建模，按拓扑顺序推进，在结构化检查点停下等用户。

## Core Principles

```
1. Depth causes drift          → minimize SEQ chain length
2. OR nodes                    → primary human decision points
3. Common successor nodes      → land on main before branching
4. Every node                  → entry assumptions + verifiable completion condition + scope limit + retry limit
5. Test failure escalates      → L0 retry (in-node) → L1 redesign (modify parent) → L2 abandon (new OR candidate)
6. Git topology                → must be isomorphic to DAG topology
7. Inquiry rule                → never ask humans to pick a technical option; ask about the constraint that picks it
8. OR branches                 → never merged with siblings; only one wins, the other is tagged and archived
```

## 核心文件（项目根）

- `PLAN.md` — DAG 本体 + 每节点规范。计划入口，不是任务列表。模板见 `templates/PLAN.md` + `templates/NODE.md`。
- `INQUIRY.md` — Inquiry 阶段输出：已折叠 OR 表 + 剩余待 spike 表 + 更新后 DAG。
- `JOURNAL.md` — 每节点完成、每次升级、每次决策追加一段。
- `NEEDS_REVIEW.md` — 触到停止条件时追加。
- `.auto-dev/state.json` — 运行时状态，防 compact 丢失。字段：

```json
{
  "plan_path": "PLAN.md",
  "phase": "design|inquiry|spike|dev|review-gate",
  "current_node": "<node id or null>",
  "current_branch": "<branch>",
  "retry_count": 0,
  "retry_limit_from_spec": 3,
  "dag_cursor": "<next node id or null>",
  "last_tag": "node/..."
}
```

这些文件的位置固定，不要放到别处。

## 主循环（DAG 游标驱动）

1. 读 `.auto-dev/state.json`。不存在 → 初始化，`phase=design`。
2. 根据 `phase` 选 workflow：
   - `design`  → 读 `workflows/design.md`，产出 `PLAN.md`。完成后 `phase=inquiry`。
   - `inquiry` → 读 `workflows/inquiry.md`，产出 `INQUIRY.md`。**此阶段是唯一允许 AskUserQuestion 的窗口**。完成后：仍有 Type B OR → `phase=spike`；否则 → `phase=dev`。
   - `spike`   → 读 `workflows/spike.md`，派 worktree subagent 并行 spike。全部完成 → 触发 review-gate（`or-decision-needed`），写 NEEDS_REVIEW 停下。
   - `dev`     → 读 `workflows/node-cycle.md`，按拓扑序选下一个可做节点（common successor 优先，然后沿已进入的 OR 分支推进），跑 Plan/Dev/Test。
   - `review-gate` → 读 `workflows/review-gate.md`，写 NEEDS_REVIEW 后停。
3. 节点完成 → 更新 state.json、打 `node/<path>` tag、追加 JOURNAL → 回第 2 步。

## 停止条件（任一触发即停下写 NEEDS_REVIEW）

- 节点 Level 0 重试达该节点 spec 里声明的 N 次 → 升 L1 → 停。
- 节点判定为 Level 1 升级（父节点需修改） → 停，等人类批准。
- 节点判定为 Level 2 升级（OR 分支假设破产） → 停，等人类批准新 OR 候选。
- 所有 spike 完成（`phase=spike` 结束） → 停，等 OR 决策。
- OR 分支端到端开发完成 → 停，等 PR review。
- SEQ 链 checkpoint（每 2–3 个连续 SEQ 节点）→ 停，方向 sanity check。
- 命中 `safety.md` 黑名单。
- 测试基线相对 DAG 起始 commit 回退（原本通过的用例现在失败）。
- 向远端 push `main` / `master` / 受保护分支（任何形式） → 停。注意：本地 main commit 合法（common successor 合法落点）。
- 需要的凭证/外部服务不可用。

停下时：`NEEDS_REVIEW.md` 追加一段（时间、节点 id / tag、停止原因 tag、现象、已尝试、建议），结束会话，不要自己绕过。

## Subagent 使用原则

只在这四类场景派 subagent；其余主循环亲自做。

1. **深度搜索** → `subagent_type: Explore`。
2. **Type B OR spike** → `general-purpose` + `isolation: worktree`。由 `workflows/spike.md` 触发，每个 OR 一个 agent，prompt 必含假设/判据/预算，回传 `spike/result-*` tag + 一页结论。
3. **独立 code review** → 每次节点 commit 前派一个 agent 独立审查 diff（不再局限于 bug 修复）。
4. **节点内的最小复现或辅助搜索** → 按 `workflows/node-cycle.md` 需要派。

**硬规则**：subagent 不得修改 `PLAN.md` / `INQUIRY.md` / `JOURNAL.md` / `NEEDS_REVIEW.md` / `.auto-dev/state.json` / git 分支或 tag 状态。状态改动一律由主循环在看到 subagent 结果后执行。

## 工作流文档

需要时按阶段加载，不要首轮全读。

- `workflows/design.md` — DAG 建模与节点规范
- `workflows/inquiry.md` — 约束型提问，折叠 Type A OR
- `workflows/spike.md` — Type B OR 并行 spike
- `workflows/node-cycle.md` — 节点 Plan/Dev/Test + 三级失败升级 + git 分支/tag 操作
- `workflows/review-gate.md` — 结构化人类检查点清单
- `safety.md` — 安全边界黑白名单

## 执行模式

- **不要进入 Plan 模式**：不用 `EnterPlanMode` / `ExitPlanMode`，不生成计划后等用户确认。
- **不要询问确认**：不用 `AskUserQuestion`，**除了** `workflows/inquiry.md` 阶段——那是唯一允许的提问窗口，进入 dev 后立即回到无人值守。
- Inquiry 的问题必须遵循约束翻译规则（见 `workflows/inquiry.md`）：不问技术选型，只问驱动技术选型的业务/产品约束。
- 唯一"停下"的方式是触发停止条件 → 写 NEEDS_REVIEW → 结束。

## 与用户沟通

- 默认不打断。节点完成与升级事件都落到 JOURNAL，用户自己看。
- 只有停止条件触发时才停下，一两句话告诉用户"停在哪、为什么、看 NEEDS_REVIEW"。
- JOURNAL / NEEDS_REVIEW 条目保持 3–6 行，不写冗长总结。
