"""WellPaiD Trader - Tool registry (V0.4 agent layer).

Single choke point for tool discovery and invocation. Unknown tools
fail safely, tool errors are contained, and execution is logged WITHOUT
arguments (args may carry user data) and WITHOUT results (may carry
quotes/P&L the operator did not ask to persist).
"""

import logging
from typing import Any, Optional

try:
    from agent.tools.base import SafetyClass, Tool, ToolResult
except ImportError:
    from .base import SafetyClass, Tool, ToolResult

logger = logging.getLogger("wellpaid.tools")


class ToolRegistry:
    """Named tool collection with safe execute()."""

    def __init__(self) -> None:
        """Initialize an empty registry."""
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool instance.

        Args:
            tool: Tool with a unique non-empty name.

        Raises:
            ValueError: On empty or duplicate names, or non-Tool objects.
        """
        if not isinstance(tool, Tool):
            raise ValueError("only Tool instances can be registered")
        if not tool.name:
            raise ValueError("tool name must be non-empty")
        if tool.name in self._tools:
            raise ValueError(f"tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        """Look up a tool by name (None if unknown)."""
        return self._tools.get(name)

    def list(self) -> list[dict]:
        """Describe all registered tools (name, description, safety)."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "safety": tool.safety.value,
            }
            for tool in self._tools.values()
        ]

    def execute(self, name: str, args: Optional[dict] = None) -> ToolResult:
        """Run a tool by name. Never raises for unknown/failing tools.

        Trace: REQUEST -> REGISTRY -> TOOL -> RESULT (see logs).
        """
        tool = self._tools.get(name)
        if tool is None:
            logger.warning("unknown tool requested: %s", name)
            return ToolResult(
                success=False,
                message=f"unknown tool: {name}",
                tool=name,
            )
        logger.info("tool start: %s", name)
        result = tool.run(args or {})
        logger.info("tool finish: %s success=%s", name, result.success)
        return result

    def __len__(self) -> int:
        """Number of registered tools."""
        return len(self._tools)


def build_default_registry(
    config: Any = None,
    paper: Any = None,
    risk: Any = None,
    memory: Any = None,
    tasks: Any = None,
    files_root: Any = None,
) -> ToolRegistry:
    """Assemble the standard personal-agent toolset.

    Missing backends are skipped (tool simply absent), except paper:
    the paper tool is always present because the paper engine constructs
    cheaply — but it refuses to submit unless configuration enables it.
    Document tools share one sandbox root (default: current directory).
    """
    try:
        from agent.tools.catalog import (
            BacktestTool,
            CalculatorTool,
            MarketDataTool,
            MemoryTool,
            PaperAccountTool,
            SystemStatusTool,
            TaskManagerTool,
        )
    except ImportError:
        from .catalog import (
            BacktestTool,
            CalculatorTool,
            MarketDataTool,
            MemoryTool,
            PaperAccountTool,
            SystemStatusTool,
            TaskManagerTool,
        )
    try:
        from agent.tools.documents import DxfTool, FilesTool, PdfTool, SheetsTool
    except ImportError:
        from .documents import DxfTool, FilesTool, PdfTool, SheetsTool
    try:
        from agent.tools.web import WebFetchTool
    except ImportError:
        from .web import WebFetchTool
    registry = ToolRegistry()
    registry.register(CalculatorTool())
    registry.register(SystemStatusTool(config))
    if memory is not None:
        registry.register(MemoryTool(memory))
    if tasks is not None:
        registry.register(TaskManagerTool(tasks))
    registry.register(MarketDataTool())
    registry.register(BacktestTool())
    registry.register(PaperAccountTool(config, paper, risk))
    registry.register(FilesTool(files_root))
    registry.register(SheetsTool(files_root))
    registry.register(PdfTool(files_root))
    registry.register(DxfTool(files_root))
    registry.register(WebFetchTool())
    return registry
