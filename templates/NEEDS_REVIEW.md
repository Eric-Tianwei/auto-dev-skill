# NEEDS_REVIEW（模板 / 示例）

主循环触发停止条件时追加。每段对应一次停下，用户处理后可自行清理。

格式：时间 + 任务 id + 停止原因分类 + 现象 + 已尝试 + 建议。

---

## 2026-04-15 15:42 · FEAT-002 · scope-overflow
- 现象: 实现 `cli schema` 需要反射配置类型，但类型定义分散在 `src/config/*.ts` 三个文件且风格不一
- 已尝试: 手写 schema（放弃，维护负担大）；用 `ts-json-schema-generator`（放弃，配置类型有循环引用）
- 建议: 先新建一条任务"统一 config 类型定义到单一模块"，再回头做 FEAT-002
- 状态: backlog FEAT-002 标记为 blocked

## 2026-04-15 16:05 · BUG-012 · cannot-reproduce
- 现象: 报告中的崩溃栈在本机 20 次运行中 0 次复现
- 已尝试: 按 repro 步骤原样跑；放大并发；切换 Node 版本至报告中的 20.11
- 建议: 需要用户补充：操作系统版本、是否开启了某个实验性 flag、崩溃时的完整环境变量
- 状态: backlog BUG-012 标记为 blocked
```
## 停止原因分类（便于用户扫视）

- `safety-boundary` — 触到黑名单操作
- `repeated-failure` — 同任务连续 2 次失败
- `test-baseline-regression` — 主分支原本通过的测试现在失败
- `cannot-reproduce` — bug 无法复现
- `scope-overflow` — 任务实际范围远超描述
- `missing-info` — 任务描述不足以动工
- `missing-credential` — 需要的外部凭证/服务不可用
- `main-modified` — main 分支被意外修改
