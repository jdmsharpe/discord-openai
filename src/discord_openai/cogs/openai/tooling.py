from typing import Any, TypedDict

from ...util import AVAILABLE_TOOLS


class ToolInfo(TypedDict):
    tool_types: list[str]
    tool_call_counts: dict[str, int]
    citations: list[dict[str, str]]
    file_citations: list[dict[str, str]]


def extract_tool_info(response: Any) -> ToolInfo:
    """Extract tool usage, web citations, and file citations from a Responses API object."""

    def get_value(item: Any, key: str, default: Any = None) -> Any:
        if isinstance(item, dict):
            return item.get(key, default)
        return getattr(item, key, default)

    citations: list[dict[str, str]] = []
    file_citations: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    seen_file_ids: set[str] = set()
    tools_used: set[str] = set()
    tool_call_counts: dict[str, int] = {}

    call_type_map = {
        "web_search_call": "web_search",
        "file_search_call": "file_search",
        "code_interpreter_call": "code_interpreter",
        "shell_call": "shell",
    }

    output_items = get_value(response, "output", []) or []
    for output_item in output_items:
        output_type = get_value(output_item, "type")
        item_name = get_value(output_item, "name")

        tool_key = call_type_map.get(output_type) or (
            item_name if item_name in AVAILABLE_TOOLS else None
        )
        if tool_key:
            tools_used.add(tool_key)
            tool_call_counts[tool_key] = tool_call_counts.get(tool_key, 0) + 1

        content_blocks = get_value(output_item, "content", []) or []
        for content_block in content_blocks:
            annotations = get_value(content_block, "annotations", []) or []
            for annotation in annotations:
                annotation_type = get_value(annotation, "type")

                if annotation_type == "url_citation":
                    url = get_value(annotation, "url")
                    title = get_value(annotation, "title") or url
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)
                    citations.append({"title": title, "url": url})
                    tools_used.add("web_search")
                elif annotation_type == "file_citation":
                    file_id = get_value(annotation, "file_id") or ""
                    filename = get_value(annotation, "filename") or file_id
                    if not file_id or file_id in seen_file_ids:
                        continue
                    seen_file_ids.add(file_id)
                    file_citations.append({"filename": filename, "file_id": file_id})

    return {
        "tool_types": sorted(tools_used),
        "tool_call_counts": tool_call_counts,
        "citations": citations,
        "file_citations": file_citations,
    }
