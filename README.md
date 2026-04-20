# OpenClaw Multimodal Toolkit

[中文介绍](README.zh-CN.md)

Utilities and skill docs for building OpenClaw-based multimodal workflows across chat channels.

This repository is a cleaned public subset of a real OpenClaw workspace. Private memory files, logs, account identifiers, and local state were removed before publishing.

## Highlights

- Multimodal message understanding for images, audio, PDFs, Office files, and text files
- AI-assisted IMAP mail reply workflow
- Cross-channel image delivery for Telegram, Feishu, QQ, and WeChat
- OpenClaw-oriented skill docs and deployment examples
- Additional OpenClaw integration notes and OneBot plugin references

## Included Components

- `multimodal-agent.py`
  Unified entrypoint for image, audio, PDF, Office, archive, and text processing.
- `mail-agent.py`
  IMAP polling, AI reply generation, and optional OpenClaw channel notifications.
- `image_sender.py`
  Channel-specific image delivery helper for generated media.
- `skills/`
  OpenClaw skill docs for multimodal messaging, image generation delivery, and OneBot integration.
- `deploy/`
  Example environment and `systemd` assets for scheduled mail-agent deployment.
- `docs/`
  Integration notes for wiring the toolkit into an OpenClaw setup.

## Repository Layout

```text
.
├── image_sender.py
├── mail-agent.py
├── multimodal-agent.py
├── requirements.txt
├── .env.example
├── README.zh-CN.md
├── docs/
├── deploy/
└── skills/
```

## Requirements

- Python 3.10+
- OpenClaw CLI available in `PATH`
- `uvx minimax-coding-plan-mcp`
- Tesseract OCR
- Poppler utilities for `pdf2image`
- Optional local `faster-whisper` model cache for faster transcription

## Installation

Install Python dependencies:

```bash
pip install -r requirements.txt
```

Copy environment template:

```bash
cp .env.example .env
```

Fill in the values you actually use before running anything.

## Configuration

Important environment variables:

- `MINIMAX_API_KEY`
- `MINIMAX_API_HOST`
- `MINIMAX_URL`
- `MINIMAX_MODEL`
- `MAIL_AGENT_EMAIL_ACCOUNT`
- `MAIL_AGENT_EMAIL_PASSWORD`
- `MAIL_AGENT_TOKEN`
- `BRAVE_API_KEY`
- `MAIL_AGENT_NOTIFY_TARGETS`

`MAIL_AGENT_NOTIFY_TARGETS` expects a JSON array:

```json
[
  {"channel":"telegram","target":"telegram:<user_id>"},
  {"channel":"feishu","target":"<open_id>"}
]
```

See also:

- [Chinese introduction](README.zh-CN.md)
- [OpenClaw integration notes](docs/OPENCLAW_INTEGRATION.md)
- [Deployment examples](deploy/)

## Usage

Transcribe voice:

```bash
python3 multimodal-agent.py voice /path/to/audio.mp3
```

Process a file:

```bash
python3 multimodal-agent.py file /path/to/file.pdf
```

Modify a file with natural language:

```bash
python3 multimodal-agent.py modify /path/to/file.txt "Change the title to Q2 summary"
```

Deliver an image:

```bash
python3 image_sender.py /path/to/image.jpg telegram <telegram_user_id> "caption"
```

## OpenClaw-Specific Assumptions

This toolkit assumes an OpenClaw-style environment in a few places:

- local OpenClaw config under `~/.openclaw/`
- `openclaw message send` available as a CLI
- MiniMax MCP launched through `uvx minimax-coding-plan-mcp`
- channel delivery conventions matching OpenClaw plugins

If you want to reuse the scripts outside OpenClaw, expect to patch paths, config lookup, and message delivery adapters.

## Security Notes

- This public version intentionally excludes secrets, memory snapshots, queue data, and logs.
- Notification targets are configured through environment variables instead of hardcoded personal IDs.
- Review channel-delivery code before using it in another environment with different trust boundaries.

## License

[MIT](LICENSE)
