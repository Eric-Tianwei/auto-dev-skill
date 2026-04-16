---
name: auto-dev
description: Long-running autonomous development loop for bypass-permissions sessions. Pulls tasks from a backlog, runs feature/bug workflows, records progress, and stops at safety boundaries.
---

# auto-dev

用于在 `--dangerously-skip-permissions` 下持续数小时无人值守开发。主循环从 backlog 取任务、按类型走对应工作流、写日志、触到边界停下等用户。

## 核心文件（项目根目录）

- `BACKLOG.md` — 待办队列。用户下发任务的入口。格式见 `templates/BACKLOG.md`。
- `JOURNAL.md` — 完成日志。每条任务追加一行，供用户回顾。
- `NEEDS_REVIEW.md` — 阻塞项。触到安全边界或连续失败时写入，随后停下。
- `.auto-dev/state.json` — 当前任务、尝试次数、起始分支等运行时状态，防 compact 丢失。

这四个文件的位置固定，不要放到别处。

## 主循环

1. 读 `BACKLOG.md`，取第一条状态为 `todo` 的任务。没有 → 写 JOURNAL 总结后停。
2. 标记该任务为 `in-progress`，写入 `.auto-dev/state.json`。
3. 按 `type` 分派：
   - `feature` → 读 `workflows/feature.md`
   - `bug` → 读 `workflows/bug.md`
4. 工作流完成后：更新 backlog 状态为 `done` 或 `blocked`，追加 JOURNAL，清 state。
5. 检查**停止条件**（见下）；未触发则回到第 1 步。

## 停止条件（任一触发即停下写 NEEDS_REVIEW）

- Backlog 清空。
- 同一任务连续 2 次失败（测试/构建/复现都算）。
- 命中安全黑名单（见 `safety.md`，待定）。
- 测试基线相对起始 commit 回退（原本通过的用例现在失败）。
- 主分支 `main` 被意外修改。
- 需要的凭证/外部服务不可用。

停下时：在 `NEEDS_REVIEW.md` 追加一段（时间、任务 id、现象、已尝试方案、建议），然后结束会话，不要自己重试第 3 次。

## Subagent 使用原则

只在这四类场景派 subagent；其余主循环亲自做。

1. **深度搜索** → `subagent_type: Explore`。
2. **并行 feature 变体** → `general-purpose` + `isolation: worktree`，每个方案一个 agent，回传分支名+设计备忘。
3. **独立 code review** → bug 修复 commit 前派一个独立 agent 审查。
4. **Bug 最小复现 + 失败测试** → 派 agent 产出复现脚本和红色测试，主循环接手修。

**硬规则**：subagent 不得修改 `BACKLOG.md` / `JOURNAL.md` / `NEEDS_REVIEW.md` / `.auto-dev/state.json` / git 分支状态。状态改动一律由主循环在看到 subagent 结果后执行。

## 工作流文档

需要时用 Read 加载：

- `workflows/feature.md` — feature 类任务流程
- `workflows/bug.md` — bug 类任务流程
- `safety.md` — 安全边界清单（待用户敲定）

## 与用户沟通

- 默认不打断。进度都落到 JOURNAL，用户自己看。
- 只有停止条件触发时才停。停下后用一两句话告诉用户"停在哪、为什么、看 NEEDS_REVIEW"。
- 不要在 JOURNAL / NEEDS_REVIEW 里写冗长总结；一条 3–6 行够了。
