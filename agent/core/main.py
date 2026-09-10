"""WellPaiD Trader - Core Agent

Interactive command-line agent for the WellPaiD Trader platform.
Provides basic commands: hello, help, status, exit.
"""

import sys
from typing import Optional

from .config import get_config
from .router import CommandRouter


class WellPaiDAgent:
    """Main agent class for WellPaiD Trader."""

    def __init__(self, env_file: Optional[str] = None) -> None:
        """Initialize the agent.
        
        Args:
            env_file: Optional path to .env configuration file.
        """
        self.version = "0.3.0"
        self.running = False
        self.config = get_config(env_file)

        # Single source of truth for commands: CommandRouter.
        self.router = CommandRouter()
        self.router.register("hello", self._cmd_hello, "Greet the agent")
        self.router.register("help", self._cmd_help, "Show help message")
        self.router.register("status", self._cmd_status, "Show system status")
        self.router.register("exit", self._cmd_exit, "Exit the agent")
        self.router.register("quit", self._cmd_exit, "Exit the agent")
        
        # Validate trading safety on startup
        is_safe, message = self.config.validate_trading_safety()
        if not is_safe:
            print(f"\n  WARNING: {message}")
            print("  Trading safety controls may be misconfigured.\n")

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
        """Route and execute commands via CommandRouter."""
        success, msg = self.router.execute(command)
        if msg:
            print(msg)
        if not success:
            print("  Type 'help' for available commands.")

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
        print("  exit    - Exit the agent")
        print("  quit    - Exit the agent")
        print("  " + "-" * 40)
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
