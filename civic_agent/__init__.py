"""Load .env before anything reads GOOGLE_API_KEY or GEMINI_MODEL at import time."""

from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from . import agent  # noqa: E402,F401  — adk web discovers root_agent through this
