# OpenClaw Multimodal Toolkit

OpenClaw-oriented utilities for:

- multimodal message understanding across IM channels
- AI-assisted mail auto-reply
- generated-image delivery to Telegram, Feishu, QQ, and WeChat

This public snapshot removes private memory, logs, state files, and real account identifiers from the original workspace.

## Included

- `multimodal-agent.py`: image, voice, PDF, Office, and text-file processing
- `mail-agent.py`: IMAP polling + AI reply + optional channel notifications
- `image_sender.py`: channel-specific image delivery helper
- `skills/`: OpenClaw skill docs for multimodal messaging and image generation delivery

## Requirements

- Python 3.10+
- OpenClaw CLI available in `PATH`
- `uvx minimax-coding-plan-mcp`
- Tesseract OCR
- Poppler utilities for `pdf2image`
- Optional: `faster-whisper` model cache for faster local transcription

## Python dependencies

Install the main Python packages:

```bash
pip install -r requirements.txt
```

## Environment

Copy `.env.example` to `.env` and fill in the values you actually use.

Important variables:

- `MINIMAX_API_KEY`
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

## Notes

- The scripts assume an OpenClaw-style local environment and may need path adjustments outside that ecosystem.
- This repo intentionally does not include secrets, state snapshots, message history, or personal memory files.
