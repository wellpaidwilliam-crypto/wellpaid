"""WellPaiD Trader - Tool abstraction (V0.4 agent layer).

A Tool is the ONLY way the agent layer touches capabilities: memory,
tasks, market data, research, paper trading, status. There is no shell
tool, no Python-eval tool, and no generic OS-execution tool — by design
they cannot exist in this registry (see SafetyClass: no such variant).

Every tool declares:
- name / description: for discovery
- safety: what the tool is allowed to touch
- schema: {field: {"type", "required", "description"}}
- execute(args): validated, error-contained, structured result
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger("wellpaid.tools")


class SafetyClass(str, Enum):
    """What a tool is allowed to touch. There is intentionally no
    EXEC capability: arbitrary shell/Python/OS execution is forbidden."""

    READ_ONLY = "read_only"  # no state mutation anywhere
    LOCAL_READ = "local_read"  # reads local user data, no mutation, no network
    LOCAL_WRITE = "local_write"  # local SQLite personal state only
    PAPER_TRADE = "paper_trade"  # simulated money, always risk-gated


@dataclass
class ToolResult:
    """Structured agent↔tool communication (Phase 12 response model)."""

    success: bool
    message: str
    tool: str = ""
    data: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)
    risk: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize for API/CLI transport."""
        return {
            "success": self.success,
            "message": self.message,
            "tool": self.tool,
            "data": self.data,
            "warnings": list(self.warnings),
            "risk": self.risk,
        }


_SCHEMA_TYPES = {
    "string": str,
    "number": (int, float),
    "integer": int,
    "boolean": bool,
}


class Tool(ABC):
    """Base class for all agent tools."""

    name: str = ""
    description: str = ""
    safety: SafetyClass = SafetyClass.READ_ONLY
    schema: dict = {}

    def validate(self, args: Optional[dict]) -> tuple[bool, str]:
        """Strict schema check: required fields, known fields, types.

        Unknown fields are rejected (fail-closed) so callers cannot
        smuggle parameters into a tool.
        """
        if args is None:
            args = {}
        if not isinstance(args, dict):
            return False, "args must be an object"
        for field_name, spec in self.schema.items():
            if spec.get("required") and field_name not in args:
                return False, f"missing required field: {field_name}"
        for field_name, value in args.items():
            if field_name not in self.schema:
                return False, f"unknown field: {field_name}"
            expected = _SCHEMA_TYPES.get(self.schema[field_name].get("type"))
            if expected is None:
                return False, f"bad schema for field: {field_name}"
            if not isinstance(value, expected) or isinstance(value, bool) and expected is not bool and self.schema[field_name].get("type") != "boolean":
                # bool is a subclass of int: reject True/False for number/integer.
                return False, f"field {field_name} must be {self.schema[field_name].get('type')}"
        return True, "ok"

    def run(self, args: Optional[dict] = None) -> ToolResult:
        """Validate then execute, containing all tool errors.

        Never raises for tool failures: validation problems and tool
        exceptions both become failed ToolResults so one bad tool call
        cannot crash the agent.
        """
        valid, reason = self.validate(args or {})
        if not valid:
            return ToolResult(
                success=False, message=reason, tool=self.name
            )
        try:
            result = self.execute(args or {})
        except Exception as exc:  # noqa: BLE001 - contained by contract
            logger.warning("tool=%s failed: %s", self.name, type(exc).__name__)
            return ToolResult(
                success=False,
                message=f"tool {self.name} failed: {type(exc).__name__}",
                tool=self.name,
            )
        if not isinstance(result, ToolResult):
            return ToolResult(
                success=False,
                message=f"tool {self.name} returned invalid result",
                tool=self.name,
            )
        result.tool = self.name
        return result

    @abstractmethod
    def execute(self, args: dict) -> ToolResult:
        """Run the tool. `args` passed validation. May raise (contained)."""
