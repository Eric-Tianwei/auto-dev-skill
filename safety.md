# 安全边界（待用户敲定）

本文档是占位。用户会在后续对话里细化清单，届时主循环在执行任何破坏性操作前都要对照这份清单。

## 初稿：默认允许（白名单）

- 本地 commit（在 `base_branch` 即默认 `ai-main`，以及 `or/*` `and/*` `spike/*` 派生分支上）
- 建分支、切分支、建 worktree（分支名必须属于 `ai-main` / `or/*` / `and/*` / `spike/*` / `failed/*` 命名空间）
- 从 `upstream_branch`（默认 `main`）往 `base_branch` 做**快进或无冲突 merge**（单向 pull）
- 安装项目依赖（`npm i` / `bun add` / `pip install -r`）到项目本地
- 跑项目脚本：测试、类型检查、lint、build、dev server
- 读写项目工作目录下的文件
- 调用 subagent

## 初稿：默认禁止（黑名单，命中即停下写 NEEDS_REVIEW）

- `git push`（任何形式）
- `git push --force` / `--force-with-lease`
- 删除分支（`git branch -D`、`git push --delete`）
- **对 `upstream_branch`（默认 `main`） / `master` 的任何写操作**：`git checkout main && commit` / `git merge ... main`（把别的往 main 合）/ `git rebase` 改写 main 历史 / push 到 main。本地也禁止。AI 的落点只有 `base_branch`。
- `base_branch` → `upstream_branch` 的合并 / PR（无论本地 `git merge` 还是远端 PR 发起）——这是人类专有的 promotion 动作。
- `upstream_branch` → `base_branch` 同步出现冲突时自行解决（必须停下让人处理）。
- `git reset --hard` 到丢弃工作中的 commit
- `git commit --no-verify` 跳过 hook
- 改 `git config`
- 改 `.github/workflows/**` 或其他 CI 配置
- 改 `.env*`、密钥、凭证文件
- 全局安装软件、改系统配置、sudo
- 调用需要付费/外部副作用的 API（发邮件、发消息、发布包、部署）
- 跨仓库操作（操作父目录或其他 repo）
- `rm -rf` 超出单文件范围

## 灰色地带（需要任务条目显式授权才能做）

- 升级主要依赖大版本
- 改数据库 migration
- 改项目根 `package.json` 的 scripts 字段
- 改 `tsconfig.json` / `pyproject.toml` 等构建配置的根级选项
- 生成超过 500 行的新文件

用户后续补充的规则直接追加到对应小节即可。
