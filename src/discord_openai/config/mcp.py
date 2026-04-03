from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

LOGGER = logging.getLogger(__name__)

APPROVAL_ALWAYS = "always"
APPROVAL_NEVER = "never"
APPROVAL_SELECTIVE = "selective"


@dataclass(frozen=True)
class OpenAIMcpPreset:
    """Validated OpenAI MCP or connector preset loaded from config."""

    name: str
    kind: str
    server_label: str
    server_url: str | None = None
    connector_id: str | None = None
    server_description: str | None = None
    authorization_env_var: str | None = None
    allowed_tools: list[str] = field(default_factory=list)
    approval: str = APPROVAL_ALWAYS
    never_tool_names: list[str] = field(default_factory=list)
    available: bool = True
    unavailable_reason: str | None = None


def _load_json_object(raw_value: str, source_name: str) -> dict[str, object]:
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError as error:
        raise ValueError(f"{source_name} must contain valid JSON.") from error
    if not isinstance(parsed, dict):
        raise ValueError(f"{source_name} must be a JSON object keyed by preset name.")
    return parsed


def _validate_https_url(url: object, preset_name: str) -> str:
    if not isinstance(url, str) or not url.strip():
        raise ValueError(f"MCP preset `{preset_name}` requires a non-empty `server_url`.")
    normalized = url.strip()
    parsed = urlparse(normalized)
    if parsed.scheme != "https" or not parsed.netloc or not parsed.hostname:
        raise ValueError(f"MCP preset `{preset_name}` must use a valid HTTPS `server_url`.")
    return normalized


def _validate_tool_names(value: object, preset_name: str, field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"MCP preset `{preset_name}` `{field_name}` must be a list of strings.")
    deduped: list[str] = []
    seen: set[str] = set()
    for item in value:
        normalized = item.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _validate_preset(name: str, raw_value: object) -> OpenAIMcpPreset:
    if not isinstance(raw_value, dict):
        raise ValueError(f"MCP preset `{name}` must be an object.")

    supported_keys = {
        "kind",
        "server_label",
        "server_url",
        "connector_id",
        "server_description",
        "authorization_env_var",
        "allowed_tools",
        "approval",
        "never_tool_names",
    }
    extra_keys = sorted(set(raw_value) - supported_keys)
    if extra_keys:
        raise ValueError(f"MCP preset `{name}` contains unsupported keys: {', '.join(extra_keys)}.")

    kind = raw_value.get("kind")
    if kind not in {"remote_mcp", "connector"}:
        raise ValueError(f"MCP preset `{name}` `kind` must be `remote_mcp` or `connector`.")

    server_url: str | None = None
    connector_id: str | None = None
    if kind == "remote_mcp":
        server_url = _validate_https_url(raw_value.get("server_url"), name)
    else:
        connector_id = raw_value.get("connector_id")
        if not isinstance(connector_id, str) or not connector_id.strip():
            raise ValueError(f"MCP preset `{name}` requires a non-empty `connector_id`.")
        connector_id = connector_id.strip()

    server_label = raw_value.get("server_label")
    if server_label is not None and not isinstance(server_label, str):
        raise ValueError(f"MCP preset `{name}` `server_label` must be a string.")
    if not server_label:
        server_label = name

    server_description = raw_value.get("server_description")
    if server_description is not None and not isinstance(server_description, str):
        raise ValueError(f"MCP preset `{name}` `server_description` must be a string.")

    authorization_env_var = raw_value.get("authorization_env_var")
    if authorization_env_var is not None and not isinstance(authorization_env_var, str):
        raise ValueError(f"MCP preset `{name}` `authorization_env_var` must be a string.")

    approval = raw_value.get("approval", APPROVAL_ALWAYS)
    if approval not in {APPROVAL_ALWAYS, APPROVAL_NEVER, APPROVAL_SELECTIVE}:
        raise ValueError(
            f"MCP preset `{name}` `approval` must be `always`, `never`, or `selective`."
        )

    never_tool_names = _validate_tool_names(
        raw_value.get("never_tool_names"), name, "never_tool_names"
    )
    if approval == APPROVAL_SELECTIVE and not never_tool_names:
        raise ValueError(
            f"MCP preset `{name}` with `approval=selective` requires `never_tool_names`."
        )

    preset = OpenAIMcpPreset(
        name=name,
        kind=kind,
        server_label=server_label,
        server_url=server_url,
        connector_id=connector_id,
        server_description=server_description,
        authorization_env_var=authorization_env_var,
        allowed_tools=_validate_tool_names(raw_value.get("allowed_tools"), name, "allowed_tools"),
        approval=approval,
        never_tool_names=never_tool_names,
    )

    if preset.authorization_env_var and not os.getenv(preset.authorization_env_var):
        LOGGER.warning(
            "OpenAI MCP preset `%s` is unavailable because `%s` is not set.",
            name,
            preset.authorization_env_var,
        )
        return OpenAIMcpPreset(
            name=preset.name,
            kind=preset.kind,
            server_label=preset.server_label,
            server_url=preset.server_url,
            connector_id=preset.connector_id,
            server_description=preset.server_description,
            authorization_env_var=preset.authorization_env_var,
            allowed_tools=preset.allowed_tools,
            approval=preset.approval,
            never_tool_names=preset.never_tool_names,
            available=False,
            unavailable_reason=(
                f"MCP preset `{name}` requires the `{preset.authorization_env_var}` env var."
            ),
        )

    return preset


def load_openai_mcp_presets() -> dict[str, OpenAIMcpPreset]:
    merged: dict[str, object] = {}

    inline_json = os.getenv("OPENAI_MCP_PRESETS_JSON", "").strip()
    if inline_json:
        merged.update(_load_json_object(inline_json, "OPENAI_MCP_PRESETS_JSON"))

    presets_path = os.getenv("OPENAI_MCP_PRESETS_PATH", "").strip()
    if presets_path:
        file_data = Path(presets_path).read_text(encoding="utf-8")
        path_presets = _load_json_object(file_data, "OPENAI_MCP_PRESETS_PATH")
        duplicate_names = sorted(set(merged) & set(path_presets))
        if duplicate_names:
            raise ValueError(
                "Duplicate OpenAI MCP preset names found across env and file config: "
                + ", ".join(duplicate_names)
            )
        merged.update(path_presets)

    presets: dict[str, OpenAIMcpPreset] = {}
    for name, raw_value in merged.items():
        presets[name] = _validate_preset(name, raw_value)
    return presets


OPENAI_MCP_PRESETS = load_openai_mcp_presets()


def parse_mcp_preset_names(raw_value: str | None) -> list[str]:
    if raw_value is None:
        return []
    parsed_names: list[str] = []
    seen: set[str] = set()
    for piece in raw_value.split(","):
        name = piece.strip()
        if not name or name in seen:
            continue
        seen.add(name)
        parsed_names.append(name)
    return parsed_names


def resolve_mcp_presets(
    preset_names: list[str],
) -> tuple[list[OpenAIMcpPreset], str | None]:
    presets: list[OpenAIMcpPreset] = []
    for name in preset_names:
        preset = OPENAI_MCP_PRESETS.get(name)
        if preset is None:
            return [], f"Unknown MCP preset `{name}`."
        if not preset.available:
            return [], preset.unavailable_reason or f"MCP preset `{name}` is unavailable."
        presets.append(preset)
    return presets, None


def build_mcp_tool(preset: OpenAIMcpPreset) -> dict[str, object]:
    tool: dict[str, object] = {
        "type": "mcp",
        "server_label": preset.server_label,
        "require_approval": APPROVAL_ALWAYS,
    }
    if preset.kind == "remote_mcp":
        tool["server_url"] = preset.server_url
    else:
        tool["connector_id"] = preset.connector_id
    if preset.server_description:
        tool["server_description"] = preset.server_description
    if preset.authorization_env_var:
        authorization = os.getenv(preset.authorization_env_var)
        if authorization:
            tool["authorization"] = authorization
    if preset.allowed_tools:
        tool["allowed_tools"] = list(preset.allowed_tools)
    if preset.approval == APPROVAL_NEVER:
        tool["require_approval"] = "never"
    elif preset.approval == APPROVAL_SELECTIVE:
        tool["require_approval"] = {
            "never": {
                "tool_names": list(preset.never_tool_names),
            }
        }
    return tool


__all__ = [
    "APPROVAL_ALWAYS",
    "APPROVAL_NEVER",
    "APPROVAL_SELECTIVE",
    "OPENAI_MCP_PRESETS",
    "OpenAIMcpPreset",
    "build_mcp_tool",
    "load_openai_mcp_presets",
    "parse_mcp_preset_names",
    "resolve_mcp_presets",
]
