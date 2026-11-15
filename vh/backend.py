"""In-memory state and execution for the staging deployment simulation."""

from copy import deepcopy
from hashlib import sha256
import json

from vh.tools import validate_args


class Backend:
    def __init__(self, initial: dict, *, fault: str | None = None):
        if fault not in (None, "timeout_first"):
            raise ValueError("unknown_fault")
        self._state = deepcopy(initial)
        self._timeout_pending = fault == "timeout_first"
        self.audit: list[dict] = []

    @property
    def state(self) -> dict:
        return self.snapshot()

    def snapshot(self) -> dict:
        return deepcopy(self._state)

    def state_hash(self) -> str:
        data = json.dumps(self._state, sort_keys=True, separators=(",", ":"), allow_nan=False)
        return sha256(data.encode("utf-8")).hexdigest()

    def apply(self, tool: str, args: dict) -> dict:
        issues = validate_args(tool, args)
        if issues:
            raise ValueError(issues[0])
        service = args["service"]
        deployment = self._state["services"].get(service)
        if deployment is None or deployment["environment"] != "staging":
            raise ValueError("unknown_service")
        if tool == "get_deployment_status":
            return {"service": service, **deepcopy(deployment)}
        target = args["release"]
        previous = deployment["active_release"]
        if target not in deployment["rollback_targets"]:
            raise ValueError("unknown_release")
        if target == previous:
            raise ValueError("already_active")
        if self._timeout_pending:
            self._timeout_pending = False
            raise TimeoutError("timeout")
        before = self.snapshot()
        deployment["active_release"] = target
        self.audit.append({"tool": tool, "args": deepcopy(args), "before": before, "after": self.snapshot()})
        return {"service": service, "environment": "staging",
                "previous_release": previous, "active_release": target}
