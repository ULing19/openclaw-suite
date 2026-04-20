# OpenClaw Suite

[中文介绍](README.zh-CN.md)

![cover](assets/cover.svg)

![Python](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-0f766e)
![Monorepo](https://img.shields.io/badge/repo-monorepo-334155)
![OpenClaw](https://img.shields.io/badge/OpenClaw-integrated-c0841a)

OpenClaw Suite is a practical monorepo for OpenClaw-oriented automation, multimodal tooling, web interfaces, deployment snippets, and skill references.

This repository started from a cleaned public subset of a real OpenClaw workspace and has been reorganized into a broader monorepo structure. Private memory files, logs, account identifiers, and local state were removed before publishing.

## What Lives Here

- multimodal message tooling across chat channels
- AI-assisted mail automation
- cross-channel media delivery
- OpenClaw skills and integration references
- a sanitized OpenClaw Web reference application
- deployment examples and environment templates

## Monorepo Layout

```text
.
├── apps/
│   └── openclaw-web/          # Sanitized reference web application
├── assets/                    # Repository-level artwork
├── deploy/                    # Example env/systemd assets
├── docs/                      # Integration notes and supporting docs
├── scripts/                   # Actual script implementations
├── skills/                    # OpenClaw skill references
├── src/                       # Lightweight Python package metadata/CLI
├── image_sender.py            # Compatibility wrapper
├── mail-agent.py              # Compatibility wrapper
├── multimodal-agent.py        # Compatibility wrapper
├── pyproject.toml
└── requirements.txt
```

## Main Components

| Area | Purpose |
|------|---------|
| `scripts/` | Runnable utilities for multimodal processing, email automation, and media delivery |
| `src/openclaw_multimodal_toolkit/` | Lightweight Python package and module-based CLI |
| `skills/` | OpenClaw-focused skill docs such as multimodal messaging, image delivery, and OneBot integration |
| `apps/openclaw-web/` | Reference FastAPI-based web UI with task mode and multimodal handling |
| `deploy/` | Example environment and `systemd` assets |
| `docs/` | Monorepo-level integration notes |

## Quick Start

Install dependencies:

```bash
pip install -r requirements.txt
pip install -e .
```

Copy the root environment template when using the toolkit scripts:

```bash
cp .env.example .env
```

For the web app, use the app-specific template:

```bash
cp apps/openclaw-web/config_example.env apps/openclaw-web/.env
```

## Typical Usage

Transcribe voice:

```bash
python3 multimodal-agent.py voice /path/to/audio.mp3
```

Process a file:

```bash
python3 multimodal-agent.py file /path/to/file.pdf
```

Deliver an image:

```bash
python3 image_sender.py /path/to/image.jpg telegram <telegram_user_id> "caption"
```

Module-based CLI:

```bash
python -m openclaw_multimodal_toolkit.cli multimodal voice /path/to/audio.mp3
python -m openclaw_multimodal_toolkit.cli image-sender /path/to/image.jpg telegram <telegram_user_id>
```

Run the web app:

```bash
cd apps/openclaw-web
python app.py
```

## Repository Positioning

This is intentionally a practical monorepo, not a highly abstract framework.

It is best suited for:

- OpenClaw users who want working reference code
- people building channel-aware multimodal automations
- developers who want reusable deployment snippets and integration examples
- teams that want one place for scripts, app references, and skill docs

## Important Sections

- [Chinese introduction](README.zh-CN.md)
- [OpenClaw integration notes](docs/OPENCLAW_INTEGRATION.md)
- [OpenClaw Web reference app](apps/openclaw-web/README.md)
- [OpenClaw Web deployment guide](apps/openclaw-web/DEPLOYMENT.md)
- [OneBot skill](skills/openclaw-onebot/SKILL.md)

## Security Notes

- This public version excludes secrets, memory snapshots, queue data, and logs.
- Notification targets are configured through environment variables instead of hardcoded personal IDs.
- The merged web app was sanitized before inclusion: hardcoded keys, personal branding, absolute production paths, and runtime artifacts were removed.

## License

[MIT](LICENSE)
