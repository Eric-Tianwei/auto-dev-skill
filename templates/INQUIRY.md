# INQUIRY（模板 / 示例）

Inquiry 阶段的全部产出。`workflows/inquiry.md` 写入此文件。

---

## Collapsed OR Nodes

| OR 节点 | 问题 | 答案 | 决策 | 理由 |
|---------|------|------|------|------|
| auth strategy | 需要跨多个子域/服务共享登录吗？ | 是，3 个服务共享 | JWT | 跨服务共享 → 无状态必选，session 方案否决 |
| DB choice | 业务里有原子性要求的金融交易吗？ | 是 | Postgres | ACID 必要，NoSQL 候选否决 |

---

## Remaining OR Nodes (→ spike)

| OR 节点 | 为何不确定（Type B 理由） | Spike scope |
|---------|-------------------------|-------------|
| search backend | 数据规模下延迟未知，需实测 | 索引 10k 条样本，测 p99（预算：≤4 文件，≤20 分钟） |
| caching layer | 当前响应时间瓶颈是否在网络/CPU 未知 | profile 现有 API 的 p99 分解（预算：≤2 文件，≤15 分钟） |

---

## Updated DAG

- `auth strategy` OR 折叠 → `or/session-auth` 标 `decided:rejected`，`or/jwt-auth` 继续。
- `DB choice` OR 折叠 → `or/nosql` 标 `decided:rejected`，`or/postgres` 继续。
- 其余 DAG 不变，见 `PLAN.md`。

---

## 提问记录（按顺序，方便回看）

1. Q（impact=2）："需要跨多个子域/服务共享登录吗？" → A: 是，3 个服务
2. Q（impact=1）："业务里有原子性要求的金融交易吗？" → A: 是
3. Q（impact=0）：已 3 题无新折叠，停止提问，剩余进 spike

---

## Spike Summary（spike 阶段完成后追加）

| OR 节点 | 候选 | 结论 | Spike tag |
|---------|------|------|-----------|
| search backend | pg-fts | p99=230ms，达标 | `spike/result-search-pg-fts` |
| search backend | meilisearch | p99=45ms，达标；多一个服务依赖 | `spike/result-search-meilisearch` |
| caching layer | redis-cache | profile 显示瓶颈在 DB 查询，cache 命中可降 80% | `spike/result-caching-redis` |
| caching layer | no-cache | DB query optimization 可降 60%，成本更低 | `spike/result-caching-none` |

→ 触发 review-gate: `or-decision-needed`，写 NEEDS_REVIEW 等人类决策。
