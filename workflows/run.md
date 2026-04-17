# Run 工作流

合并旧的 node-cycle / review-gate。每节点跑 Plan/Dev/Test，失败就重试到 limit，再失败就停下让人类重编排。

---

## 每节点一轮

### 1. 选节点

从 `.auto-dev/dag.json` 找所有 `status == "pending"` 且所有入边 `from` 节点 `status == "done"` 的节点，按拓扑序取一个（common successor 优先，然后沿已进入的 OR 分支推进）。

### 2. 读节点 md

读 `.auto-dev/nodes/<id>.md`：frontmatter 拿到 `branch` / `deps` / `or_candidate_of`；正文拿到 Entry / Completion / Scope / Retry limit / Escalation 建议。

更新 dag.json 该节点 `status="dev"`，更新 state.json 的 `current_node` / `current_branch` / `retry_count=0`。

### 3. 切分支

按 frontmatter `branch`：
- `ai-main`（common successor）：本地 base_branch。
- `or/<desc>`（OR 候选首节点）：从 common successor tag 切出，**切出前跑一次 upstream → base 同步**（见 SKILL.md 同步协议）。
- `and/<parent>-<desc>`：从父分支切出。

绝不切到 `main` / `master`。

### 4. Plan（进 dev 前）

- 遍历节点 md 的 Entry 列表，确认每项引用的 `node/<id>` tag 已存在（`git tag -l`）。
- 缺失 → 停（`entry-missing`）。

### 5. Dev

- 实现，严守 Scope（max_files / max_new_deps）。超 scope 立刻停（`scope-overflow`），不要夹带。
- 不夹带无关改动；想顺手清理的 → 作为新节点加到 dag.json 和 `.auto-dev/nodes/`，不当前做。

### 6. Test

跑节点 Completion 指定的测试 + 项目全量测试。

- **通过** → 进通过流程。
- **基线回退**（原本通过的测试现在失败）→ 停（`test-baseline-regression`）。
- **失败** → retry_count += 1：
  - 未到 limit → 同分支新 commit 重试。
  - 到 limit → 停（`node-stuck`），在 NEEDS_REVIEW 里列出：失败信号、你试过什么、从 Escalation 菜单里**建议**哪条动作（改节点 md / 改 dag.json / 弃 OR 分支）。人类改完重启即继续。

### 7. 通过流程

1. **独立 code review**：commit 前派 `general-purpose` subagent 看 diff，问：触到根因了吗？有回归风险吗？是否用"绕过"代替"修复"（吞异常、改测试期望、加特殊分支）？有问题 → 处理后重 test。
2. **Commit**：`<type>(<node-id>): <summary>`，body 带 completion 通过证据。
3. **Tag**：`git tag node/<id>`。
4. **AND merge-back**（节点 branch 形如 `and/*`）：回父分支 `git merge --no-ff and/<parent>-<desc>`，父分支打 tag 标记已回合。
5. **更新 dag.json**：该节点 `status="done"`，`completion_tag="node/<id>"`。跑 validate_dag.py，非零 → 停（`dag-schema-invalid`）。
6. **JOURNAL**：追加一段（时间 / tag / 结论 / 下一节点）。
7. **state.json**：`last_tag` / `dag_cursor` 指向下一节点；`retry_count=0`。

### 8. OR 分支完成检查

若刚完成节点所在 OR 分支从首节点到终节点全部 `status=done` → 停（`or-branch-review`），等人类做 PR 到 upstream。

---

## 停止原因清单

| tag | 触发 |
|-----|------|
| `dag-schema-invalid` | `validate_dag.py` 非零 |
| `node-stuck` | 节点重试达 limit，需要人类重编排 |
| `entry-missing` | 节点前置 tag 不存在 |
| `scope-overflow` | 实际改动超节点 Scope |
| `or-decision-needed` | spike 全部完成，等人类在 dag.json 写 `or_groups[].decided` |
| `or-branch-review` | OR 分支端到端完成，等人类 review + PR |
| `safety-boundary` | 命中 `safety.md` 黑名单 |
| `test-baseline-regression` | 原本通过的用例现在失败 |
| `protected-push-attempted` | 对 upstream/受保护分支的任何写操作，或未授权 push base_branch |
| `upstream-sync-conflict` | upstream → base 同步有冲突 |
| `missing-credential` | 外部凭证/服务不可用 |

---

## 禁止

- 不为过测试改/删已有断言。
- 不用 `try/except pass` / `@ts-ignore` / 注释断言 掩盖问题。
- 不 skip / xfail 已有测试。
- 不 `--no-verify` 跳 hook。
- 不在一个节点里跨节点动其他节点的文件。

## 注意

- 图的质量由你自己判断。validator 过了不等于图对；validator 不过肯定是图崩了。
- 节点 md 是 spec，dag.json 是骨架。两者不一致时以 dag.json 的 id 和 edges 为拓扑真相，以节点 md 的正文为执行真相。发现不一致停下修，不要硬跑。
