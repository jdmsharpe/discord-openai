from typing import Any

from ...util import REASONING_EFFORT_MEDIUM, REASONING_MODELS, UsageInfo, extract_usage


def build_reasoning_config(model: str, reasoning_effort: str | None) -> dict[str, str] | None:
    """Build the Responses API reasoning config for a chat request."""
    if model in REASONING_MODELS:
        return {
            "effort": reasoning_effort or REASONING_EFFORT_MEDIUM,
            "summary": "auto",
        }
    if reasoning_effort:
        return {"effort": reasoning_effort, "summary": "auto"}
    return None


def get_response_text(response: Any) -> str:
    """Return the primary text output for an OpenAI response."""
    return getattr(response, "output_text", None) or "No response."


def extract_summary_text(response: Any) -> str:
    """Extract reasoning summary text from a Responses API object."""
    parts: list[str] = []
    output_items = getattr(response, "output", None) or []
    for item in output_items:
        if getattr(item, "type", None) != "reasoning":
            continue
        for block in getattr(item, "summary", None) or []:
            if getattr(block, "type", None) == "summary_text":
                text = getattr(block, "text", None)
                if text:
                    parts.append(text)
    return "\n\n".join(parts)


def get_usage(response: Any) -> UsageInfo:
    """Return normalized usage info for downstream cost tracking."""
    return extract_usage(response)


__all__ = [
    "build_reasoning_config",
    "extract_summary_text",
    "get_response_text",
    "get_usage",
]
