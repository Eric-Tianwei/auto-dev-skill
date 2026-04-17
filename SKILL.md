---
name: auto-dev
version: 3.0.0
description: Long-running autonomous AI coding loop for bypass-permissions sessions. Plans as a DAG of per-node markdown specs plus a minimal JSON skeleton — not a giant narrated plan. Two workflows (plan / run), two-action failure handling (retry / stop for human reorchestration), validator only catches JSON/topology collapse and leaves graph quality to the AI. Use when the user wants an unattended Claude Code session to plan and build a multi-node feature across hours with minimal interruptions.
---

# auto-dev

在 `--dangerously-skip-permissions` 下无人值守开发。计划是一张 DAG：骨架（id + 边）在 `.auto-dev/dag.json`，每个节点的详细 spec 在 `.auto-dev/nodes/<id>.md`。执行时逐个节点读 spec 跑 Plan/Dev/Test。

## Core Principles

```
1. 节点 = 一个 md 文件（frontmatter: name/description/deps/branch；正文: Entry/Completion/Scope/Retry/Escalation）
2. DAG = 极简骨架：nodes[].id + edges[{from,to}] + or_groups（无边类型、无 rationale、无 kind）
3. 图的质量由 AI 判断，validator 只兜底 JSON/拓扑崩塌
4. 失败只分两态：重试 vs 停下让人类重编排（不再 L0/L1/L2）
5. 每个节点 → 可验证 completion + scope limit + retry limit
6. Git topology isomorphic to DAG（or/*, and/*, spike/* 分支；node/*, decision/*, spike/result-* tag）
7. Inquiry 规则：不问技术选型，问驱动选型的业务/产品约束
8. OR 分支 never merged with siblings；胜者留下，败者 tag + archive
9. AI never touches upstream：main/master 人类专属；AI 在 base_branch (ai-main)，人类做 PR
```

## 核心文件

### Skill 侧（本仓）

- `workflows/plan.md` — 规划阶段（合并 design + inquiry + spike）
- `workflows/run.md` — 执行阶段（合并 node-cycle + review-gate）
- `templates/node.md` — 节点 md 模板
- `templates/dag.schema.json` — DAG JSON Schema
- `templates/dag.example.json` — DAG 示例
- `templates/JOURNAL.md` / `templates/NEEDS_REVIEW.md` — 产出模板
- `scripts/validate_dag.py` — 零依赖 Python 校验器
- `safety.md` — 安全边界

### 使用者仓库侧

```
.auto-dev/
  dag.json                 # 编排骨架
  state.json               # 运行时状态
  schema/dag.schema.json   # schema 副本
  nodes/<id>.md            # 每节点一个 spec
PLAN.md                    # 可选 mermaid 视图（从 dag.json 生成）
JOURNAL.md
NEEDS_REVIEW.md
```

`.auto-dev/state.json` 字段：

```json
{
  "phase": "plan|dev|review-gate",
  "base_branch": "ai-main",
  "upstream_branch": "main",
  "last_upstream_sync": "<ISO or null>",
  "current_node": "<id or null>",
  "current_branch": "<branch>",
  "retry_count": 0,
  "dag_cursor": "<next id or null>",
  "last_tag": "node/...",
  "skill_version": "3.0.0"
}
```

## Base / upstream 分离

AI 在 `base_branch`（默认 `ai-main`）工作；`upstream_branch`（默认 `main`）是人类主线。

| 动作 | 允许方 |
|------|--------|
| `base_branch` 本地 commit | AI |
| 从 `base_branch` 开 `or/*` `and/*` `spike/*` | AI |
| `git push base_branch` 到远端 | AI 不得（除非 safety.md 显式授权） |
| `base_branch` → `upstream_branch` 合并/PR | 仅人类 |
| `upstream_branch` → `base_branch` 同步 | AI 可；冲突则停（`upstream-sync-conflict`） |
| 直接写 `upstream_branch` | AI 绝不（`protected-push-attempted`） |

**首次初始化**：`.auto-dev/state.json` 不存在时读取/询问 `base_branch` / `upstream_branch`，默认 `ai-main` / `main`；若 base 不存在从当前 HEAD 建。

**同步时机**：`phase=plan → dev` 切换时、每次开 `or/*` 分支前跑 `git fetch && git log --oneline base_branch..upstream_branch`。可快进则 AI 自合；冲突则停。

## 主循环

1. 读 `.auto-dev/state.json`，不存在则初始化 `phase=plan`。
2. 若 `phase != plan`，先跑 `python3 scripts/validate_dag.py .auto-dev/dag.json`。非零 → 停（`dag-schema-invalid`）。
3. 按 `phase` 选 workflow：
   - `plan` → `workflows/plan.md`。完成后 `phase=dev`。
   - `dev` → `workflows/run.md`：按拓扑序取下一可做节点，读 `.auto-dev/nodes/<id>.md` 跑 Plan/Dev/Test。
   - `review-gate` → 已写好 NEEDS_REVIEW，停。
4. 节点完成 → 更新 dag.json 里该节点 `status="done"` / `completion_tag` → 打 git tag → 追加 JOURNAL → 回第 2 步。

## Subagent 使用

只在这四类场景派：

1. **深度搜索** → `Explore`（只读）。
2. **Type B OR spike** → `general-purpose` + `isolation: worktree`，每 OR 候选一个。
3. **每节点 commit 前独立 code review** → `general-purpose`。
4. **节点内最小复现/辅助搜索**。

**硬规则**：subagent 不得修改 `.auto-dev/**` / `PLAN.md` / `JOURNAL.md` / `NEEDS_REVIEW.md` / git 分支或 tag 状态。状态改动由主循环执行。

## 执行模式

- 不进入 Plan 模式（不用 `EnterPlanMode`），不等用户确认。
- 不 `AskUserQuestion`，**例外**：`plan.md` 的 Inquiry 步骤——进 dev 后立即回到无人值守。
- 唯一"停下"方式：触发停止条件 → 写 NEEDS_REVIEW → 结束。

## 与用户沟通

- 默认不打断。节点完成/失败都落 JOURNAL，用户自看。
- 停止时一两句话告诉用户停在哪、看 NEEDS_REVIEW。
- JOURNAL / NEEDS_REVIEW 条目 3–6 行，不写冗长总结。
