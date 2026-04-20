#!/usr/bin/env python3
"""Compatibility wrapper for scripts/mail-agent.py."""

from pathlib import Path
import runpy


if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).with_name("scripts") / "mail-agent.py"), run_name="__main__")
