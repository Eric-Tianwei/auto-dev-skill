---
name: auto-dev
version: 3.3.0
description: Long-running autonomous AI coding loop for bypass-permissions sessions. Plans as a DAG of per-node markdown specs plus a minimal JSON skeleton — not a giant narrated plan. Orchestration decisions (node / edge / or / phase) go through the `auto-dev` CLI, which emits event lines and an append-only events.log so the causal chain survives context compaction. Two workflows (plan / run), two-action failure handling (retry / stop for human reorchestration), validator only catches JSON/topology collapse and leaves graph quality to the AI. Use when the user wants an unattended Claude Code session to plan and build a multi-node feature across hours with minimal interruptions.
---

# auto-dev

在 `--dangerously-skip-permissions` 下无人值守开发。计划是一张 DAG：骨架在 `.auto-dev/dag.json`，每节点 spec 在 `.auto-dev/nodes/<id>.md`。**编排决策走 `auto-dev` CLI**——增节点 / 连边 / 定 OR / 改状态都是一条命令，每条写操作印一行事件并追加 `.auto-dev/events.log`，会话被压缩后 `auto-dev log` 一键回溯。

## Core Principles

```
1. 节点 = 一个 md 文件（frontmatter + 正文）
2. DAG = 极简骨架 + OR 组
3. 结构决策 + 机械可推导的 bookkeeping 走 CLI（产出事件）；需要人类判断的叙事（PLAN / JOURNAL / NEEDS_REVIEW / 节点 md 正文）直接 Edit
4. CLI 是糖，不是墙：直接编辑 .auto-dev/** 依然合法，用 validator 兜底
5. 图的质量由 AI 判断，validator 只兜底 JSON/拓扑崩塌
6. 失败只分两态：重试 vs 停下让人类重编排
7. 每个节点 → 可验证 completion + scope limit + retry limit
8. Git topology isomorphic to DAG（or/*, and/*, spike/* 分支；node/*, decision/*, spike/result-* tag）
9. Inquiry 规则：不问技术选型，问驱动选型的业务/产品约束
10. OR 分支 never merged with siblings；胜者留下，败者 tag + archive
11. AI never touches upstream：main/master 人类专属；AI 在 base_branch (ai-main)
```

## CLI 速查

调用形式：`python3 <skill-dir>/scripts/auto-dev.py <cmd>`。下文写 `auto-dev` 为简称。

**把 `scripts/auto-dev.py` 当黑盒**——执行时不要 Read 它的源码。能力查本节速查表；参数查 `auto-dev <cmd> --help`；实在搞不定看错误输出（`! <reason>`）+ 退出码。读源码 = 把 JSON/state 实现细节塞回你上下文，等于白抽象。例外：**你在开发/修改这个 skill 本身**。

| 命令 | 作用 |
|---|---|
| `init [--base B] [--upstream U] [--force]` | 建 `.auto-dev/` 骨架（dag.json / state.json / nodes/ / schema/ / events.log） |
| `node add <id> [--deps a,b] [--branch B] [--or-of G] [--name N] [--desc D] [--body-stdin]` | 建节点：写 `.auto-dev/nodes/<id>.md`、登记 `dag.nodes`、连 deps 边。`--body-stdin` 时从 stdin 读 body（heredoc 一次写完 Entry/Completion/Scope/Retry/Escalation，**推荐首次填充走这条路**，省 Read+多次 Edit 的 round-trip） |
| `node rm <id>` | 删节点 + 级联边 + 同步子节点 md `deps` + OR 组候选清理（<2 连带删组） |
| `node status <id> <pending\|dev\|done\|blocked\|abandoned> [--tag T]` | 改状态（done 时带 tag）。**dev** 自动写 `current_node / current_branch / retry_count=0`；**done** 自动写 `last_tag / retry_count=0 / dag_cursor`（下一 ready），并清 `current_node`。 |
| `finish <id> [--type T] [--extra-message M] [--note N] [--tag T] [--project DIR]` | **一把梭收尾**：git add -A → commit（msg 自动拼 `<type>(<id>): <desc>` + Completion checklist + `--extra-message` + Co-Authored-By）→ tag（默认 `node/<id>`）→ `node status done --tag` → JOURNAL append 一段。git 错误原样透传；tag 已存在 / 无 stage 改动会 die。节省每节点 5+ 个 tool call。|
| `edge add <from> <to>` / `edge rm <from> <to>` | 补/删边；自动同步 `<to>.md` frontmatter `deps` |
| `or create <id> --candidates a,b,c` | 新 OR 组；候选 md frontmatter 写 `or_candidate_of` |
| `or decide <id> <winner>` | 定胜负；败者节点自动 `status=abandoned` |
| `phase set <plan\|dev\|review-gate>` | 切阶段；设 dev 会先跑 validate，失败拒绝；并算首个 ready 作 `dag_cursor` |
| `validate` | 包 `validate_dag.py`，非零退出码 5 |
| `status [--json]` | 单屏：phase / cursor / ready / current / pending-or / counts |
| `nodes [--json] [--filter S]` | 每节点密集视图：id / status / branch / deps / **needs（Entry）/ produces（Completion）** —— 编排完节点、准备连边时看这一屏 |
| `log [--tail N]` / `log --head N` | 打印 events.log |

**事件行前缀**：`+` 创建 / `-` 删除 / `~` 属性变更 / `>` 状态变更 / `✓` 校验过/收尾完成 / `!` 错误 / `?` 状态查询。事件只在**写**成功后追加 log；`validate` / `status` / `log` 是读操作，不写 log。

**cwd 规则**：CLI 会从当前目录向上递归找 `.auto-dev/`（类似 git 找 `.git`），找到后 chdir 到那个目录再执行。你在子项目目录跑 `auto-dev status` 也不用 cd 回根。例外：`init` 始终在当前 cwd 建骨架。

**退出码**：0 成功 / 1 用法 / 2 状态（.auto-dev 缺失/会破坏一致性）/ 3 not-found / 4 冲突（存在/成环/已决定）/ 5 validate 失败。

## 文件所有权

| 路径 | 谁写 |
|---|---|
| `.auto-dev/dag.json` / `events.log` / `schema/**` | **CLI 专属**（AI 直改也行但会丢事件） |
| `.auto-dev/state.json` 运行时字段（`current_node` / `current_branch` / `retry_count` / `last_tag` / `dag_cursor`） | **CLI 自动推**（`node status` / `finish` / `phase set` 内同步）。AI 仅在重试 +1、upstream_sync 这些 CLI 覆盖不到的场景直接 Edit。 |
| `.auto-dev/nodes/<id>.md` frontmatter | CLI（`node add` / `edge add/rm` / `or create` 会自动维护 `deps` 和 `or_candidate_of`） |
| `.auto-dev/nodes/<id>.md` 正文（Entry / Completion / Scope / Retry / Escalation） | AI 直接 Edit |
| `PLAN.md` / `JOURNAL.md` / `NEEDS_REVIEW.md` | AI 直接 Edit（`finish` 会自动追加一段 JOURNAL，其他 Edit 照旧） |
| git branches / tags | 主循环用 git 命令；`finish` 负责每节点的 commit + tag |

原则：**结构决策 + 机械可推导的 bookkeeping 走 CLI 以产出事件；需要人类判断的叙事直接 Edit**。

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

**首次初始化**：`.auto-dev/state.json` 不存在时跑 `auto-dev init`（可 `--base` / `--upstream` 指定，默认 `ai-main` / `main`）；若 base 不存在从当前 HEAD 建。

**同步时机**：`phase=plan → dev` 切换时、每次开 `or/*` 分支前跑 `git fetch && git log --oneline base_branch..upstream_branch`。可快进则 AI 自合；冲突则停。

## 主循环

1. 若 `.auto-dev/` 不存在 → 跑 `auto-dev init`。
2. 读 state.json 的 `phase`；若 `phase != plan`，跑 `auto-dev validate`。非零 → 停（`dag-schema-invalid`）。
3. 按 phase 选 workflow：
   - `plan` → `workflows/plan.md`。完成后 `auto-dev phase set dev`。
   - `dev` → `workflows/run.md`：从 `auto-dev status` 取 `cursor` / `ready`；读 `.auto-dev/nodes/<id>.md` 跑 Plan/Dev/Test。
   - `review-gate` → 已写 NEEDS_REVIEW，停。
4. 节点完成 → `auto-dev finish <id>`（一把梭：commit + tag + status done + JOURNAL）→ 回第 2 步。

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
