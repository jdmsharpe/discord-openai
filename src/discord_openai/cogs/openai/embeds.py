from typing import Any

from discord import Colour, Embed

from ...util import calculate_cost, calculate_tool_cost, chunk_text, truncate_text


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


def append_thinking_embeds(embeds: list[Embed], thinking_text: str) -> None:
    """Append thinking summary as a spoilered Discord embed."""
    if not thinking_text:
        return

    if len(thinking_text) > 3500:
        thinking_text = thinking_text[:3450] + "\n\n... [thinking truncated]"

    embeds.append(
        Embed(
            title="Thinking",
            description=f"||{thinking_text}||",
            color=Colour.light_grey(),
        )
    )


def append_response_embeds(embeds, response_text):
    """Append response text, chunked to respect Discord limits."""
    used = sum(len(e.description or "") for e in embeds)
    available = max(500, 6000 - used - 500)
    if len(response_text) > available:
        response_text = truncate_text(response_text, available)

    for index, chunk in enumerate(chunk_text(response_text), start=1):
        embeds.append(
            Embed(
                title="Response" + (f" (Part {index})" if index > 1 else ""),
                description=chunk,
                color=Colour.blue(),
            )
        )


def append_sources_embed(
    embeds: list[Embed],
    citations: list[dict[str, str]],
    file_citations: list[dict[str, str]] | None = None,
) -> None:
    """Append a sources embed listing web links and/or file citations."""
    if not citations and not file_citations:
        return

    parts: list[str] = []

    if citations:
        web_lines = [
            f"{index}. [{citation['title']}]({citation['url']})"
            for index, citation in enumerate(citations[:20], start=1)
        ]
        parts.append("\n".join(web_lines))

    if file_citations:
        file_lines = [
            f"{index}. {citation['filename']}"
            for index, citation in enumerate(file_citations[:20], start=1)
        ]
        parts.append("**Files referenced:**\n" + "\n".join(file_lines))

    description = "\n\n".join(parts)
    current_total = sum(len(embed.description or "") + len(embed.title or "") for embed in embeds)
    remaining_chars = 6000 - current_total - len("Sources")
    if remaining_chars < 50:
        return

    max_description_length = min(4096, remaining_chars)
    if max_description_length <= 0:
        return

    if len(description) > max_description_length:
        description = truncate_text(description, max_description_length - 3)

    embeds.append(Embed(title="Sources", description=description, color=Colour.blue()))


def append_pricing_embed(
    embeds: list[Embed],
    model: str,
    input_tokens: int,
    output_tokens: int,
    daily_cost: float,
    cached_tokens: int = 0,
    reasoning_tokens: int = 0,
    tool_call_counts: dict[str, int] | None = None,
) -> None:
    """Append a compact pricing embed showing model, cost, and token usage."""
    tool_cost = calculate_tool_cost(tool_call_counts) if tool_call_counts else 0.0
    cost = calculate_cost(model, input_tokens, output_tokens, cached_tokens) + tool_cost
    in_part = f"{input_tokens:,} in"
    if cached_tokens:
        in_part += f" ({cached_tokens:,} cached)"
    visible_tokens = output_tokens - reasoning_tokens
    out_part = f"{visible_tokens:,} out"
    if reasoning_tokens:
        out_part += f" / {reasoning_tokens:,} thinking"
    parts = [f"${cost:.4f}", f"{in_part} / {out_part}"]
    if tool_call_counts:
        tool_str = " + ".join(
            f"{tool.replace('_', ' ')} ×{count}" for tool, count in sorted(tool_call_counts.items())
        )
        parts.append(f"tools: {tool_str} (${tool_cost:.4f})")
    parts.append(f"daily ${daily_cost:.2f}")
    embeds.append(Embed(description=" · ".join(parts), color=Colour.blue()))


def append_flat_pricing_embed(
    embeds: list[Embed],
    cost: float,
    daily_cost: float,
    details: str = "",
) -> None:
    """Append a compact pricing embed for non-token-based commands."""
    parts = [f"${cost:.4f}"]
    if details:
        parts.append(details)
    parts.append(f"daily ${daily_cost:.2f}")
    embeds.append(Embed(description=" · ".join(parts), color=Colour.blue()))


def error_embed(description: str) -> Embed:
    """Create a red error embed with the given description."""
    return Embed(title="Error", description=description, color=Colour.red())
