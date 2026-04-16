# 安全边界（待用户敲定）

本文档是占位。用户会在后续对话里细化清单，届时主循环在执行任何破坏性操作前都要对照这份清单。

## 初稿：默认允许（白名单）

- 本地 commit（在非 main 分支）
- 建分支、切分支、建 worktree
- 安装项目依赖（`npm i` / `bun add` / `pip install -r`）到项目本地
- 跑项目脚本：测试、类型检查、lint、build、dev server
- 读写项目工作目录下的文件
- 调用 subagent

## 初稿：默认禁止（黑名单，命中即停下写 NEEDS_REVIEW）

- `git push`（任何形式）
- `git push --force` / `--force-with-lease`
- 删除分支（`git branch -D`、`git push --delete`）
- 向远端 push `main` / `master` / 受保护分支（任何形式，含 `--force*`）。注意：**本地** `main` commit 合法——common successor 节点按设计就落在本地 main。
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
