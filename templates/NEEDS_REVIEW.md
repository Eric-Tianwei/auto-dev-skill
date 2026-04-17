# NEEDS_REVIEW（模板）

触发停止条件时追加。每段对应一次停下，用户处理完可清理。

格式：时间 + 节点 id 或 tag + 停止原因 tag + 现象 + 已尝试 + 建议 + 状态。

---

## 2026-04-15 14:35 · auth-strategy · or-decision-needed
- 现象: 两条 OR 候选 spike 全部回来，结论见 JOURNAL 最新段
- 已尝试: 两个 worktree spike 并行完成，数据齐
- 建议: 选 or-jwt-signing（p99=45ms，跨服务共享登录需求明确）；人类跑 `auto-dev or decide auth-strategy or-jwt-signing`
- 状态: or 组 `decided` 待人类填

## 2026-04-15 16:20 · or-jwt-refresh · node-stuck
- 现象: 重试 3 次均失败，失败信号都指向 middleware 未暴露 refresh 钩子
- 已尝试: 节点内换了 3 种 refresh 实现
- 建议: 跑 `auto-dev node add mw-refresh-hook --deps mw-validation` 再 `auto-dev edge add mw-refresh-hook or-jwt-refresh`；或改 `.auto-dev/nodes/or-jwt-refresh.md` 的 Completion 放宽对 refresh 的要求
- 状态: 该节点 `status="blocked"`

---

## 停止原因

- `dag-schema-invalid` — `auto-dev validate` 非零
- `design-blocked` — plan 阶段无法建出一致 DAG（写不出 completion / 估不出 scope / 需求矛盾）
- `node-stuck` — 节点重试达 limit，需要人类从节点 md 的 Escalation 菜单里选一条改
- `entry-missing` — 节点前置 tag 不存在
- `scope-overflow` — 实际改动超节点 Scope
- `or-decision-needed` — spike 全部完成，等人类跑 `auto-dev or decide <g> <winner>`
- `or-branch-review` — OR 分支端到端完成，等人类 review + PR
- `safety-boundary` — 命中 safety.md 黑名单
- `test-baseline-regression` — 原本通过的测试现在失败
- `protected-push-attempted` — 对 upstream/受保护分支的任何写操作
- `upstream-sync-conflict` — upstream → base 同步有冲突
- `missing-credential` — 外部凭证/服务不可用
