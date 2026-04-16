# BACKLOG（模板 / 示例）

每条任务一个二级标题，状态用 frontmatter-ish 的行首标记。AI 按从上到下顺序取 `status: todo` 的第一条。

---

## [FEAT-001] 给 CLI 加 --dry-run 参数
- status: todo
- type: feature
- priority: P1
- goal: 让用户在不实际写文件的情况下预览会发生什么
- acceptance:
  - 所有会写文件/发请求的命令都支持 `--dry-run`
  - dry-run 输出清晰列出"会做什么"
  - 现有测试不回退
- notes: 可以探索 2 个方案 —— 在 CLI 层拦截 vs 在执行器层拦截

## [BUG-007] 并发请求下计数器偶发少 1
- status: todo
- type: bug
- priority: P0
- symptom: 压测 100 并发时 counter 比预期少 1–3
- repro: `bun run bench:counter --concurrency 100`（本地可稳定复现约 30% 概率）
- notes: 上周重构过 counter 的 lock，怀疑相关

## [FEAT-002] 导出 JSON schema
- status: todo
- type: feature
- priority: P2
- goal: 用户能拿到配置文件的 schema 做 IDE 补全
- acceptance:
  - `cli schema` 输出合法 JSON Schema draft-07
  - README 有一段使用说明
```
## 状态取值

- `todo` — 待处理
- `in-progress` — AI 正在做（同一时刻至多一条）
- `done` — 完成并 commit
- `done-pending-review` — feature 多方案完成，等用户挑选
- `blocked` — 写到 NEEDS_REVIEW 等用户

## 字段约定

- `type`: `feature` | `bug`
- `priority`: `P0` | `P1` | `P2`
- feature 必须有 `goal` 和 `acceptance`
- bug 必须有 `symptom` 和 `repro`
- `notes` 可选，放背景/线索/约束
