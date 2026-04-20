"""Minimal CLI helpers for the toolkit."""

from pathlib import Path
import runpy
import sys


_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS = _ROOT / "scripts"


def run_script(name: str) -> None:
    runpy.run_path(str(_SCRIPTS / name), run_name="__main__")


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python -m openclaw_multimodal_toolkit.cli <mail|multimodal|image-sender> [args...]")
        return 1
    command = sys.argv[1]
    sys.argv = [sys.argv[0], *sys.argv[2:]]
    mapping = {
        "mail": "mail-agent.py",
        "multimodal": "multimodal-agent.py",
        "image-sender": "image_sender.py",
    }
    script = mapping.get(command)
    if not script:
        print(f"Unknown command: {command}")
        return 1
    run_script(script)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
