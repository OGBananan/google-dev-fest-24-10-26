"""Small in-process abuse limits for the single-worker demo service."""

from collections import defaultdict, deque
from threading import Lock
from time import monotonic

from fastapi import HTTPException

MAX_IMAGE_BYTES = 8 * 1024 * 1024
_events = defaultdict(deque)
_lock = Lock()


def limit(scope: str, client: str, count: int, seconds: int) -> None:
    now = monotonic()
    key = (scope, client)
    with _lock:
        events = _events[key]
        while events and events[0] <= now - seconds:
            events.popleft()
        if len(events) >= count:
            retry = max(1, int(seconds - (now - events[0])) + 1)
            raise HTTPException(429, "Too many requests. Please try again later.",
                                headers={"Retry-After": str(retry)})
        events.append(now)


def image_extension(data: bytes) -> str:
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "Photo must be between 1 byte and 8 MB")
    if data.startswith(b"\xff\xd8\xff") and data.endswith(b"\xff\xd9"):
        return ".jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return ".webp"
    raise HTTPException(415, "Please upload a JPEG, PNG, or WebP photo")


def message_text(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HTTPException(400, "message is required")
    if len(value) > 1000:
        raise HTTPException(413, "Message is too long (1000 characters max)")
    return value.strip()
