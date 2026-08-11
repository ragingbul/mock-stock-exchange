"""Debug session logging (NDJSON). Remove after verification."""

from __future__ import annotations

import json
import time
from pathlib import Path

_LOG = Path(__file__).resolve().parents[3] / "debug-2cb40a.log"
_SESSION = "2cb40a"


def dbg_log(
    location: str,
    message: str,
    data: dict,
    hypothesis_id: str,
    run_id: str = "pre-fix",
) -> None:
    try:
        payload = {
            "sessionId": _SESSION,
            "runId": run_id,
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        with _LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, default=str) + "\n")
    except Exception:
        pass
