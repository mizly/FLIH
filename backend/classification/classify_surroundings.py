#!/usr/bin/env python3
"""Classify a robot's surroundings from a camera frame and optional LiDAR scan."""
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx

from yibu_audit import append_audit_record


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_IMAGE = Path(__file__).with_name("images.jpg")
DEFAULT_AUDIT_LOG = REPO_ROOT / ".data" / "yibu_api_calls.jsonl"

SYSTEM_PROMPT = """You are the perception module for a small indoor mobile robot.
Fuse the camera image with the LiDAR readings when present. Do not invent objects
that are not supported by either sensor. Return ONLY one valid JSON object with:
scene_type (string), summary (string), objects (array of strings),
traversable_directions (array chosen from front/left/right/back),
hazards (array of strings), nearest_obstacle_m (number or null),
confidence (number from 0 to 1), and reasoning (one short string).
Treat LiDAR distances as stronger evidence for clearance and collision risk, and
the image as stronger evidence for semantic labels."""


def load_env(path: Path) -> None:
    """Load simple KEY=VALUE entries without overriding the process environment."""
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key:
            os.environ.setdefault(key, value)


def data_url(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def load_lidar(path: Path | None) -> Any | None:
    if path is None:
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    ranges = value.get("ranges") if isinstance(value, dict) else value
    if not isinstance(ranges, list) or not ranges:
        raise ValueError("LiDAR JSON must contain a non-empty distance array")
    if not all(isinstance(item, (int, float)) or item is None for item in ranges):
        raise ValueError("LiDAR ranges must contain only numbers or null")
    return value


def extract_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        cleaned = "\n".join(lines[1:-1]).strip()
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("OMNI response did not contain a JSON object") from None
        value = json.loads(cleaned[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("OMNI response JSON was not an object")
    return value


def classify(image: Path, lidar: Any | None, purpose: str) -> dict[str, Any]:
    load_env(REPO_ROOT / ".env")
    api_key = os.getenv("YIBU_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("YIBU_API_KEY is missing; add it to the repository's .env file")
    base_url = os.getenv("YIBU_BASE_URL", "https://yibuapi.com/v1").rstrip("/")
    model = os.getenv("YIBU_MODEL", "qwen3.5-omni-plus")
    endpoint = f"{base_url}/chat/completions"
    sensor_context = (
        "No LiDAR scan was provided; infer geometry only from the image."
        if lidar is None
        else "LiDAR scan JSON (distances are metres unless unit says otherwise):\n"
        + json.dumps(lidar, separators=(",", ":"))
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": [
                {"type": "text", "text": sensor_context},
                {"type": "image_url", "image_url": {"url": data_url(image)}},
            ]},
        ],
        "temperature": 0.1,
        "max_tokens": 500,
    }
    started = time.monotonic()
    status_code: int | None = None
    response_json: dict[str, Any] = {}
    try:
        with httpx.Client(timeout=300.0, trust_env=False) as client:
            response = client.post(
                endpoint,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
            )
        status_code = response.status_code
        try:
            parsed = response.json()
            response_json = parsed if isinstance(parsed, dict) else {}
        except ValueError:
            response_json = {}
        response.raise_for_status()
        record = append_audit_record(
            model=model, api_key=api_key, endpoint=endpoint, purpose=purpose,
            transport="http", ok=True, status_code=status_code,
            latency_s=time.monotonic() - started, response_json=response_json,
            audit_log=DEFAULT_AUDIT_LOG,
        )
    except Exception as exc:
        append_audit_record(
            model=model, api_key=api_key, endpoint=endpoint, purpose=purpose,
            transport="http", ok=False, status_code=status_code,
            latency_s=time.monotonic() - started, response_json=response_json,
            error=f"{type(exc).__name__}: {exc}", audit_log=DEFAULT_AUDIT_LOG,
        )
        raise
    choices = response_json.get("choices") or []
    text = choices[0].get("message", {}).get("content", "") if choices else ""
    result = extract_json(text)
    result["call_id"] = record["call_id"]
    result["model"] = model
    result["usage"] = {
        "input_tokens": record["input_tokens"],
        "output_tokens": record["output_tokens"],
        "total_tokens": record["total_tokens"],
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, default=DEFAULT_IMAGE)
    parser.add_argument("--lidar", type=Path, help="Optional LiDAR scan JSON")
    parser.add_argument("--purpose", default="surroundings_classification")
    args = parser.parse_args()
    if not args.image.is_file():
        parser.error(f"image does not exist: {args.image}")
    try:
        result = classify(args.image, load_lidar(args.lidar), args.purpose)
    except (OSError, ValueError, RuntimeError, httpx.HTTPError) as exc:
        print(f"classification failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
