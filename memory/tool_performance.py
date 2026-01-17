import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any


def _log_path(base_dir: str = "memory") -> Path:
    base = Path(base_dir)
    base.mkdir(parents=True, exist_ok=True)
    return base / "tool_performance.jsonl"


def log_tool_performance(entry: dict[str, Any], base_dir: str = "memory") -> None:
    path = _log_path(base_dir)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def get_tool_performance_summary(max_entries: int = 50, base_dir: str = "memory") -> dict[str, Any]:
    path = _log_path(base_dir)
    if not path.exists():
        return {"total_calls": 0, "error_rate": 0.0, "avg_duration_ms": 0.0, "per_tool": {}, "recent_errors": []}

    lines = path.read_text(encoding="utf-8").splitlines()
    recent = lines[-max_entries:] if max_entries > 0 else lines
    entries = []
    for line in recent:
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    total = len(entries)
    if total == 0:
        return {"total_calls": 0, "error_rate": 0.0, "avg_duration_ms": 0.0, "per_tool": {}, "recent_errors": []}

    total_duration = 0.0
    error_count = 0
    per_tool: dict[str, dict[str, Any]] = {}
    recent_errors = []

    for entry in entries:
        tool = entry.get("tool_name", "unknown")
        duration = float(entry.get("duration_ms", 0.0))
        status = entry.get("status", "unknown")
        total_duration += duration
        if status == "error":
            error_count += 1
            if entry.get("error"):
                recent_errors.append({"tool_name": tool, "error": entry["error"]})

        if tool not in per_tool:
            per_tool[tool] = {"calls": 0, "errors": 0, "avg_duration_ms": 0.0}
        per_tool[tool]["calls"] += 1
        per_tool[tool]["errors"] += 1 if status == "error" else 0

    for tool, stats in per_tool.items():
        tool_entries = [e for e in entries if e.get("tool_name") == tool]
        if tool_entries:
            stats["avg_duration_ms"] = sum(float(e.get("duration_ms", 0.0)) for e in tool_entries) / len(tool_entries)

    return {
        "total_calls": total,
        "error_rate": round(error_count / total, 3),
        "avg_duration_ms": round(total_duration / total, 2),
        "per_tool": per_tool,
        "recent_errors": recent_errors[-10:]
    }


def build_tool_performance_entry(tool_name: str, status: str, duration_ms: float, args_count: int, error: str | None = None) -> dict[str, Any]:
    return {
        "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "tool_name": tool_name,
        "status": status,
        "duration_ms": round(duration_ms, 2),
        "args_count": args_count,
        "error": error
    }
