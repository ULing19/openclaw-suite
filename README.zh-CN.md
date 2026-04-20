# OpenClaw Multimodal Toolkit

[English](README.md)

![cover](assets/cover.svg)

![Python](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-0f766e)
![OpenClaw](https://img.shields.io/badge/OpenClaw-integrated-c0841a)
![Status](https://img.shields.io/badge/status-practical%20toolkit-334155)

这是一个面向 OpenClaw 生态的多模态工具仓库，整理了实际工作区中已经跑通的一部分脚本、技能说明和部署示例，并在公开前移除了私人记忆、日志、状态文件和真实账号标识。

## 仓库能做什么

- 处理图片、语音、PDF、Office、文本文件等多模态输入
- 轮询 IMAP 邮箱并生成 AI 自动回复
- 把生成图片发送到 Telegram、飞书、QQ、微信等渠道
- 合并一个清洗后的 OpenClaw Web 参考应用
- 给 OpenClaw 技能和通道集成提供现成参考
- 提供 OneBot / systemd / 环境变量示例

## 主要内容

- `multimodal-agent.py`
  兼容入口，实际逻辑在 `scripts/` 中。
- `mail-agent.py`
  兼容入口，实际逻辑在 `scripts/` 中。
- `image_sender.py`
  兼容入口，实际逻辑在 `scripts/` 中。
- `scripts/`
  存放真实可执行脚本实现。
- `src/openclaw_multimodal_toolkit/`
  提供基础包结构和模块化 CLI 入口。
- `skills/`
  `multimodal-messaging`、`image-gen-deliver`、`openclaw-onebot` 等技能文档。
- `apps/openclaw-web/`
  从独立仓库清洗并合并进来的 Web 参考应用。
- `deploy/`
  部署时可直接参考的 `.env` 和 `systemd` 示例。
- `docs/`
  OpenClaw 集成说明和配置建议。

## 目录结构

```text
.
├── assets/
├── apps/
├── deploy/
├── docs/
├── image_sender.py
├── mail-agent.py
├── multimodal-agent.py
├── pyproject.toml
├── requirements.txt
├── scripts/
├── src/
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

如果你希望按包方式使用，也可以：

```bash
pip install -e .
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

模块化 CLI 方式：

```bash
python -m openclaw_multimodal_toolkit.cli multimodal voice /path/to/audio.mp3
python -m openclaw_multimodal_toolkit.cli image-sender /path/to/image.jpg telegram <telegram_user_id>
```

## 仓库定位

这个仓库更像“实战型工具包”，不是通用 SDK，也不是已经完全产品化的框架。

它最适合：

- 想快速复用 OpenClaw 多模态处理思路的人
- 想直接改现成脚本和部署示例的人
- 想参考技能文档和通道整合方式的人

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
- [OpenClaw Web 参考应用](apps/openclaw-web/README.md)
- [OneBot 技能文档](skills/openclaw-onebot/SKILL.md)
- [systemd / env 部署示例](deploy/)

## 许可证

[MIT](LICENSE)
