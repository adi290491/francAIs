"""Hugging Face Space entry point: check configuration, build the UI, launch."""

import logging

from tutor.core.config import get_settings
from tutor.core.errors import ConfigError
from ui.app import build_demo

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

# Fail fast at startup (not on the first click) if HF_TOKEN or other settings are wrong.
try:
    get_settings()
except ConfigError as exc:
    raise SystemExit(f"Startup failed: {exc}") from None

demo = build_demo()

if __name__ == "__main__":
    demo.launch()
