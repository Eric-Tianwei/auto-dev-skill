# Review Gate 工作流

结构化人类检查点。每次 `workflows/node-cycle.md` 或 `workflows/spike.md` 完成一步，对照这份清单决定是否停下写 NEEDS_REVIEW。

**判定数据源永远是 `.auto-dev/dag.json`**。checkpoint 判定看 `edges[].type`，不看"我连做了几个节点"的执行计数。PLAN.md 的文字描述不是判据。

## 触发即停下的检查点

| 触发 | 停止原因 tag | NEEDS_REVIEW 内容要点 |
|------|-------------|----------------------|
| **`validate_dag.py` 退出码非零** | `dag-schema-invalid` | validator stderr 输出、怀疑的 dag.json 段落、建议修改点 |
| 所有 spike 完成，OR 候选结论齐 | `or-decision-needed` | 每个 OR 的候选列表、spike 结论、分支 tag、建议选哪条（可有可无） |
| 某条 OR 分支从首节点到终节点全部 node tag 完成 | `or-branch-review` | 分支名、覆盖节点列表、`git diff <base_branch> or/<x>` 指引（人类 review 后自行 PR 到 `upstream_branch`） |
| 节点升 L1 | `level-1-escalation` | 节点 id、失败 tag、父节点 id、建议的父修改方向 |
| 节点升 L2 | `level-2-escalation` | OR 分支名、`decision/abandoned-*` tag、根因、建议的新 OR 候选方向（一句话） |
| **沿 dag.edges 回溯，有 2–3 条首尾相连的 `type="SEQ"` 边全部完成且未经 checkpoint** | `seq-checkpoint` | 这条 SEQ 链涉及的节点 tag 序列、当前累计 diff 范围、一句话方向 sanity check 请求 |
| 命中 `safety.md` 黑名单 | `safety-boundary` | 触碰的条款、尝试的操作、建议的替代路径 |
| 测试基线回退 | `test-baseline-regression` | 回退测试列表、最近 node tag、怀疑的 commit |
| 任务要求的凭证/服务不可用 | `missing-credential` | 缺什么、在哪能配 |
| 对 `upstream_branch` / `master` 的任何写操作，或向远端 push 受保护分支 | `protected-push-attempted` | 触发命令、目标 ref、原因 |
| `upstream_branch → base_branch` 同步出现冲突 | `upstream-sync-conflict` | 冲突文件列表、upstream 最新 commit、base_branch 当前 HEAD、建议的解冲突方向 |

### seq-checkpoint 判定算法（精确）

节点 `X` 完成时：
1. 从 dag.json 取 `X` 的最近完成祖先链（按 `completion_tag != null`）。
2. 沿入边回溯：若 `edge.type == "SEQ"` 且 `edge.from` 的 `status == "done"`，计数 +1；遇到 AND/OR 边或 status 非 done 即停。
3. 若连续 SEQ 边数 ≥ 2（即 3 个节点首尾相连全 done），触发 `seq-checkpoint`。
4. 触发后在 JOURNAL 记一行 `seq-checkpoint passed at node/<X>`，下次计数从 X 之后重新开始。

**AND 兄弟节点连续完成不计入本项**——它们之间没有 SEQ 边。

## 不触发检查点的场景（继续 autonomous）

- L0 重试（未达 spec N 次）。
- AND 分支 merge 回父分支。
- **AND 兄弟节点连续完成**（它们之间是 AND 边，不是 SEQ；即使 3 个、5 个连续做完也不算 seq-checkpoint）。
- 单节点 completion tag。
- 每次 commit。
- 本地 `base_branch`（默认 `ai-main`）的 common successor commit。
- 无冲突的 `upstream_branch → base_branch` 同步 merge。
- Inquiry 阶段的 AskUserQuestion（那不是 review-gate，是 inquiry 内机制）。

## 写 NEEDS_REVIEW 的格式

```markdown
## <YYYY-MM-DD HH:MM> · <node-id-or-tag> · <停止原因 tag>
- 现象: <一行>
- 已尝试: <一行>
- 建议: <一行，给用户的下一步>
- 状态: <PLAN 里对应节点/分支标的状态>
```

写完调用流程：
1. 追加一段到 `NEEDS_REVIEW.md`。
2. 同步更新 `PLAN.md` 中涉及节点的状态（`blocked` / `pending-review` / `abandoned`）。
3. 更新 `.auto-dev/state.json`：`phase=review-gate`，记录触发原因。
4. 向用户输出一两句话："停在 <tag>，原因 <停止原因>，详情见 NEEDS_REVIEW.md。"
5. 结束会话。

## 恢复

用户处理完 NEEDS_REVIEW 后下一次启动：
- 主循环读 state.json，`phase=review-gate` → 读最新 NEEDS_REVIEW 段，确认用户是否已在 **dag.json**（例如 `or_groups[].decided`、节点 `status`）或 NEEDS_REVIEW 里留下决策/批准痕迹。PLAN.md 文字不算决策依据。
- 有决策 → 按决策设置下一阶段（dev / design / spike），清 review-gate phase。
- 无决策 → 不推进，向用户说明等待什么。

## 注意

- Review-gate 只停"已准备好给人看"的状态：代码 committed、tag 打完、PLAN 状态更新完。不要在不一致状态下停。
- 一次会话可触发多个 review-gate（比如连续两个 L1），但写完第一个就必须结束会话——不要停下后又继续。
