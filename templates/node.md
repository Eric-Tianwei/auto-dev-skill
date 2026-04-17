---
name: <node-id>
description: <one-line purpose>
deps: []
branch: ai-main
# or_candidate_of: <or-group-id>   # 仅当此节点是某 OR 组的竞争候选时填
---

## Entry

开工前必须已真/已建的前提（父节点 tag、接口契约、环境等）。

- `<parent>` tag 存在
- 接口契约：父节点输出什么

## Completion

可验证的 completion 条件。"实现了 X" 不算——必须是可跑或可看：

- [ ] 测试命令或脚本（例如 `bun test tests/foo.test.ts`）
- [ ] 可观察的外部行为

## Scope

- max_files: <N>
- max_new_deps: <N>
- estimated_commits: <N>

## Retry

- limit: <N>（简单 2 / 一般 3 / 不确定 5；不要无限重试）

## Escalation

重试耗尽时停下写 NEEDS_REVIEW，给人类一个动作菜单，并建议你倾向哪条：

- 改本节点 md（放宽 completion / 缩 scope / 拆成两节点）
- 改 dag.json（加新节点 / 删节点 / 改 deps / 换 branch）
- 弃 OR 分支（若此节点在 or_groups 中）
