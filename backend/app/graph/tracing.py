from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.core.logging import log_event


def persist_trace(correlation_id: str, traces: list[dict[str, Any]], extra: dict[str, Any] | None = None) -> Path:
    payload = {
        "correlation_id": correlation_id,
        "ts": datetime.now(timezone.utc).isoformat(),
        "node_transitions": traces,
        **(extra or {}),
    }
    path = get_settings().traces_dir / f"{correlation_id}.json"
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    log_event("trace_persisted", path=str(path), nodes=len(traces))
    return path


def load_trace(correlation_id: str) -> dict[str, Any] | None:
    path = get_settings().traces_dir / f"{correlation_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
