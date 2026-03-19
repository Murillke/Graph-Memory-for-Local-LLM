"""Shared MCP handler utilities."""

from __future__ import annotations

import json
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional, Union

from typing_extensions import TypedDict  # Required for Python < 3.12 with Pydantic

from tools.config import Config, load_config
from tools.mcp_network import MCPNetworkConfig, validate_mcp_network_config


class SuccessResponse(TypedDict):
    status: Literal["ok"]
    data: Dict[str, Any]


class ErrorResponse(TypedDict, total=False):
    status: Literal["error"]
    type: Literal["validation", "not_found", "internal", "config"]
    message: str
    errors: List[str]


Response = Union[SuccessResponse, ErrorResponse]

_CURRENT_NETWORK_CERT_METADATA: ContextVar[Optional[Dict[str, Any]]] = ContextVar(
    "current_network_cert_metadata",
    default=None,
)


@dataclass
class RuntimeState:
    """Resolved runtime state for MCP handlers."""

    config: Config
    project_name: Optional[str]
    graph_db_path: str
    sql_db_path: str
    mcp_config: MCPNetworkConfig


def ok(data: Dict[str, Any]) -> SuccessResponse:
    return {
        "status": "ok",
        "data": data,
    }


def fail(
    error_type: Literal["validation", "not_found", "internal", "config"],
    message: str,
    *,
    errors: Optional[List[str]] = None,
) -> ErrorResponse:
    response: ErrorResponse = {
        "status": "error",
        "type": error_type,
        "message": message,
    }
    if errors:
        response["errors"] = errors
    return response


def load_runtime_state(config_path: Optional[str] = None) -> RuntimeState:
    """Load config and validate MCP network settings."""
    config = load_config(config_path=config_path)
    mcp_config = MCPNetworkConfig.from_dict(config.get_mcp_config())
    errors = validate_mcp_network_config(mcp_config)
    if errors:
        raise ValueError("; ".join(errors))

    project_name = config.get_project_name()
    return RuntimeState(
        config=config,
        project_name=project_name,
        graph_db_path=config.get_graph_db_path(project_name),
        sql_db_path=config.get_sql_db_path(),
        mcp_config=mcp_config,
    )


def require_project(state: RuntimeState) -> str:
    """Return the configured project name or raise a config error."""
    if not state.project_name:
        raise LookupError("No project_name configured in mem.config.json")
    return state.project_name


def parse_json_field(value: Any, default: Any) -> Any:
    """Return parsed JSON when stored as a string, otherwise the original value."""
    if value in (None, ""):
        return default
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


def set_current_network_cert_metadata(metadata: Optional[Dict[str, Any]]) -> None:
    """Set best-effort network certificate metadata for the current request context."""
    _CURRENT_NETWORK_CERT_METADATA.set(metadata)


def get_current_network_cert_metadata() -> Optional[Dict[str, Any]]:
    """Get best-effort network certificate metadata for the current request context."""
    return _CURRENT_NETWORK_CERT_METADATA.get()
