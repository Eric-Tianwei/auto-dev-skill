# Node Cycle 工作流

每个 DAG 节点都跑一次 Plan/Dev/Test。测试失败按三级升级判定。

## 进入节点

1. 读 `PLAN.md` 中当前节点的规范（entry / completion / scope / retry N / L1 触发 / L2 触发）。
2. 切到正确分支（`<base>` 指 `.auto-dev/state.json.base_branch`，默认 `ai-main`）：
   - SEQ 节点：留在父分支上线性 commit。
   - AND 节点：`git checkout -b and/<parent>-<desc>` 从父切出。
   - OR 分支首节点：从 common successor tag 切 `or/<desc>`。**切出前执行一次 upstream → base 同步检查**（见 SKILL.md「同步协议」）。
   - Common successor：**本地 `<base>` 分支**（由 safety.md 允许）。**绝不**切到 `main` / `master`。
3. 更新 `.auto-dev/state.json`：`current_node` / `current_branch` / `retry_count=0`。

## Plan（进 dev 前）

- 确认所有 entry assumptions 对应的 tag 已存在（`git tag -l node/<prerequisite>`）。
- 缺失 → 写 NEEDS_REVIEW（`entry-missing`）停。

## Dev

- 实现，严守 scope limit（max files / max new deps）。
- 超 scope → 立刻停下写 NEEDS_REVIEW（`scope-overflow`），**不要**夹带。
- 不夹带无关改动。看到顺手想清理的 → 作为新节点进 PLAN，不当前做。

## Test

跑该节点 completion condition 指定的测试（加跑项目全量测试验基线）。

- 通过 → 进"通过流程"。
- 失败 → 进"失败判级"。

### 测试基线

节点 Plan 阶段记录起始 commit 的测试基线。跑完后对比：原本通过的用例现在失败 → `test-baseline-regression` 即刻停（哪怕本节点 completion 通过）。

## 失败判级（三级表）

| 级别 | 特征 | 动作 |
|------|------|------|
| **L0 实现细节** | 失败在实现细节（off-by-one、算法、边界）；改本节点代码可修；接口不变 | 同分支新 commit 重试；`retry_count += 1`；达 spec N → 升 L1 |
| **L1 父约束不可达** | N 次重试均失败 / 失败指向父接口而非实现 / completion condition 在当前输入下不可能成立 | 打 tag `failed/<name>-<reason>`；写 NEEDS_REVIEW（`level-1-escalation`）**等人类批准父修改**；停 |
| **L2 OR 分支假设破产** | 父改了也不变 / 多个子节点 L1 指向同一根因 / OR 核心假设违反需求 | 打 tag `decision/abandoned-<branch>-<reason>`；写 NEEDS_REVIEW（`level-2-escalation`）**等人类确认新 OR 候选**；停 |

**重试上限 N 必须在 Plan 阶段设定在节点 spec 里，不在 Dev 时临时改。** 否则 AI 会陷入 L0 无限重试的局部最优陷阱。

区分 L0/L1：看"改本节点代码能否修"。区分 L1/L2：看"改父节点能否修"。两级判定有疑问 → 向高升一级（保守）。

## 通过流程

1. **独立 code review**：commit 前派 `general-purpose` subagent 看 diff，重点问：
   - 是否触到根因（对 bug 型节点）？
   - 是否引入回归风险？
   - 是否用"绕过"代替"修复"（吞异常、改测试期望、加特殊分支）？
   - 有实质问题 → 处理后重 test。
2. **Commit**：消息格式 `<type>(<node-id>): <summary>`，body 含 completion 通过证据一句话。
3. **Tag**：`git tag node/<path>`（path 由 DAG 位置确定，例如 `node/or-jwt-signing`）。
4. **AND merge-back**（只限 AND 节点）：回父分支，`git merge --no-ff and/<parent>-<desc>`，在父分支打 tag 标记该 AND 已回合。
5. **JOURNAL**：追加一段（时间 / tag / 结论 / 下一节点）。
6. **state.json 更新**：`last_tag` / `dag_cursor` 指向下一节点；`retry_count=0`。
7. **review-gate 触发检查**：见 `workflows/review-gate.md`。触发 → 停；否则 → 回主循环取下个节点。

## 禁止

- 不得为让测试通过而改/删已有断言。
- 不得 `try/except pass`、`@ts-ignore`、注释掉断言掩盖问题。
- 不得 skip / xfail 已有测试。
- 不得 `--no-verify` 跳 hook。
- 不得在一个节点里跨 DAG 动别的节点的文件。
