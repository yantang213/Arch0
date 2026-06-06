---
name: arch0
description: "Arch0 项目记忆归档：当用户希望在 remote 主机、coding agent、Mac 本地 Arch Agent 之间沉淀项目级记忆、提交完成工作总结、保存 setup/incident/debug/operation notes、安装或修复 arch0 CLI、配置 remote client、检查 Arch0 server 连通性、或用 arch0 insert 发送 Markdown archive 时使用。本 skill 只指导 client 侧 agent 安装、配置和调用 Arch0 CLI；不要直接写 arch-vault，不要在 remote 侧决定项目路径，不要复制 Arch0 server 的 LLM routing/decision logic。"
metadata:
  requires:
    bins: ["arch0"]
  cliHelp: "arch0 --help; arch0 setup remote --help; arch0 insert --help; arch0 status --help; arch0 doctor --help; arch0 config --help"
---

# Arch0

Arch0 is a local-first project memory archive. A remote coding agent prepares useful Markdown context and calls the `arch0` CLI; the local Arch0 server on the user's Mac decides where the archive belongs and writes to `arch-vault`.

```bash
# 常用示例
arch0 setup remote
arch0 status
arch0 insert ./work-summary.md --title "Nginx HTTPS setup"
arch0 doctor
```

## 前置条件

执行任何归档操作前，先确认：

1. `arch0 --help` 可运行；不可运行时先按「安装或修复」处理
2. remote machine 已通过 `arch0 setup remote` 配置 `server_url`；API token 只有在 local Arch0 server 启用时才需要
3. `arch0 status` 连通性检查通过；失败时先跑 `arch0 doctor`
4. 待归档内容不包含 secrets、private keys、tokens、passwords、cookies 或 credential material

Arch0 的职责边界：

- Remote agent：整理信息、写 Markdown、调用 `arch0 insert`
- Arch0 CLI：读取 Markdown，构造 V0.1 insert payload，通过 HTTP 发给 server
- Local Arch0 server：安全扫描、LLM decision、选择 project、写 vault/index/audit

## 快速决策

- 用户说“把这次完成的工作沉淀/记忆/保存到 Arch0” → 写 Markdown 文件，然后 `arch0 insert <file>`
- 用户在 remote 主机第一次使用 Arch0 → 先 `arch0 --help`，失败则安装；之后 `arch0 setup remote` 和 `arch0 status`
- 用户说 Arch0 连不上、token 不对、server 无响应 → `arch0 doctor`
- 用户只想看当前配置 → `arch0 config show`
- 用户要求直接修改本地 vault、指定 project 文件路径、手写 index → 拒绝该做法，改用 `arch0 insert`
- 用户要求 recall/update/delete/search → 只有 CLI 明确支持时才执行；当前不要发明这些命令

## Commands

| Command | 用途 |
|---|---|
| `arch0 setup remote` | 在 remote machine 上配置 local Arch0 server URL、可选 API token、sender、default instruction |
| `arch0 status` | 快速检查 config 和 `/healthz` 连通性 |
| `arch0 doctor` | 诊断 config、HTTP、auth、Tailscale/网络问题 |
| `arch0 insert <markdown_file>` | 将 Markdown archive 提交给 local Arch0 server |
| `arch0 config show` | 显示 redacted config |
| `arch0 config set <key> <value>` | 更新单个配置项 |

## 安装或修复

如果 `arch0 --help` 已经可运行，不要重复安装。

如果 `arch0 --help` 失败，使用用户或项目文档提供的 official install URL。优先用可检查的安装方式：

```bash
curl -fsSLO https://raw.githubusercontent.com/yantang213/Arch0/main/scripts/install.sh
sh install.sh
```

用户明确要求一行安装时，才用：

```bash
curl -fsSL https://raw.githubusercontent.com/yantang213/Arch0/main/scripts/install.sh | sh
```

安装后验证：

```bash
arch0 --help
```

如果 installer 提示 `~/.local/bin` 不在 `PATH`，为当前 session 临时使用完整 shim 路径，或按用户确认更新 shell profile。不要静默改 shell profile。

## Setup Remote

在 remote machine 上运行：

```bash
arch0 setup remote
```

需要向用户或已有上下文确认：

- `server_url`：Mac 上 local Arch0 server 的 URL，通常是 Tailscale IP/MagicDNS + port
- `api_token`：如果 local Arch0 server 启用了 token
- `send_from_who`：能识别这台 remote 或 agent 的来源名
- `default_instruction`：默认归档指导，可留空或用项目约定

配置后必须验证：

```bash
arch0 status
```

如果失败：

```bash
arch0 doctor
```

根据输出修复 server URL、token、Tailscale、SSH tunnel 或网络问题。

## Insert Archive

当任务完成、用户要求沉淀经验，或当前工作产生了以后维护会用到的项目上下文时，创建一个临时 Markdown 文件并提交。

Markdown 内容建议包含：

- 背景和目标
- 关键决策
- 执行过的重要命令或配置
- 修改过的关键文件
- 验证结果
- 后续风险或 TODO

提交：

```bash
arch0 insert <markdown_file>
```

常用选项：

```bash
arch0 insert <markdown_file> --title "<title>"
arch0 insert <markdown_file> --instruction "<user guidance for storage/update>"
arch0 insert <markdown_file> --from "<sender identity>"
arch0 insert <markdown_file> --dry-run
```

结果处理：

- `accepted`：server 已归档到项目
- `needs_review`：server 已保存到 review 区，routing 不确定
- `rejected`：server 拒绝，通常是内容不合规或包含疑似敏感信息

## Troubleshooting

优先顺序：

```bash
arch0 status
arch0 doctor
arch0 config show
```

常见修复：

```bash
arch0 setup remote
arch0 config set server_url <url>
arch0 config set api_token <token>
arch0 config set send_from_who <sender>
arch0 config set default_instruction <instruction>
```

不要把 API token 原样打印给用户。除非用户明确要求且上下文安全，否则使用 redacted output。

## 禁区

- Do not write to `arch-vault/` directly.
- Do not create, rename, or choose project vault paths locally.
- Do not duplicate Arch0 server decision logic in the client.
- Do not include secrets in archive content.
- Do not bypass `arch0 insert` by crafting raw vault files.
- Do not expose the local Arch0 server to the public internet unless the user explicitly chooses that network design.
- Do not run destructive commands while repairing Arch0 setup unless the user explicitly asks for that operation.
