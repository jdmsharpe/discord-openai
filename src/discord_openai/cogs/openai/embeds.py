from discord import Colour, Embed

from ...util import calculate_cost, calculate_tool_cost, chunk_text


def _fit_markdown_sections(
    sections: list[tuple[str | None, list[str]]],
    max_length: int = 4000,
) -> str:
    """Fit complete Markdown entries without slicing through links."""

    rendered_sections: list[str] = []
    for heading, entries in sections:
        accepted: list[str] = []
        for entry in entries:
            body = "\n".join([*accepted, entry])
            rendered = f"{heading}\n{body}" if heading else body
            candidate = "\n\n".join([*rendered_sections, rendered])
            if len(candidate) > max_length:
                break
            accepted.append(entry)
        if accepted:
            body = "\n".join(accepted)
            rendered_sections.append(f"{heading}\n{body}" if heading else body)
    return "\n\n".join(rendered_sections)


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

    sections: list[tuple[str | None, list[str]]] = []

    if citations:
        web_lines = [
            f"{index}. [{citation['title']}]({citation['url']})"
            for index, citation in enumerate(citations[:20], start=1)
        ]
        sections.append((None, web_lines))

    if file_citations:
        file_lines = [
            f"{index}. {citation['filename']}"
            for index, citation in enumerate(file_citations[:20], start=1)
        ]
        sections.append(("**Files referenced:**", file_lines))

    description = _fit_markdown_sections(sections)
    if not description:
        return

    embeds.append(Embed(title="Sources", description=description, color=Colour.blue()))


def append_research_sources_embed(
    embeds: list[Embed],
    citations: list[dict[str, str]],
    file_citations: list[dict[str, str]] | None = None,
) -> None:
    """Append a grouped 'Sources' embed for deep research, matching the Gemini bot.

    Mirrors discord-gemini's research citations layout: a ``**Web sources**`` group and
    a ``**Documents**`` group, each numbered and capped at 8 entries with an
    ``_…and N more_`` overflow line. Kept separate from the chat ``append_sources_embed``
    so the chat flow's source format is unaffected.
    """
    if not citations and not file_citations:
        return

    sections: list[tuple[str | None, list[str]]] = []
    if citations:
        numbered = [
            f"{index}. [{citation['title']}]({citation['url']})"
            for index, citation in enumerate(citations[:8], start=1)
        ]
        if len(citations) > 8:
            numbered.append(f"_…and {len(citations) - 8} more_")
        sections.append(("**Web sources**", numbered))
    if file_citations:
        numbered = [
            f"{index}. {citation['filename']}"
            for index, citation in enumerate(file_citations[:8], start=1)
        ]
        if len(file_citations) > 8:
            numbered.append(f"_…and {len(file_citations) - 8} more_")
        sections.append(("**Documents**", numbered))

    description = _fit_markdown_sections(sections)
    if not description:
        return
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


__all__ = [
    "append_flat_pricing_embed",
    "append_pricing_embed",
    "append_research_sources_embed",
    "append_response_embeds",
    "append_sources_embed",
    "append_thinking_embeds",
    "error_embed",
]
