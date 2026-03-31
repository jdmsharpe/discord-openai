from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypedDict

from ...config.auth import OPENAI_VECTOR_STORE_IDS
from ...config.mcp import build_mcp_tool, resolve_mcp_presets

TOOL_WEB_SEARCH = {"type": "web_search"}
TOOL_CODE_INTERPRETER = {"type": "code_interpreter", "container": {"type": "auto"}}
TOOL_FILE_SEARCH = {
    "type": "file_search",
    "max_num_results": 5,
    "ranking_options": {"ranker": "auto", "score_threshold": 0.3},
}
TOOL_SHELL = {"type": "shell", "environment": {"type": "container_auto"}}
CALL_LIKE_OUTPUT_TYPES = frozenset({"computer_call", "custom_tool_call", "function_call"})


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    label: str
    description: str
    payload_factory: Callable[[], dict[str, Any]]
    availability_error: Callable[[str], str | None]


class ToolInfo(TypedDict):
    tool_types: list[str]
    tool_call_counts: dict[str, int]
    citations: list[dict[str, str]]
    file_citations: list[dict[str, str]]
    mcp_calls: list[dict[str, str]]
    mcp_list_tools: list[dict[str, Any]]
    pending_mcp_approval: dict[str, Any] | None


class ToolSelectOption(TypedDict):
    label: str
    value: str
    description: str
    default: bool


def _always_available(_: str) -> str | None:
    return None


def _file_search_availability(_: str) -> str | None:
    if not OPENAI_VECTOR_STORE_IDS:
        return "File search requires OPENAI_VECTOR_STORE_IDS to be set in your .env."
    return None


def _shell_availability(model: str) -> str | None:
    if not model.startswith("gpt-5"):
        return "Shell currently requires a GPT-5 series model in this bot configuration."
    return None


def _build_web_search_tool() -> dict[str, Any]:
    return TOOL_WEB_SEARCH.copy()


def _build_code_interpreter_tool() -> dict[str, Any]:
    return {
        "type": TOOL_CODE_INTERPRETER["type"],
        "container": dict(TOOL_CODE_INTERPRETER["container"]),
    }


def _build_file_search_tool() -> dict[str, Any]:
    return {
        "type": TOOL_FILE_SEARCH["type"],
        "max_num_results": TOOL_FILE_SEARCH["max_num_results"],
        "ranking_options": dict(TOOL_FILE_SEARCH["ranking_options"]),
        "vector_store_ids": OPENAI_VECTOR_STORE_IDS.copy(),
    }


def _build_shell_tool() -> dict[str, Any]:
    return {
        "type": TOOL_SHELL["type"],
        "environment": dict(TOOL_SHELL["environment"]),
    }


TOOL_REGISTRY: dict[str, ToolDefinition] = {
    "web_search": ToolDefinition(
        name="web_search",
        label="Web Search",
        description="Search the web for current information.",
        payload_factory=_build_web_search_tool,
        availability_error=_always_available,
    ),
    "code_interpreter": ToolDefinition(
        name="code_interpreter",
        label="Code Interpreter",
        description="Run Python code in a sandbox.",
        payload_factory=_build_code_interpreter_tool,
        availability_error=_always_available,
    ),
    "file_search": ToolDefinition(
        name="file_search",
        label="File Search",
        description="Search your indexed vector store files.",
        payload_factory=_build_file_search_tool,
        availability_error=_file_search_availability,
    ),
    "shell": ToolDefinition(
        name="shell",
        label="Shell",
        description="Run commands in an OpenAI hosted container.",
        payload_factory=_build_shell_tool,
        availability_error=_shell_availability,
    ),
}


def get_tool_definitions() -> tuple[ToolDefinition, ...]:
    """Return the currently registered tool definitions."""
    return tuple(TOOL_REGISTRY.values())


def get_tool_select_options(selected_tool_types: set[str] | None = None) -> list[ToolSelectOption]:
    """Build UI-ready tool option metadata from the centralized registry."""
    selected_tool_types = selected_tool_types or set()
    return [
        {
            "label": definition.label,
            "value": definition.name,
            "description": definition.description,
            "default": definition.name in selected_tool_types,
        }
        for definition in get_tool_definitions()
    ]


def get_tool_select_max_values() -> int:
    """Return the max number of tool options the selector should permit."""
    return len(TOOL_REGISTRY)


def is_known_tool(tool_name: str) -> bool:
    return tool_name in TOOL_REGISTRY


def normalize_tool_name(raw_name: str | None) -> str | None:
    if raw_name is None:
        return None
    normalized = raw_name.strip()
    if not normalized:
        return None
    if normalized.endswith("_call"):
        return normalized.removesuffix("_call")
    return normalized


def resolve_selected_tools(
    selected_tool_names: list[str],
    model: str,
    mcp_preset_names: list[str] | None = None,
) -> tuple[list[dict[str, Any]], str | None]:
    """Build tool payloads for selected tool names and model constraints."""
    tools: list[dict[str, Any]] = []
    seen_tool_names: set[str] = set()

    for tool_name in selected_tool_names:
        if tool_name in seen_tool_names:
            continue
        seen_tool_names.add(tool_name)

        definition = TOOL_REGISTRY.get(tool_name)
        if definition is None:
            continue

        error = definition.availability_error(model)
        if error:
            return [], error

        tools.append(definition.payload_factory())

    mcp_presets, mcp_error = resolve_mcp_presets(mcp_preset_names or [])
    if mcp_error:
        return [], mcp_error
    for preset in mcp_presets:
        tools.append(build_mcp_tool(preset))

    return tools, None


def extract_tool_info(response: Any) -> ToolInfo:
    """Extract tool usage, web citations, and file citations from a Responses API object."""

    def get_value(item: Any, key: str, default: Any = None) -> Any:
        if isinstance(item, dict):
            return item.get(key, default)
        return getattr(item, key, default)

    def extract_tool_key(output_item: Any) -> str | None:
        output_type = get_value(output_item, "type")
        item_name = get_value(output_item, "name")

        if item_name and (
            output_type in CALL_LIKE_OUTPUT_TYPES
            or (isinstance(output_type, str) and output_type.endswith("_call"))
        ):
            return normalize_tool_name(item_name)

        if isinstance(output_type, str) and (
            output_type in CALL_LIKE_OUTPUT_TYPES or output_type.endswith("_call")
        ):
            return normalize_tool_name(output_type)

        if isinstance(item_name, str) and item_name in TOOL_REGISTRY:
            return item_name

        return None

    citations: list[dict[str, str]] = []
    file_citations: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    seen_file_ids: set[str] = set()
    tools_used: set[str] = set()
    tool_call_counts: dict[str, int] = {}
    mcp_calls: list[dict[str, str]] = []
    mcp_list_tools: list[dict[str, Any]] = []
    pending_mcp_approval: dict[str, Any] | None = None

    output_items = get_value(response, "output", []) or []
    for output_item in output_items:
        output_type = get_value(output_item, "type")
        tool_key = extract_tool_key(output_item)

        if tool_key:
            tools_used.add(tool_key)
            tool_call_counts[tool_key] = tool_call_counts.get(tool_key, 0) + 1

        if output_type == "mcp_list_tools":
            mcp_list_tools.append(
                {
                    "server_label": get_value(output_item, "server_label"),
                    "tools": get_value(output_item, "tools", []),
                }
            )
            tools_used.add("mcp")
            continue

        if output_type == "mcp_call":
            mcp_calls.append(
                {
                    "server_label": get_value(output_item, "server_label") or "",
                    "name": get_value(output_item, "name") or "",
                    "output": get_value(output_item, "output") or "",
                }
            )
            tools_used.add("mcp")
            continue

        if output_type == "mcp_approval_request" and pending_mcp_approval is None:
            pending_mcp_approval = {
                "approval_request_id": get_value(output_item, "id") or "",
                "server_label": get_value(output_item, "server_label") or "",
                "tool_name": get_value(output_item, "name") or "",
                "arguments": get_value(output_item, "arguments") or "",
            }
            tools_used.add("mcp")
            continue

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
        "mcp_calls": mcp_calls,
        "mcp_list_tools": mcp_list_tools,
        "pending_mcp_approval": pending_mcp_approval,
    }


__all__ = [
    "TOOL_CODE_INTERPRETER",
    "TOOL_FILE_SEARCH",
    "TOOL_REGISTRY",
    "TOOL_SHELL",
    "TOOL_WEB_SEARCH",
    "ToolDefinition",
    "ToolInfo",
    "ToolSelectOption",
    "extract_tool_info",
    "get_tool_definitions",
    "get_tool_select_max_values",
    "get_tool_select_options",
    "is_known_tool",
    "normalize_tool_name",
    "resolve_selected_tools",
]
