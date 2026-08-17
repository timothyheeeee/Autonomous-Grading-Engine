from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.core.correlation import get_correlation_id

_LOG_BUFFER: list[dict[str, Any]] = []
MAX_BUFFER = 500


def _log_path() -> Path:
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return get_settings().logs_dir / f"agent-{day}.jsonl"


def log_event(event: str, **fields: Any) -> dict[str, Any]:
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "correlation_id": fields.pop("correlation_id", get_correlation_id()),
        "event": event,
        **fields,
    }
    _LOG_BUFFER.append(record)
    if len(_LOG_BUFFER) > MAX_BUFFER:
        del _LOG_BUFFER[: len(_LOG_BUFFER) - MAX_BUFFER]
    path = _log_path()
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, default=str) + "\n")
    return record


def recent_logs(limit: int = 100) -> list[dict[str, Any]]:
    return list(reversed(_LOG_BUFFER[-limit:]))
