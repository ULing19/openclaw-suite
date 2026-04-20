# OpenClaw Multimodal Toolkit

Utilities and skill docs for building OpenClaw-based multimodal workflows across chat channels.

This repository packages a cleaned-up public subset of a real OpenClaw workspace. Private memory files, logs, account identifiers, and local state have been removed before publishing.

## What It Does

- Understand incoming images through MiniMax MCP
- Transcribe voice messages with `faster-whisper`
- Extract text from PDFs, Office files, and plain-text documents
- Send generated images to Telegram, Feishu, QQ, and WeChat
- Poll IMAP mailboxes and generate AI-assisted email replies

## Included Components

- `multimodal-agent.py`
  Unified entrypoint for image, audio, PDF, Office, archive, and text processing.
- `mail-agent.py`
  IMAP polling + AI reply generation + optional OpenClaw channel notifications.
- `image_sender.py`
  Channel-specific image delivery helper for generated media.
- `skills/`
  OpenClaw skill docs for multimodal messaging and image generation delivery.

## Repository Layout

```text
.
├── image_sender.py
├── mail-agent.py
├── multimodal-agent.py
├── requirements.txt
├── .env.example
└── skills/
    ├── image-gen-deliver/
    └── multimodal-messaging/
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

`MAIL_AGENT_NOTIFY_TARGETS` expects a JSON array, for example:

```json
[
  {"channel":"telegram","target":"telegram:<user_id>"},
  {"channel":"feishu","target":"<open_id>"}
]
```

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
python3 multimodal-agent.py modify /path/to/file.txt "把标题改成季度总结"
```

Deliver an image:

```bash
python3 image_sender.py /path/to/image.jpg telegram <telegram_user_id> "caption"
```

## OpenClaw-Specific Assumptions

This code assumes an OpenClaw-style environment in a few places:

- local OpenClaw config under `~/.openclaw/`
- `openclaw message send` available as a CLI
- MiniMax MCP launched through `uvx minimax-coding-plan-mcp`
- channel delivery conventions matching OpenClaw plugins

If you want to reuse the scripts outside OpenClaw, expect to patch paths, config lookup, and message delivery adapters.

## Security Notes

- This public version intentionally excludes secrets, memory snapshots, queue data, and logs.
- Notification targets are now configured via environment variables instead of hardcoded personal IDs.
- Review channel-delivery code before using it in another environment with different trust boundaries.

## Current Status

This repository is a practical toolkit snapshot, not yet a polished framework package. It is best suited for:

- OpenClaw users who want working reference scripts
- people building similar multimodal chat automations
- adapting channel-delivery patterns for their own agent workflows

## License

No license file has been added yet. Until one is added, treat the repository as source-visible rather than open-source licensed.
