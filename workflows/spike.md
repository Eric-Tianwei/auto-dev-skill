# Spike 工作流

处理 Inquiry 后剩余的 Type B OR 节点。每个 OR 派一个 worktree subagent 独立验证，最后汇总交人类决策。

## 触发

`.auto-dev/state.json` 中 `phase=spike` 且 dag.json 存在 `or_type == "B"` 且 `decided == null` 的 `or_groups[]` 条目。

## 每个 Type B OR 的处理

1. **建分支**：`spike/<desc>`（每个 OR 候选一个）。
2. **派 subagent**：`subagent_type: general-purpose` + `isolation: worktree`。prompt 必须包含：
   - 要验证的**具体假设**（一句话，可证伪）。
   - **成功判据**（什么情况算这个候选可行）+ **失败判据**。
   - **预算**：最多 ≤N 文件、≤M commit、≤若干分钟（主循环设定）。
   - **禁止**：改 `.auto-dev/dag.json` / `.auto-dev/schema/` / `.auto-dev/state.json` / `PLAN.md` / `INQUIRY.md` / `JOURNAL.md` / `NEEDS_REVIEW.md` / `base_branch`（默认 `ai-main`）/ `upstream_branch`（默认 `main`）/ 其他 spike 分支。
   - **产出要求**：
     - `spike/<desc>/RESULT.md` ≤ 50 行：假设、方法、结果数据、结论（go/no-go + 依据）、风险。
     - 分支上打 tag `spike/result-<desc>`。
     - 回传给主循环：分支名、tag 名、结论一句话。
3. **并行**：所有 spike 同一批派出。`Agent` 工具同一条消息多个 tool_use 即并行。

## 汇总

所有 spike 回来后（同步等齐），主循环：

1. 读各自 `RESULT.md`，在 `JOURNAL.md` 追加一段，每 spike 一行（tag + 结论）。
2. 在 `INQUIRY.md` 末尾追加一节 **Spike Summary**：各 OR 候选的结论对照表。
3. **触发 review-gate**（`or-decision-needed`）：写 `NEEDS_REVIEW.md`，列出每个 OR 的候选和建议，**停下等人类决策**。不得自己选。

## 人类决策后（下一次启动）

用户在 dag.json 的 `or_groups[].decided` 字段写入获胜 OR_HEAD id（并把其余候选加入 `rejected`）。主循环：
1. 跑 `validate_dag.py`，非零 → 停。
2. 对每个已决策的 or_group：
   - 获胜候选对应的 OR_HEAD 节点 `status` 保持 `"pending"`（等进 dev）。
   - 被弃候选 OR_HEAD `status="abandoned"`。
   - 打 git tag：`decision/selected-<branch>` 于获胜分支；`decision/rejected-<branch>-<reason>` 于每个被弃分支（tag 永久保留状态，分支可删）。
3. 同步 PLAN.md 视图。
4. 更新 `.auto-dev/state.json`：`phase=dev`，`dag_cursor` 指向所选分支的首节点。

## 失败处理

- Spike subagent 超预算未结论 → 该 OR 标 `inconclusive`，在汇总里明确写出，人类决策时可要求加预算重 spike 或直接否决该候选。
- Spike subagent 违反硬规则（改了禁止改的文件 / 改了其他分支）→ 丢弃该 spike 结果，写 NEEDS_REVIEW，停。

## 注意

- Spike 分支上的代码**默认全部丢**，只留 tag + RESULT.md。之后 dev 阶段从零在 `or/<desc>` 分支上重写；不得直接 merge spike 分支到 or 分支（spike 代码未经节点规范约束）。
- 不要用 spike 阶段探索 Type A 问题（那应该在 inquiry 就解决）。
- 多个 OR 之间可能相关：A OR 的结果影响 B OR 的可行性。此时在 PLAN 里显式标 dependency，第二批 spike 推迟到第一批决策后。
