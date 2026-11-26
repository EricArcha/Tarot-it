# 安装与牌图交付

首次使用时，先确认当前宿主具备读 Skill、执行 Python、写入状态目录和把图交到当前聊天的能力。任何输出路径均来自运行器的 `show`。跨机器时使用宿主托管的附件或下载途径。同机 HTML 可以用系统浏览器打开，并在断网后复查。

| 宿主 | 安装完整 `tarot-it` 目录 | 回复当前对话 |
| --- | --- | --- |
| Codex | 项目 `.agents/skills/tarot-it/`，或用户 `~/.agents/skills/tarot-it/`。显式入口 `$tarot-it`。 | Desktop 对可读本地图片使用 `![牌面](/absolute/path.jpg)`，同时提供牌桌文件链接。侧栏可打开 PNG/JPG。纯 CLI 提供绝对路径，支持图像的 TUI 可同时试图片预览。 [Skills](https://developers.openai.com/codex/skills) · [图像预览变更日志](https://learn.chatgpt.com/docs/changelog?type=chatgpt-desktop-app) |
| Claude Code | 项目 `.claude/skills/tarot-it/`，或用户 `~/.claude/skills/tarot-it/`。显式入口 `/tarot-it`。 | 在本地 CLI 回复可打开的 HTML 绝对路径和有引号的系统命令，例如 macOS 用 `open '/absolute path/spread.html'`，Linux 用 `xdg-open '/absolute path/spread.html'`。路径取自 `show`。 [Skills](https://code.claude.com/docs/en/skills) · [Bash 权限](https://code.claude.com/docs/en/permissions) |
| OpenClaw | 活动工作区 `skills/tarot-it/`。按该部署 Skills 列表确认加载。 | Control UI 的自动可见回复中，每个附件各写一条独立 `MEDIA:` 行，路径含空格时加双引号，例如 `MEDIA:"/my workspace/牌桌.jpg"`。交付离线牌桌时用 `show --zip-board` 返回的 `board_zip`，Control UI 已观察到裸 HTML 会被拒收。若宿主提供结构化回复，用 `mediaUrl` 或 `mediaUrls`。配置为 `message_tool_only` 时，官方接口是 `message(action=send)` 的 `media` 或 `attachments`，只发到当前已确认的对话。 [Skills](https://docs.openclaw.ai/tools/skills) · [富输出协议](https://docs.openclaw.ai/reference/rich-output-protocol) |
| Hermes Agent | 当前 profile 的 Skill 根目录。默认 `~/.hermes/skills/tarot-it/`。用 Skills 列表确认加载，调用 `skill_view` 时以实际安装路径为准。 | Gateway 用 Deliverable Mode。为 `--output-root` 选择可交付的目录，完整绝对路径每一段只用字母、数字、点、下划线和连字符，例如 `~/.hermes/cache/scratch/tarot-it` 展开后的路径。将文件绝对路径作为回复正文中的纯文本，避免反引号。Gateway 会在支持的渠道内嵌图片，HTML 可作为文件交付。纯 CLI 提供本机 HTML 绝对路径。 [Skills](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills) · [Deliverable Mode](https://hermes-agent.nousresearch.com/docs/user-guide/features/deliverable-mode) |

有 `overview` 时，可用一张全景加牌位文字展示 5–12 张牌，并提供 `board` 或 `board_zip`。其余时候用 `images` 顺序输出。ZIP 中只有自包含的 `spread.html`，带 900 像素长边牌图，解压后可离线打开。普通 `board` 保留高清原图。目标端附件限制较小时按顺序分组，或改发牌桌。遇到路径或权限错误先处理交付，再用同一 `run_id` 重跑 `show`。只有确认文件在当前用户可读取的位置后才把它作为交付结果。

Hermes Gateway 会按聊天历史去重正文中的相同路径。用户明确需要补传时，为 `check` 和 `show` 指定一个新的已获准 scratch 子目录，保持 `run_id` 不变，用新路径交付原结果。

`check --output-root <host-dir>` 验证生成文件的权限。它无法证明 Gateway 也能读取，需在客户端实测。对于按用户运行的单人宿主，可用工作区内 `.tarot-it` 私有目录作为状态根。共享部署应给每个聊天或已识别用户独立授权和状态空间。不要把数据库目录作为公开附件目录。共享隔离未验证时采用单人部署。
