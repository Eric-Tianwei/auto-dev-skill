# PLAN（模板 / 示例）

DAG 本体 + 节点规范。是 skill 的计划入口，取代扁平 BACKLOG。

---

## DAG

```mermaid
flowchart TD
  LOGIN[node/login-endpoint-stub]:::done --> MW[node/middleware-validation]:::done
  MW --> OR{{OR: auth strategy}}
  OR --> OJ[or/jwt-auth · or-jwt-signing]:::dev
  OR --> OS[or/session-auth · or-session-store]:::pending

  OJ --> AJB[and/jwt-blacklist]:::pending
  OJ --> AJR[and/jwt-rotation]:::pending

  classDef done fill:#9f9
  classDef dev fill:#ff9
  classDef pending fill:#eee
```

> common successor（LOGIN, MW）落在 main。OR 从 MW 的 tag 分出，OR 之间不会合并——由人类决策后只有一条 merge 回 main。

---

## 节点表

| id | 类型 | 边关系 | 分支 | 状态 | 完成 tag |
|----|------|--------|------|------|----------|
| login-endpoint-stub | COMMON | → middleware-validation | main | done | `node/login-endpoint-stub` |
| middleware-validation | COMMON | login-endpoint-stub → | main | done | `node/middleware-validation` |
| or-jwt-signing | OR/首 | MW → | or/jwt-auth | dev | — |
| or-jwt-refresh | SEQ | or-jwt-signing → | or/jwt-auth | pending | — |
| and-jwt-blacklist | AND | or-jwt-signing → (回合) | and/jwt-auth-blacklist | pending | — |
| and-jwt-rotation  | AND | or-jwt-signing → (回合) | and/jwt-auth-rotation | pending | — |
| or-session-store | OR/首 | MW → | or/session-auth | pending | — |
| or-session-refresh | SEQ | or-session-store → | or/session-auth | pending | — |

**状态取值**：`pending` / `dev` / `done` / `blocked` / `pending-review` / `abandoned` / `decided`

---

## 节点规范

每个节点按 `templates/NODE.md` 填一段，下方紧跟节点表。示例：

### Node: or-jwt-signing

**Entry assumptions**
- [x] `node/middleware-validation` 已存在
- [x] 接口契约：MW 提供 `req.auth: { token?: string }`

**Completion condition**
- [ ] 单元测试 `tests/jwt/sign.test.ts` 全绿
- [ ] 接口：`signToken(payload, ttl) → string` + `verifyToken(string) → payload | null`

**Scope limit**
- Max files changed: 4
- Max new dependencies: 1（jose）
- Estimated commits: 2–3

**Retry limit (L0 → L1 升级)**
- Escalate after **3** failed attempts

**Failure escalation rules**
- L1 trigger: MW 接口不够（比如缺 token 提取位置）
- L2 trigger: 测试表明 JWT 无法满足需求（比如需要即时吊销但约束里排除了黑名单）

---

## OR 候选对照

| OR 节点 | 候选 | 状态 | 决策 tag |
|---------|------|------|----------|
| auth strategy | or/jwt-auth | dev | — |
| auth strategy | or/session-auth | pending | — |

用户在此处或 `INQUIRY.md` 填入选择后，主循环将打 `decision/selected-*` / `decision/rejected-*` tag。
