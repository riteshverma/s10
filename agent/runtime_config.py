from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

import yaml
from google.genai import types

ROOT = Path(__file__).parent.parent
PROFILE_YAML = ROOT / "config" / "profiles.yaml"


@lru_cache(maxsize=1)
def load_profile() -> Dict[str, Any]:
    try:
        return yaml.safe_load(PROFILE_YAML.read_text()) or {}
    except FileNotFoundError:
        return {}


def is_deterministic() -> bool:
    llm = load_profile().get("llm", {})
    return bool(llm.get("deterministic", False))


def get_llm_generation_settings() -> Dict[str, Any]:
    llm = load_profile().get("llm", {})
    return llm.get("generation", {}) or {}


def gemini_generation_config() -> types.GenerateContentConfig | None:
    settings = get_llm_generation_settings()
    if not settings:
        return None
    return types.GenerateContentConfig(
        temperature=settings.get("temperature", 0.0),
        top_p=settings.get("top_p", 1.0),
        top_k=settings.get("top_k", 1),
        max_output_tokens=settings.get("max_output_tokens", 1024),
        candidate_count=settings.get("candidate_count", 1),
    )


def stable_run_id(*parts: object) -> str:
    joined = "||".join("" if part is None else str(part) for part in parts)
    digest = hashlib.sha256(joined.encode("utf-8")).hexdigest()
    return f"det-{digest[:16]}"


def deterministic_timestamp() -> str:
    return "1970-01-01T00:00:00Z"


def get_tool_retry_settings() -> Dict[str, Any]:
    retry_cfg = load_profile().get("tools", {}).get("retry", {}) or {}
    return {
        "max_attempts": int(retry_cfg.get("max_attempts", 3)),
        "backoff_ms": int(retry_cfg.get("backoff_ms", 250)),
        "backoff_multiplier": float(retry_cfg.get("backoff_multiplier", 2.0)),
    }


def get_execution_seed(default_seed: int = 0) -> int:
    execution_cfg = load_profile().get("execution", {}) or {}
    return int(execution_cfg.get("deterministic_seed", default_seed))


def get_perception_retry_settings() -> Dict[str, Any]:
    """Perception retry settings: avoid excess LLM calls while allowing confidence to rise."""
    perception_cfg = load_profile().get("perception", {}) or {}
    return {
        "max_attempts": min(10, max(1, int(perception_cfg.get("max_retries", 5)))),
        "early_exit_after_no_improvement": min(5, max(1, int(perception_cfg.get("early_exit_no_improvement_attempts", 2)))),
    }
