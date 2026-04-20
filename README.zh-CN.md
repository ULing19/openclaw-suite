# OpenClaw Suite

[English](README.md)

![cover](assets/cover.svg)

![Python](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-0f766e)
![Monorepo](https://img.shields.io/badge/repo-monorepo-334155)
![OpenClaw](https://img.shields.io/badge/OpenClaw-integrated-c0841a)

这是一个围绕 OpenClaw 生态整理出来的实战型 monorepo，里面同时放了多模态脚本、邮件自动化、渠道发送工具、技能文档、部署示例，以及一个清洗后的 Web 参考应用。

这个仓库最初来自真实工作区的公开化子集，发布前已经移除了私人记忆、日志、真实账号标识和本地状态文件，之后又进一步整理成总仓结构。

## 仓库里有什么

- 多模态消息处理脚本
- AI 邮件自动回复工具
- Telegram / 飞书 / QQ / 微信等渠道的媒体发送辅助
- OpenClaw 相关 skills 和集成说明
- `openclaw-web` 的清洗版参考应用
- `systemd` / `.env` / 部署示例

## Monorepo 结构

```text
.
├── apps/
│   └── openclaw-web/          # 清洗后的 Web 参考应用
├── assets/                    # 仓库级视觉资源
├── deploy/                    # env / systemd 示例
├── docs/                      # 集成说明
├── scripts/                   # 真实脚本实现
├── skills/                    # OpenClaw 技能文档
├── src/                       # 轻量包结构和 CLI
├── image_sender.py            # 兼容入口
├── mail-agent.py              # 兼容入口
├── multimodal-agent.py        # 兼容入口
├── pyproject.toml
└── requirements.txt
```

## 主要模块

| 模块 | 作用 |
|------|------|
| `scripts/` | 多模态处理、邮件自动化、图片发送等脚本 |
| `src/openclaw_multimodal_toolkit/` | 轻量 Python 包和模块化 CLI |
| `skills/` | `multimodal-messaging`、`image-gen-deliver`、`openclaw-onebot` 等技能文档 |
| `apps/openclaw-web/` | FastAPI Web 参考应用，包含任务模式和多模态处理 |
| `deploy/` | 环境变量和 `systemd` 示例 |
| `docs/` | Monorepo 级别的集成说明 |

## 快速开始

安装依赖：

```bash
pip install -r requirements.txt
pip install -e .
```

如果你要用根目录下这些工具脚本：

```bash
cp .env.example .env
```

如果你要跑 Web 应用：

```bash
cp apps/openclaw-web/config_example.env apps/openclaw-web/.env
```

## 常见用法

语音转写：

```bash
python3 multimodal-agent.py voice /path/to/audio.mp3
```

处理文件：

```bash
python3 multimodal-agent.py file /path/to/file.pdf
```

发送图片：

```bash
python3 image_sender.py /path/to/image.jpg telegram <telegram_user_id> "说明文字"
```

模块化 CLI：

```bash
python -m openclaw_multimodal_toolkit.cli multimodal voice /path/to/audio.mp3
python -m openclaw_multimodal_toolkit.cli image-sender /path/to/image.jpg telegram <telegram_user_id>
```

运行 Web 应用：

```bash
cd apps/openclaw-web
python app.py
```

## 仓库定位

这个仓库不是追求高度抽象的框架，而是偏“能直接拿来改”的实战型总仓。

它更适合：

- 希望直接复用 OpenClaw 工作流的人
- 需要多渠道、多模态自动化的人
- 想同时保留脚本、Web 参考应用、部署文档和技能说明的人

## 重点入口

- [OpenClaw 集成说明](docs/OPENCLAW_INTEGRATION.md)
- [OpenClaw Web 参考应用](apps/openclaw-web/README.md)
- [OpenClaw Web 部署文档](apps/openclaw-web/DEPLOYMENT.md)
- [OneBot 技能文档](skills/openclaw-onebot/SKILL.md)

## 安全说明

- 公开版不包含 secrets、记忆快照、日志和运行时数据库。
- 通知目标改成环境变量，不再硬编码个人账号。
- 合并进来的 Web app 已经做过清洗：硬编码 key、个人品牌、绝对生产路径和运行时垃圾都已去除。

## 许可证

[MIT](LICENSE)
