# NODE（模板）

每个 DAG 节点在 `PLAN.md` 里都要有一段按此格式的规范。没有它不进 dev。

---

## Node: <node-id>

**Entry assumptions**
- [ ] <父节点 tag 必须存在，例如 `node/middleware-validation`>
- [ ] <接口契约描述：父节点输出什么给本节点消费>
- [ ] <其他环境/数据前提>

**Completion condition**
- [ ] <可验证的测试路径或脚本命令，例如 `bun test tests/auth/jwt.test.ts`>
- [ ] <可观察的外部行为，例如 `POST /login 返回合法 JWT 且能被下个节点的 verify 通过`>

（注意："实现了 X" 不算 completion condition；必须是可跑、可看的。）

**Scope limit**
- Max files changed: <N>
- Max new dependencies: <N>（0 除非有理由）
- Estimated commits: <N>

**Retry limit (L0 → L1 升级)**
- Escalate after **<N>** failed attempts

**Failure escalation rules**
- L1 trigger: <具体条件，例如"失败信息指向父节点接口而非实现细节"或"重试 N 次后 completion condition 仍不可达"。>
- L2 trigger: <具体条件，例如"父节点改动后失败模式不变"或"本 OR 分支核心假设与需求矛盾"。>

**Git 操作**
- 分支：`<or/jwt-auth | and/jwt-blacklist | ai-main>`（common successor 落在 `base_branch`，默认 `ai-main`；不是 `main`）
- SEQ / AND / common successor：<本节点类型>
- 完成 tag：`node/<path>`

---

## 填写要点

- **entry** 能勾选的都勾上；不能勾的 → 本节点暂不能开工，dag_cursor 跳过。
- **completion** 如果写不出可验证条件 → design 失败，写 NEEDS_REVIEW，不要带着含糊 completion 进 dev。
- **scope** 故意写紧。超了宁可拆节点。
- **retry N** 惯例：简单节点 2，一般节点 3，很不确定的 5。不要 >5——不确定应改进 completion 或拆节点，不是无限重试。
- **L1/L2 trigger** 必须具体到"读到什么信号才升级"。留空等于没有，升级判定会失准。
