from __future__ import annotations

import json
import re

from .config import get_settings


def dumps_json(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def loads_json(value: str | None, default):
    if not value:
        return default
    return json.loads(value)


def serialize_traits(value: dict | None) -> str | None:
    return dumps_json(value) if value else None


def deserialize_traits(value: str | None) -> dict | None:
    return loads_json(value, None)


def job_result_image_url(job_code: str) -> str:
    settings = get_settings()
    return f"{settings.public_base_url.rstrip('/')}/api/try-on/jobs/{job_code}/result-image"


def build_style_code(name: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", name.strip().lower())
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    return normalized or "style"
