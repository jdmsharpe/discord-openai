"""Load OpenAI model pricing from pricing.yaml.

The YAML file ships with the package so pricing is always available. Set the
``OPENAI_PRICING_PATH`` environment variable to point at a different YAML file
for runtime overrides (e.g. when a vendor price change beats the next release).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


def _resolve_pricing_path() -> Path:
    override = os.getenv("OPENAI_PRICING_PATH")
    if override:
        return Path(override)
    return Path(__file__).with_name("pricing.yaml")


def _load_raw() -> dict[str, Any]:
    path = _resolve_pricing_path()
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise RuntimeError(f"{path} must contain a YAML mapping at the top level.")
    return data


_RAW: dict[str, Any] = _load_raw()
_MODELS: dict[str, dict[str, Any]] = _RAW.get("models") or {}
_TOOLS: dict[str, dict[str, Any]] = _RAW.get("tools") or {}
_IMAGE: dict[str, dict[str, Any]] = _RAW.get("image_generation") or {}
_TTS: dict[str, dict[str, Any]] = _RAW.get("text_to_speech") or {}
_STT: dict[str, dict[str, Any]] = _RAW.get("speech_to_text") or {}
_VIDEO: dict[str, dict[str, Any]] = _RAW.get("video_generation") or {}
_FALLBACKS: dict[str, dict[str, Any]] = _RAW.get("fallbacks") or {}


def _flatten_image_pricing() -> dict[tuple[str, str, str], float]:
    result: dict[tuple[str, str, str], float] = {}
    for model_id, cfg in _IMAGE.items():
        by_qs = cfg.get("by_quality_size") or {}
        for quality, sizes in by_qs.items():
            for size, price in (sizes or {}).items():
                result[(model_id, quality, size)] = float(price)
    return result


MODEL_PRICING: dict[str, tuple[float, float]] = {
    model_id: (float(cfg["input_per_million"]), float(cfg["output_per_million"]))
    for model_id, cfg in _MODELS.items()
}

TOOL_CALL_PRICING: dict[str, float] = {
    tool_id: float(cfg["per_call"]) for tool_id, cfg in _TOOLS.items()
}

IMAGE_PRICING: dict[tuple[str, str, str], float] = _flatten_image_pricing()

IMAGE_PRICING_DEFAULTS: dict[str, float] = {
    model_id: float(cfg["default_per_image"])
    for model_id, cfg in _IMAGE.items()
    if "default_per_image" in cfg
}

TTS_PRICING_PER_CHAR: dict[str, float] = {
    model_id: float(cfg["per_character"]) for model_id, cfg in _TTS.items()
}

STT_PRICING_PER_MINUTE: dict[str, float] = {
    model_id: float(cfg["per_minute"]) for model_id, cfg in _STT.items()
}

VIDEO_PRICING_PER_SECOND: dict[str, float] = {
    model_id: float(cfg["per_second"]) for model_id, cfg in _VIDEO.items()
}


def _fallback(key: str, field: str, default: float) -> float:
    value = (_FALLBACKS.get(key) or {}).get(field)
    return float(value) if value is not None else default


UNKNOWN_CHAT_MODEL_PRICING: tuple[float, float] = (
    _fallback("unknown_chat_model", "input_per_million", 2.50),
    _fallback("unknown_chat_model", "output_per_million", 10.00),
)
UNKNOWN_IMAGE_MODEL_PRICING: float = _fallback("unknown_image_model", "per_image", 0.034)
UNKNOWN_TTS_MODEL_PRICING: float = _fallback("unknown_tts_model", "per_character", 0.000015)
UNKNOWN_STT_MODEL_PRICING: float = _fallback("unknown_stt_model", "per_minute", 0.006)
UNKNOWN_VIDEO_MODEL_PRICING: float = _fallback("unknown_video_model", "per_second", 0.10)


__all__ = [
    "IMAGE_PRICING",
    "IMAGE_PRICING_DEFAULTS",
    "MODEL_PRICING",
    "STT_PRICING_PER_MINUTE",
    "TOOL_CALL_PRICING",
    "TTS_PRICING_PER_CHAR",
    "UNKNOWN_CHAT_MODEL_PRICING",
    "UNKNOWN_IMAGE_MODEL_PRICING",
    "UNKNOWN_STT_MODEL_PRICING",
    "UNKNOWN_TTS_MODEL_PRICING",
    "UNKNOWN_VIDEO_MODEL_PRICING",
    "VIDEO_PRICING_PER_SECOND",
]
