# Review Gate 工作流

结构化人类检查点。每次 `workflows/node-cycle.md` 或 `workflows/spike.md` 完成一步，对照这份清单决定是否停下写 NEEDS_REVIEW。

## 触发即停下的检查点

| 触发 | 停止原因 tag | NEEDS_REVIEW 内容要点 |
|------|-------------|----------------------|
| 所有 spike 完成，OR 候选结论齐 | `or-decision-needed` | 每个 OR 的候选列表、spike 结论、分支 tag、建议选哪条（可有可无） |
| 某条 OR 分支从首节点到终节点全部 node tag 完成 | `or-branch-review` | 分支名、覆盖节点列表、`git diff main or/<x>` 指引 |
| 节点升 L1 | `level-1-escalation` | 节点 id、失败 tag、父节点 id、建议的父修改方向 |
| 节点升 L2 | `level-2-escalation` | OR 分支名、`decision/abandoned-*` tag、根因、建议的新 OR 候选方向（一句话） |
| 连续 2–3 个 SEQ 节点完成且中间未经 checkpoint | `seq-checkpoint` | 已完成节点 tag 序列、当前累计 diff 范围、一句话方向 sanity check 请求 |
| 命中 `safety.md` 黑名单 | `safety-boundary` | 触碰的条款、尝试的操作、建议的替代路径 |
| 测试基线回退 | `test-baseline-regression` | 回退测试列表、最近 node tag、怀疑的 commit |
| 任务要求的凭证/服务不可用 | `missing-credential` | 缺什么、在哪能配 |
| 向远端 push main / 受保护分支 | `protected-push-attempted` | 触发命令、目标 ref、原因 |

## 不触发检查点的场景（继续 autonomous）

- L0 重试（未达 spec N 次）。
- AND 分支 merge 回父分支。
- 单节点 completion tag。
- 每次 commit。
- 本地 main 的 common successor commit。
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
- 主循环读 state.json，`phase=review-gate` → 读最新 NEEDS_REVIEW 段，确认用户是否已在 PLAN.md 留下决策/批准痕迹。
- 有决策 → 按决策设置下一阶段（dev / design / spike），清 review-gate phase。
- 无决策 → 不推进，向用户说明等待什么。

## 注意

- Review-gate 只停"已准备好给人看"的状态：代码 committed、tag 打完、PLAN 状态更新完。不要在不一致状态下停。
- 一次会话可触发多个 review-gate（比如连续两个 L1），但写完第一个就必须结束会话——不要停下后又继续。
