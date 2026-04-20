#!/usr/bin/env python3
"""Compatibility wrapper for scripts/image_sender.py."""

from pathlib import Path
import runpy


if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).with_name("scripts") / "image_sender.py"), run_name="__main__")
