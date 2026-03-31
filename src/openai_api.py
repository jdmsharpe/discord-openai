"""Backward-compatible shim for the old top-level openai_api module."""

from warnings import warn

from discord_openai import OpenAICog
from discord_openai.cogs.openai.embeds import (
    append_flat_pricing_embed,
    append_pricing_embed,
    append_response_embeds,
    append_sources_embed,
    append_thinking_embeds,
)
from discord_openai.cogs.openai.embeds import (
    error_embed as _error_embed,
)
from discord_openai.cogs.openai.responses import extract_summary_text
from discord_openai.cogs.openai.tooling import extract_tool_info

warn(
    "openai_api is deprecated; import from discord_openai instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "OpenAICog",
    "_error_embed",
    "append_flat_pricing_embed",
    "append_pricing_embed",
    "append_response_embeds",
    "append_sources_embed",
    "append_thinking_embeds",
    "extract_summary_text",
    "extract_tool_info",
]
