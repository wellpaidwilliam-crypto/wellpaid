"""WellPaiD Trader - Core Agent

Interactive personal AI agent: CLI commands plus a tool layer
(calculator, memory, tasks, market data, backtest, paper account)
with conservative natural-language shortcuts.
"""

import re
import shlex
import sys
from typing import Optional

from .config import get_config
from .router import CommandRouter

# Natural-language shortcuts: anchored patterns only, documented in help.
_NATURAL_PATTERNS = (
    ("remember", re.compile(r"^remember(?:\s+that)?\s+(.+)$", re.IGNORECASE)),
    ("remind", re.compile(r"^remind me to\s+(.+)$", re.IGNORECASE)),
    ("price", re.compile(r"^price(?:\s+of)?\s+(\S+)(?:\s+(stock|crypto|forex))?$", re.IGNORECASE)),
)


class WellPaiDAgent:
    """Main agent class for WellPaiD Trader."""

    def __init__(self, env_file: Optional[str] = None, registry=None) -> None:
        """Initialize the agent.

        Args:
            env_file: Optional path to .env configuration file.
            registry: Optional prebuilt ToolRegistry (tests inject stores).
        """
        self.version = "0.7.0"
        self.running = False
        self.config = get_config(env_file)

        # Single source of truth for commands: CommandRouter.
        self.router = CommandRouter()
        self.router.register("hello", self._cmd_hello, "Greet the agent")
        self.router.register("help", self._cmd_help, "Show help message")
        self.router.register("status", self._cmd_status, "Show system status")
        self.router.register("tools", self._cmd_tools, "List agent tools")
        self.router.register("run", self._cmd_run, "Run a tool: run <name> k=v ...")
        self.router.register("exit", self._cmd_exit, "Exit the agent")
        self.router.register("quit", self._cmd_exit, "Exit the agent")

        self.tools = registry if registry is not None else self._build_registry()

        # Validate trading safety on startup
        is_safe, message = self.config.validate_trading_safety()
        if not is_safe:
            print(f"\n  WARNING: {message}")
            print("  Trading safety controls may be misconfigured.\n")

    def _build_registry(self):
        """Assemble the default toolset over live SQLite backends."""
        from ..data.memory import MemoryStore
        from ..risk.engine import RiskEngine
        from ..trading.paper import PaperTradingEngine
        from ..tools.registry import build_default_registry
        from .tasks import TaskManager

        risk = RiskEngine.from_config(self.config)
        paper = PaperTradingEngine(risk_engine=risk)
        return build_default_registry(
            self.config,
            paper,
            risk,
            MemoryStore(),
            TaskManager(),
        )

    def start(self) -> None:
        """Start the interactive agent loop."""
        self.running = True
        print(f"\n{'='*50}")
        print(f"  WellPaiD Trader Agent v{self.version}")
        print(f"  Environment: {self.config.ENVIRONMENT}")
        print(f"{'='*50}")
        print("  Type 'help' for available commands.")
        print(f"{'='*50}\n")

        while self.running:
            try:
                user_input = input("WellPaiD> ").strip()
                if not user_input:
                    continue
                self._process_command(user_input)
            except KeyboardInterrupt:
                print("\n\nExiting WellPaiD Agent...")
                self.running = False
            except EOFError:
                print("\n\nExiting WellPaiD Agent...")
                self.running = False

    def _process_command(self, command: str) -> None:
        """Try natural shortcuts, then route via CommandRouter."""
        if self._try_natural(command):
            return
        success, msg = self.router.execute(command)
        if msg:
            print(msg)
        if not success:
            print("  Type 'help' for available commands.")

    def _show_result(self, result) -> None:
        """Print a ToolResult (message + warnings, never secrets)."""
        print(f"  {result.message}")
        for warning in result.warnings:
            print(f"  ! {warning}")

    def _try_natural(self, command: str) -> bool:
        """Conservative natural-language shortcuts. True if handled."""
        text = command.strip()
        for kind, pattern in _NATURAL_PATTERNS:
            match = pattern.match(text)
            if not match:
                continue
            if kind == "remember":
                self._show_result(
                    self.tools.execute(
                        "memory",
                        {"action": "remember", "content": match.group(1)},
                    )
                )
            elif kind == "remind":
                self._show_result(
                    self.tools.execute(
                        "tasks", {"action": "create", "title": match.group(1)}
                    )
                )
            elif kind == "price":
                symbol, asset = match.group(1), match.group(2) or "stock"
                self._show_result(
                    self.tools.execute(
                        "market_data",
                        {"action": "price", "symbol": symbol, "asset_type": asset},
                    )
                )
            return True
        return False

    @staticmethod
    def _parse_kv(tokens: list) -> dict:
        """Parse k=v tokens (numeric/bool auto-detect, else string)."""
        args = {}
        for token in tokens:
            if "=" not in token:
                continue
            key, _, value = token.partition("=")
            lowered = value.lower()
            if lowered in ("true", "false"):
                args[key] = lowered == "true"
                continue
            try:
                args[key] = int(value)
                continue
            except ValueError:
                pass
            try:
                args[key] = float(value)
                continue
            except ValueError:
                pass
            args[key] = value
        return args

    def _cmd_tools(self, args: list) -> None:
        """List registered agent tools."""
        print("\n  Agent Tools:")
        print("  " + "-" * 40)
        for tool in self.tools.list():
            print(f"  {tool['name']:<15} [{tool['safety']}] {tool['description']}")
        print("  " + "-" * 40)
        print("  Run one with: run <name> key=value ...")
        print()

    def _cmd_run(self, args: list) -> None:
        """Run a registered tool: run <name> [key=value ...]."""
        if not args:
            print("  Usage: run <tool-name> [key=value ...]")
            print("  See available tools with: tools")
            return
        try:
            tokens = shlex.split(" ".join(args))
        except ValueError:
            print("  Could not parse arguments.")
            return
        name, rest = tokens[0], tokens[1:]
        self._show_result(self.tools.execute(name, self._parse_kv(rest)))

    def _cmd_hello(self, args: list) -> None:
        """Respond to hello command."""
        print("  Hello! Welcome to WellPaiD Trader.")
        print("  I'm your personal AI assistant for trading research and automation.")
        print("  Currently in RESEARCH-ONLY mode. No real trading enabled.")

    def _cmd_help(self, args: list) -> None:
        """Show available commands."""
        print("\n  Available Commands:")
        print("  " + "-" * 40)
        print("  hello   - Greet the agent")
        print("  help    - Show this help message")
        print("  status  - Show system status")
        print("  tools   - List agent tools")
        print("  run     - Run a tool: run <name> key=value ...")
        print("  exit    - Exit the agent")
        print("  quit    - Exit the agent")
        print("  " + "-" * 40)
        print("  Shortcuts: remember <fact> | remind me to <task> | price [of] <sym>")
        trading_status = "ENABLED" if self.config.TRADING_ENABLED else "DISABLED"
        print(f"  Trading: {trading_status}")
        print()

    def _cmd_status(self, args: list) -> None:
        """Show system status."""
        config = self.config
        trading_status = "ENABLED" if config.TRADING_ENABLED else "DISABLED"
        paper_status = "ENABLED" if config.PAPER_TRADING_ENABLED else "DISABLED"
        live_status = "ENABLED" if config.LIVE_TRADING_ENABLED else "DISABLED"
        mode = "TRADING" if config.TRADING_ENABLED else "RESEARCH ONLY"
        
        print("\n  System Status:")
        print("  " + "-" * 40)
        print("  Core:             ONLINE")
        print(f"  Trading:          {trading_status}")
        print(f"  Paper Trading:    {paper_status}")
        print(f"  Live Trading:     {live_status}")
        print("  " + "-" * 40)
        print(f"  Mode:             {mode}")
        print(f"  Environment:      {config.ENVIRONMENT}")
        print(f"  Version:          {self.version}")
        print()

    def _cmd_exit(self, args: list) -> None:
        """Exit the agent."""
        print("\n  Shutting down WellPaiD Agent...")
        print("  Goodbye!")
        self.running = False


def main() -> None:
    """Entry point for the WellPaiD Agent."""
    # Check for .env file in current directory
    env_file = ".env"
    agent = WellPaiDAgent(env_file)
    agent.start()


if __name__ == "__main__":
    main()
