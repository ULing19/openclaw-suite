# OpenClaw Integration Notes

[中文说明](#中文) | [English](#english)

---

## 中文

这份说明聚焦于如何把本仓库里的脚本接入一个已有的 OpenClaw 环境。

### 1. 典型接入方式

- `multimodal-agent.py`
  给技能、消息处理或外部脚本调用，负责理解图片、转写语音、提取文件内容。
- `image_sender.py`
  给图片生成后的“交付步骤”调用，按渠道发送媒体。
- `mail-agent.py`
  作为独立定时任务运行，轮询邮箱并生成自动回复，同时可选地通过 OpenClaw 渠道通知。

### 2. 推荐目录

如果你想按这个仓库的结构部署，可以放到：

```text
/opt/openclaw-multimodal-toolkit
```

然后把 `.env`、systemd 文件和脚本放在同一个目录体系下。

### 3. OpenClaw 侧依赖

至少需要：

- `openclaw` CLI 可执行
- 本机可访问 `~/.openclaw/`
- 已配置的消息渠道，例如 Telegram / Feishu / QQ / WeChat
- 可运行 `uvx minimax-coding-plan-mcp`

### 4. 通知目标建议

不要把个人账号或群组目标硬编码进脚本。

推荐通过环境变量设置：

```json
[
  {"channel":"telegram","target":"telegram:<user_id>"},
  {"channel":"qqbot","target":"qqbot:c2c:<user_id>"}
]
```

### 5. OneBot 相关

如果你的 OpenClaw 同时接了 QQ OneBot 通道，可以配合 `skills/openclaw-onebot/SKILL.md` 一起使用。

适合场景：

- QQ 私聊或群聊做 AI 助手
- QQ 里接收图片/文件/语音，再交给多模态脚本处理
- block streaming 分块回复

---

## English

These notes focus on wiring this repository into an existing OpenClaw environment.

### 1. Typical integration pattern

- `multimodal-agent.py`
  Called by skills, message handlers, or wrapper scripts for image, voice, and file understanding.
- `image_sender.py`
  Used as the delivery step after image generation.
- `mail-agent.py`
  Runs as a scheduled job for mailbox polling, AI reply generation, and optional OpenClaw channel notifications.

### 2. Suggested deployment path

A practical layout is:

```text
/opt/openclaw-multimodal-toolkit
```

### 3. OpenClaw-side prerequisites

- `openclaw` CLI in `PATH`
- local access to `~/.openclaw/`
- configured channels such as Telegram, Feishu, QQ, or WeChat
- `uvx minimax-coding-plan-mcp` available

### 4. Notification target guidance

Do not hardcode personal IDs into scripts.

Prefer environment-driven JSON configuration:

```json
[
  {"channel":"telegram","target":"telegram:<user_id>"},
  {"channel":"qqbot","target":"qqbot:c2c:<user_id>"}
]
```

### 5. OneBot pairing

If your OpenClaw instance also runs a QQ OneBot channel, this repository pairs naturally with `skills/openclaw-onebot/SKILL.md`.
