"""Allowlisted tools for the simulated staging service."""

from copy import deepcopy
from dataclasses import dataclass


SERVICE = "checkout-api"
ROLLBACK_TARGETS = ("10", "11")


@dataclass
class ToolDef:
    name: str
    kind: str
    params: dict
    dur_ms: int


TOOLS = {
    "get_deployment_status": ToolDef("get_deployment_status", "ro", {
        "service": {"type": "string", "enum": [SERVICE]},
    }, 2000),
    "rollback_deployment": ToolDef("rollback_deployment", "irrev", {
        "service": {"type": "string", "enum": [SERVICE]},
        "release": {"type": "string", "enum": list(ROLLBACK_TARGETS)},
    }, 1500),
}
_DESCRIPTIONS = {
    "get_deployment_status": "Read the release and available rollback targets in the mock staging service.",
    "rollback_deployment": "Set the mock staging service to an eligible prior release.",
}


def validate_args(name: str, args: dict) -> list[str]:
    """Return the synthetic tool contract violations, without reading state."""
    if not isinstance(name, str) or name not in TOOLS:
        return ["unknown_tool"]
    if not isinstance(args, dict):
        return ["invalid_args"]
    if args.keys() != TOOLS[name].params.keys():
        return ["unexpected_args"]
    if args["service"] != SERVICE:
        return ["unknown_service"]
    if name == "rollback_deployment":
        release = args["release"]
        if not isinstance(release, str) or len(release) != 2 or not release.isascii() or not release.isdigit():
            return ["invalid_release"]
        if release not in ROLLBACK_TARGETS:
            return ["unknown_release"]
    return []


def tool_schemas() -> list[dict]:
    return [
        {"type": "function", "function": {
            "name": tool.name, "description": _DESCRIPTIONS[tool.name],
            "parameters": {
                "type": "object", "properties": deepcopy(tool.params),
                "required": list(tool.params), "additionalProperties": False,
            },
        }}
        for tool in TOOLS.values()
    ]


def summary(name: str, args: dict, result: dict) -> str:
    """Describe a successful tool's observed result."""
    return f"{result['environment']} {result['service']} is now on release {result['active_release']}"
