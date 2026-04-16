# NEEDS_REVIEW（模板 / 示例）

主循环触发停止条件时追加。每段对应一次停下，用户处理后可清理。

格式：时间 + 节点 id 或 tag + 停止原因 tag + 现象 + 已尝试 + 建议 + 状态。

---

## 2026-04-15 14:35 · all-spikes-complete · or-decision-needed
- 现象: 两个 OR 的 spike 全部回来，各自结论见 INQUIRY.md 的 Spike Summary
- 已尝试: 4 个 worktree spike 并行完成，数据齐
- 建议: search 选 meilisearch（p99=45ms，性能优先）；caching 选 no-cache（profile 显示 DB 优化更直接）
- 状态: PLAN 中 auth 已 decided，search / caching 两个 OR 待人类选择

## 2026-04-15 16:20 · or-jwt-refresh · level-1-escalation
- 现象: 重试 3 次均失败，失败信号统一指向 middleware 未暴露 refresh 钩子
- 已尝试: 节点内换 3 种 refresh 实现；每次都卡在"middleware 不认 refresh token 路径"
- 建议: 批准修改 `node/middleware-validation`，新增 refresh path 白名单；改后重跑 or-jwt-refresh
- 状态: or-jwt-refresh 标 blocked，`failed/or-jwt-refresh-mw-missing-refresh-hook` tag 已打

## 2026-04-15 17:05 · or/session-auth · level-2-escalation
- 现象: 第 2 个 session 节点失败；根因不是实现也不是父接口，而是需求要求"跨服务共享登录"，session 方案无法满足（inquiry 阶段实际上已折叠，但未清理）
- 已尝试: 尝试引入跨服务 session 存储——方案爆炸，估 scope >20 文件，远超节点 spec
- 建议: 整条 `or/session-auth` 弃；tag `decision/abandoned-or-session-auth-cross-service-requirement` 已打
- 状态: 不需要新 OR 候选（auth 的 or/jwt-auth 已选定），请人类确认弃分支正确

---

## 停止原因分类（便于用户扫视）

- `design-blocked` — 计划阶段无法建出一致 DAG
- `entry-missing` — 节点前置 tag 不存在
- `scope-overflow` — 实际改动超出节点 spec
- `level-1-escalation` — 节点 L0 重试达上限或父约束不可达
- `level-2-escalation` — OR 分支核心假设破产
- `or-decision-needed` — 所有 spike 完成，等人类选 OR
- `or-branch-review` — OR 分支全端完成，等 PR review
- `seq-checkpoint` — 连续 2–3 个 SEQ 节点完成，请方向 sanity check
- `safety-boundary` — 命中 safety.md 黑名单
- `test-baseline-regression` — 原本通过的测试现在失败
- `protected-push-attempted` — 尝试 push main / 受保护分支
- `missing-credential` — 外部凭证/服务不可用
- `cannot-reproduce` — （节点为 bug 型时）按 repro 无法复现
- `missing-info` — 节点描述不足以动工
