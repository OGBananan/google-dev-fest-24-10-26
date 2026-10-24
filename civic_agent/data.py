"""Mock AMC store. Single JSON file, read-modify-write under a lock.

Not a database on purpose: the hackathon rules say mock the municipal system,
and one file keeps the whole data layer inspectable during the demo.
"""

import json
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "wards.json"
IST = timezone(timedelta(hours=5, minutes=30))

_lock = threading.Lock()


def load() -> dict:
    with DB_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def save(db: dict) -> None:
    tmp = DB_PATH.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(db, fh, indent=2, ensure_ascii=False)
    tmp.replace(DB_PATH)


def mutate(fn):
    """Apply fn to the loaded db under a lock, persist, return fn's result."""
    with _lock:
        db = load()
        result = fn(db)
        save(db)
        return result


def now_ist() -> str:
    return datetime.now(IST).isoformat(timespec="seconds")
