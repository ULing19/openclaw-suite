# OpenClaw Multimodal Toolkit

[English](README.md)

这是一个面向 OpenClaw 生态的多模态工具仓库，整理了实际工作区中已经跑通的一部分脚本、技能说明和部署示例，并在公开前移除了私人记忆、日志、状态文件和真实账号标识。

## 仓库能做什么

- 处理图片、语音、PDF、Office、文本文件等多模态输入
- 轮询 IMAP 邮箱并生成 AI 自动回复
- 把生成图片发送到 Telegram、飞书、QQ、微信等渠道
- 给 OpenClaw 技能和通道集成提供现成参考
- 提供 OneBot / systemd / 环境变量示例

## 主要内容

- `multimodal-agent.py`
  多模态统一入口，覆盖图片理解、语音转写、PDF/OCR、Office 文档和文本文件处理。
- `mail-agent.py`
  邮件轮询、AI 回复、OpenClaw 渠道通知。
- `image_sender.py`
  多渠道图片发送助手。
- `skills/`
  `multimodal-messaging`、`image-gen-deliver`、`openclaw-onebot` 等技能文档。
- `deploy/`
  部署时可直接参考的 `.env` 和 `systemd` 示例。
- `docs/`
  OpenClaw 集成说明和配置建议。

## 目录结构

```text
.
├── image_sender.py
├── mail-agent.py
├── multimodal-agent.py
├── requirements.txt
├── .env.example
├── docs/
├── deploy/
└── skills/
```

## 依赖要求

- Python 3.10+
- 已安装并可执行的 OpenClaw CLI
- `uvx minimax-coding-plan-mcp`
- Tesseract OCR
- Poppler（给 `pdf2image` 用）
- 可选：本地 `faster-whisper` 模型缓存

## 安装方式

安装 Python 依赖：

```bash
pip install -r requirements.txt
```

复制环境变量模板：

```bash
cp .env.example .env
```

然后把实际配置填进去。

## 关键环境变量

- `MINIMAX_API_KEY`
- `MINIMAX_API_HOST`
- `MINIMAX_URL`
- `MINIMAX_MODEL`
- `MAIL_AGENT_EMAIL_ACCOUNT`
- `MAIL_AGENT_EMAIL_PASSWORD`
- `MAIL_AGENT_TOKEN`
- `BRAVE_API_KEY`
- `MAIL_AGENT_NOTIFY_TARGETS`

`MAIL_AGENT_NOTIFY_TARGETS` 采用 JSON 数组，例如：

```json
[
  {"channel":"telegram","target":"telegram:<user_id>"},
  {"channel":"feishu","target":"<open_id>"}
]
```

## 快速示例

语音转写：

```bash
python3 multimodal-agent.py voice /path/to/audio.mp3
```

处理文件：

```bash
python3 multimodal-agent.py file /path/to/file.pdf
```

自然语言修改文件：

```bash
python3 multimodal-agent.py modify /path/to/file.txt "把标题改成季度总结"
```

发送图片：

```bash
python3 image_sender.py /path/to/image.jpg telegram <telegram_user_id> "说明文字"
```

## OpenClaw 绑定点

这个仓库不是完全通用的 Python 库，它默认依赖一些 OpenClaw 约定：

- 本地配置路径在 `~/.openclaw/`
- 通过 `openclaw message send` 发消息
- 通过 `uvx minimax-coding-plan-mcp` 调 MiniMax MCP
- 渠道格式和插件行为遵循 OpenClaw 生态

如果你要拿去做非 OpenClaw 项目，通常需要改：

- 配置读取逻辑
- 消息发送适配层
- 路径和部署方式

## 额外文档

- [OpenClaw 集成说明](docs/OPENCLAW_INTEGRATION.md)
- [systemd / env 部署示例](deploy/)

## 许可证

[MIT](LICENSE)
