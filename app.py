"""Hugging Face Space entry point: check configuration, build the UI, launch."""

# `spaces` is preinstalled on Hugging Face Spaces (not a project dependency) and must be
# imported before other libraries on ZeroGPU hardware. It is absent in local development.
try:
    import spaces
except ImportError:
    spaces = None

import logging

from tutor.core.config import get_settings
from tutor.core.errors import ConfigError
from ui.app import build_demo

if spaces is not None:

    @spaces.GPU
    def _zerogpu_placeholder() -> None:
        """Never called. ZeroGPU (the free Space tier) refuses to start unless a @spaces.GPU
        function exists; all inference here is hosted, so no GPU work is ever requested."""


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

# Fail fast at startup (not on the first click) if HF_TOKEN or other settings are wrong.
try:
    get_settings()
except ConfigError as exc:
    raise SystemExit(f"Startup failed: {exc}") from None

demo = build_demo()

if __name__ == "__main__":
    demo.launch()
