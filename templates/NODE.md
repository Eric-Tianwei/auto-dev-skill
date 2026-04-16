# NODE（模板）

> **字段到视图的对照**。节点规范的 source of truth 是 `.auto-dev/dag.json` 里 `nodes[]` 数组的对象；本模板展示如何把该对象**渲染**到 `PLAN.md`。修改先改 dag.json 跑 schema，再同步本视图。

---

## dag.json 字段（权威）

```json
{
  "id": "or-jwt-signing",
  "kind": "OR_HEAD",
  "branch": "or/jwt-auth",
  "entry": ["node/middleware-validation exists", "MW provides req.auth: { token?: string }"],
  "completion": [
    "signToken(payload, ttl) -> string and verifyToken(s) -> payload|null exposed",
    "tests/jwt/sign.test.ts passes"
  ],
  "scope": { "max_files_changed": 4, "max_new_dependencies": 1, "estimated_commits": "2-3" },
  "retry_limit": 3,
  "escalation": {
    "l1_trigger": "Failure indicates MW does not surface token payload at expected call site",
    "l2_trigger": "Tests show JWT cannot meet requirement (e.g. instant revocation)"
  },
  "or_type": "A",
  "status": "pending",
  "completion_tag": null
}
```

## PLAN.md 视图（人类视图，由字段渲染）

### Node: or-jwt-signing

**Entry assumptions** ← `nodes[].entry`
- [ ] `node/middleware-validation` 已存在
- [ ] MW 提供 `req.auth: { token?: string }`

**Completion condition** ← `nodes[].completion`
- [ ] `signToken(payload, ttl) → string` + `verifyToken(string) → payload | null` 对外暴露
- [ ] `tests/jwt/sign.test.ts` 全绿

（"实现了 X" 不算 completion condition；必须是可跑、可看的。）

**Scope limit** ← `nodes[].scope`
- Max files changed: 4
- Max new dependencies: 1
- Estimated commits: 2–3

**Retry limit** ← `nodes[].retry_limit` — 3

**Failure escalation** ← `nodes[].escalation`
- L1 trigger: MW 接口不够（例如缺 token 提取位置）
- L2 trigger: 测试表明 JWT 无法满足需求（例如需要即时吊销但黑名单被排除）

**Git 操作** ← `nodes[].branch` + `nodes[].kind`
- 分支：`or/jwt-auth`（kind=OR_HEAD；common successor 落在 base_branch，默认 `ai-main`；不是 `main`）
- 完成 tag：`node/or-jwt-signing`（写入 `nodes[].completion_tag`）

---

## 填写要点（写 dag.json 时记牢）

- **`entry`** 数组每项一行；本节点开工前对应 tag 必须存在，否则 dag_cursor 跳过。
- **`completion`** 至少 1 项，每项必须可跑或可观察。写不出来 → design 失败（`design-blocked` / `dag-schema-invalid`），不要带含糊进 dev。
- **`scope.max_files_changed`** 故意写紧。超了宁可拆节点。
- **`retry_limit`** 惯例：简单节点 2，一般节点 3，很不确定的 5。schema 上限 5——更不确定应改 completion 或拆节点，不是无限重试。
- **`escalation.l1_trigger` / `l2_trigger`** 必须具体到"读到什么信号才升级"。留空等于没有，升级判定会失准。
- **`kind == "OR_HEAD"`** 必须同时设 `or_type`（`"A"` 或 `"B"`），并且该节点 id 出现在某个 `or_groups[].candidates`。
