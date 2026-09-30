"""
Small shared helper functions: safe filenames, JSON list/dict serialization
helpers for SQLAlchemy Text columns, and misc formatting.
"""
import json
import re
import uuid
from pathlib import Path


def safe_filename(original_name: str) -> str:
    """Produce a filesystem-safe, collision-resistant filename."""
    stem = Path(original_name).stem
    suffix = Path(original_name).suffix
    stem = re.sub(r"[^A-Za-z0-9_\-]", "_", stem)[:60]
    unique = uuid.uuid4().hex[:8]
    return f"{stem}_{unique}{suffix}"


def to_json(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def from_json(value: str, default=None):
    if not value:
        return default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


def seconds_per_slide(duration_minutes: int, slide_count: int) -> float:
    if slide_count <= 0:
        return 60.0
    return max(15.0, (duration_minutes * 60) / slide_count)
