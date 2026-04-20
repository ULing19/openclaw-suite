# openclaw-suite

> OpenClaw monorepo for multimodal tooling, web apps, skills, and deployment references

[![Open Source](https://img.shields.io/badge/Open%20Source-MIT-green?style=flat-square)](https://github.com/ULing19/openclaw-suite)
[![Stars](https://img.shields.io/github/stars/ULing19/openclaw-suite?style=flat-square)](https://github.com/ULing19/openclaw-suite/stargazers)
[![Language](https://img.shields.io/github/languages/top/ULing19/openclaw-suite?style=flat-square)](https://github.com/ULing19/openclaw-suite)
[![Last Commit](https://img.shields.io/github/last-commit/ULing19/openclaw-suite?style=flat-square)](https://github.com/ULing19/openclaw-suite/commits)

## 📖 About

Multimodal AI tooling monorepo built on **OpenClaw**, covering:

- 🤖 Agent skills & task automation (Python, Node.js)
- 💬 Multi-channel integrations (QQ, Telegram, Feishu, WeChat, Discord, Signal)
- 🖼️ Multimodal processing (image understanding, voice/STT, file parsing, OCR)
- 🌐 Web apps & deployment (FastAPI, Docker, Nginx, Linux server)
- 📊 Task queue & persistence (SQLite, scheduled & on-demand jobs)

## 🛠️ Tech Stack

| Category | Technologies |
|----------|-------------|
| **AI Framework** | OpenClaw, Hermes Bridge |
| **Voice/Image** | Whisper (STT), MiniMax VL/TTS, multimodal APIs |
| **Bot Protocols** | OneBot 11 (QQ), Telegram Bot API, Feishu, WeChat |
| **Backend** | FastAPI, Python, SQLite |
| **Frontend** | Vanilla JS, HTML/CSS |
| **Infra** | Docker Compose, Nginx, Node.js, Linux |
| **Channels** | QQ Bot · Telegram · Feishu · WeChat · Discord · Signal |

## 📁 Structure

```
openclaw-suite/
├── skills/              # OpenClaw agent skills
├── deployments/         # Deployment configs & scripts
│   └── youling-profile-site/   # Profile site (standalone HTML)
├── backend/             # Backend services (FastAPI, task queue)
└── ...
```

## 🚀 Quick Start

```bash
# Clone the repo
git clone https://github.com/ULing19/openclaw-suite.git
cd openclaw-suite

# View deployment docs
cat deployments/DEPLOY.md

# Check skill implementations
ls skills/
```

## 📂 Key Modules

### Skills (`skills/`)
Reusable OpenClaw agent skills for specialized tasks — STT, image gen, web search, etc.

### Deployments (`deployments/`)
Production-ready configs: Nginx routing, Docker Compose, HTTPS setup, and profile site.

### Backend (`backend/`)
FastAPI-based task worker and queue system with SQLite persistence.

## 📄 License

MIT — feel free to use, modify, and distribute.
