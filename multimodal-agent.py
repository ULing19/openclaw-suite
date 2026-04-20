#!/usr/bin/env python3
"""Compatibility wrapper for scripts/multimodal-agent.py."""

from pathlib import Path
import runpy


if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).with_name("scripts") / "multimodal-agent.py"), run_name="__main__")
