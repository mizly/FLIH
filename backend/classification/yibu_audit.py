"""Append-only Yibu API usage accounting without request or response content."""
from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


def _integer(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_usage(response_json: Mapping[str, Any] | None) -> dict[str, Any]:
    data = response_json or {}
    usage = data.get("usage") if isinstance(data.get("usage"), Mapping) else {}
    input_tokens = _integer(usage.get("prompt_tokens") or usage.get("input_tokens"))
    output_tokens = _integer(usage.get("completion_tokens") or usage.get("output_tokens"))
    total_tokens = _integer(usage.get("total_tokens"))
    derived = False
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens, derived = input_tokens + output_tokens, True
    return {
        "input_tokens": input_tokens, "output_tokens": output_tokens,
        "total_tokens": total_tokens, "usage_reported": bool(usage),
        "total_tokens_derived": derived, "usage_raw": dict(usage),
    }


def append_audit_record(*, model: str, api_key: str, endpoint: str,
                        purpose: str, transport: str, ok: bool, latency_s: float,
                        response_json: Mapping[str, Any] | None = None,
                        status_code: int | None = None, error: str | None = None,
                        audit_log: str | Path) -> dict[str, Any]:
    record: dict[str, Any] = {
        "schema_version": "yibu_call_audit_v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "timestamp_local": time.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "call_id": uuid.uuid4().hex, "provider": "yibuapi", "model": model,
        "key_suffix": "..." + api_key[-4:], "purpose": purpose,
        "transport": transport, "endpoint": endpoint, "ok": ok,
        "status_code": status_code, "latency_s": round(latency_s, 4),
        **normalize_usage(response_json),
    }
    if error:
        record["error"] = error.replace(api_key, "[REDACTED]")[:2000]
    path = Path(audit_log)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
    fd = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
    try:
        os.write(fd, payload)
    finally:
        os.close(fd)
    return record
