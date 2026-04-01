from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypedDict

from ...config.auth import OPENAI_VECTOR_STORE_IDS

TOOL_WEB_SEARCH = {"type": "web_search"}
TOOL_CODE_INTERPRETER = {"type": "code_interpreter", "container": {"type": "auto"}}
TOOL_FILE_SEARCH = {
    "type": "file_search",
    "max_num_results": 5,
    "ranking_options": {"ranker": "auto", "score_threshold": 0.3},
}
TOOL_SHELL = {"type": "shell", "environment": {"type": "container_auto"}}


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    label: str
    description: str
    payload_factory: Callable[[], dict[str, Any]]
    availability_error: Callable[[str], str | None]
    billing_key: str | None = None


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
        billing_key="web_search",
    ),
    "code_interpreter": ToolDefinition(
        name="code_interpreter",
        label="Code Interpreter",
        description="Run Python code in a sandbox.",
        payload_factory=_build_code_interpreter_tool,
        availability_error=_always_available,
        billing_key="code_interpreter",
    ),
    "file_search": ToolDefinition(
        name="file_search",
        label="File Search",
        description="Search your indexed vector store files.",
        payload_factory=_build_file_search_tool,
        availability_error=_file_search_availability,
        billing_key="file_search",
    ),
    "shell": ToolDefinition(
        name="shell",
        label="Shell",
        description="Run commands in an OpenAI hosted container.",
        payload_factory=_build_shell_tool,
        availability_error=_shell_availability,
        billing_key="shell",
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


__all__ = [
    "TOOL_CODE_INTERPRETER",
    "TOOL_FILE_SEARCH",
    "TOOL_REGISTRY",
    "TOOL_SHELL",
    "TOOL_WEB_SEARCH",
    "ToolDefinition",
    "ToolSelectOption",
    "get_tool_definitions",
    "get_tool_select_options",
]
