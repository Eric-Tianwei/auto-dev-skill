# JOURNAL（模板 / 示例）

主循环在每次节点完成、升级、决策时追加一段。用户扫这份文件就能了解几小时内 DAG 推进到哪了。

格式：时间 + `node/` 或 `decision/` tag + 分支 + 一句话结论 + 下一步/备注。≤ 6 行。

---

## 2026-04-15 14:05 · node/login-endpoint-stub · main
- 结论: common successor 完成，stub 返回 501 + 记录 req.auth 位
- 下一: main 上做 middleware-validation

## 2026-04-15 14:20 · node/middleware-validation · main
- 结论: 中间件提取 token 并挂到 req.auth；覆盖 5 个用例；全量测试无回退
- 下一: 从此 tag 开出 or/jwt-auth 和 or/session-auth

## 2026-04-15 14:35 · spike 全部完成 · or-decision-needed
- Spike: `spike/result-search-pg-fts`、`spike/result-search-meilisearch`、`spike/result-caching-redis`、`spike/result-caching-none`
- 停止原因: OR 决策待人类，详见 NEEDS_REVIEW.md
- 状态: PLAN 中两个 OR 保持 open

## 2026-04-15 15:10 · decision/selected-jwt-auth · main
- 结论: 用户确认选 jwt；session 候选打 decision/rejected-session-auth-stateless-requirement
- 下一: 在 or/jwt-auth 开始做 or-jwt-signing

## 2026-04-15 15:42 · node/or-jwt-signing · or/jwt-auth
- 结论: jose 库签/验通过；独立 review 无实质问题
- 下一: AND 并行做 and/jwt-blacklist 和 and/jwt-rotation

## 2026-04-15 16:20 · level-1-escalation · or-jwt-refresh
- 失败 tag: failed/or-jwt-refresh-mw-missing-refresh-hook
- 停止原因: L1 升级——middleware-validation 没暴露 refresh 钩子，需改父
- 下一: 等人类批准父节点修改方向，详见 NEEDS_REVIEW.md

---

## 条目写作规则

- 一个事件一段。不要合并多个事件。
- 失败重试（L0）**不写 JOURNAL**，只更新 state.json 的 retry_count。L1/L2 升级才写。
- AND 分支完成 merge 回父时写一段（便于追溯）。
- 决策（OR 选择、父修改批准）写一段，引用 tag。
- 不写冗长根因分析——根因放进 commit message，JOURNAL 只保留索引。
