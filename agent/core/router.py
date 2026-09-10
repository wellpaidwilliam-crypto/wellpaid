"""WellPaiD Trader - Command Router

Modular command routing system for the agent.
Supports registration of commands with handlers.
"""

from typing import Callable, Optional, Any
from dataclasses import dataclass


@dataclass
class Command:
    """Represents a registered command."""
    name: str
    handler: Callable
    description: str
    usage: Optional[str] = None


class CommandRouter:
    """Command routing system for the WellPaiD Agent.
    
    Supports registration of commands with handlers and
    provides safe execution with error handling.
    """
    
    def __init__(self) -> None:
        """Initialize the command router."""
        self.commands: dict[str, Command] = {}
    
    def register(
        self,
        name: str,
        handler: Callable,
        description: str,
        usage: Optional[str] = None,
    ) -> None:
        """Register a new command.
        
        Args:
            name: Command name (will be lowercased)
            handler: Function to call when command is executed
            description: Help text for the command
            usage: Optional usage string
        """
        self.commands[name.lower()] = Command(
            name=name.lower(),
            handler=handler,
            description=description,
            usage=usage,
        )
    
    def unregister(self, name: str) -> bool:
        """Unregister a command.
        
        Args:
            name: Command name to remove
            
        Returns:
            True if command was removed, False if not found
        """
        if name.lower() in self.commands:
            del self.commands[name.lower()]
            return True
        return False
    
    def execute(self, command_str: str, **kwargs: Any) -> tuple[bool, str]:
        """Execute a command string.
        
        Args:
            command_str: Command string (e.g., "help" or "status --verbose")
            **kwargs: Additional arguments to pass to handler
            
        Returns:
            Tuple of (success, message)
        """
        parts = command_str.strip().split()
        if not parts:
            return False, "No command provided"
        
        cmd_name = parts[0].lower()
        args = parts[1:]
        
        command = self.commands.get(cmd_name)
        if not command:
            return False, f"Unknown command: '{cmd_name}'. Type 'help' for available commands."
        
        try:
            result = command.handler(args, **kwargs)
            if result is None:
                return True, ""
            return True, str(result)
        except Exception as e:
            return False, f"Error executing '{cmd_name}': {str(e)}"
    
    def get_help(self) -> str:
        """Get formatted help text for all commands.
        
        Returns:
            Formatted help string
        """
        if not self.commands:
            return "No commands registered."
        
        lines = ["Available Commands:", "-" * 40]
        
        # Sort commands alphabetically
        for name in sorted(self.commands.keys()):
            cmd = self.commands[name]
            usage = cmd.usage if cmd.usage else ""
            lines.append(f"  {name:<12} {cmd.usage if usage else ''}")
            lines.append(f"              {cmd.description}")
        
        lines.append("-" * 40)
        return "\n".join(lines)
    
    def has_command(self, name: str) -> bool:
        """Check if a command exists.
        
        Args:
            name: Command name to check
            
        Returns:
            True if command exists
        """
        return name.lower() in self.commands
    
    def list_commands(self) -> list[str]:
        """Get list of registered command names.
        
        Returns:
            List of command names
        """
        return sorted(self.commands.keys())
    
    def __repr__(self) -> str:
        """String representation."""
        return f"CommandRouter(commands={len(self.commands)})"
