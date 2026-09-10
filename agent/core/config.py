"""WellPaiD Trader - Configuration Module

Safe configuration management with environment variables.
All trading controls default to DISABLED.
"""

import os
from pathlib import Path
from typing import Optional


class Config:
    """Configuration manager for WellPaiD Trader.
    
    All trading-related settings default to False/disabled
    to prevent accidental live trading.
    """
    
    def __init__(self, env_file: Optional[str] = None) -> None:
        """Initialize configuration.
        
        Args:
            env_file: Optional path to .env file. If None, only uses environment variables.
        """
        if env_file:
            self._load_env_file(env_file)
        
        # Application settings
        self.APP_NAME: str = os.getenv("APP_NAME", "WellPaiD Trader")
        self.ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
        self.LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
        
        # Trading safety controls - ALL DEFAULT TO FALSE
        self.TRADING_ENABLED: bool = self._parse_bool(os.getenv("TRADING_ENABLED", "false"))
        self.PAPER_TRADING_ENABLED: bool = self._parse_bool(os.getenv("PAPER_TRADING_ENABLED", "false"))
        self.LIVE_TRADING_ENABLED: bool = self._parse_bool(os.getenv("LIVE_TRADING_ENABLED", "false"))
        
        # API Keys
        self.EXCHANGE_API_KEY: str = os.getenv("EXCHANGE_API_KEY", "")
        self.EXCHANGE_API_SECRET: str = os.getenv("EXCHANGE_API_SECRET", "")
        
        # Database
        self.DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///wellpaid.db")
        
        # Risk Engine Defaults
        self.MAX_POSITION_SIZE: int = int(os.getenv("MAX_POSITION_SIZE", "1000"))
        self.MAX_DAILY_LOSS: int = int(os.getenv("MAX_DAILY_LOSS", "500"))
        self.MAX_DRAWDOWN: float = float(os.getenv("MAX_DRAWDOWN", "0.1"))
        self.MAX_TRADES_PER_DAY: int = int(os.getenv("MAX_TRADES_PER_DAY", "10"))
        self.MAX_NOTIONAL_PER_TRADE: float = float(
            os.getenv("MAX_NOTIONAL_PER_TRADE", "100000")
        )
        self.MAX_TOTAL_NOTIONAL_EXPOSURE: float = float(
            os.getenv("MAX_TOTAL_NOTIONAL_EXPOSURE", "500000")
        )
    
    def _parse_bool(self, value: str) -> bool:
        """Parse boolean value from string."""
        return value.lower() in ("true", "1", "yes", "on")
    
    def _load_env_file(self, path: str) -> None:
        """Load environment variables from .env file."""
        env_path = Path(path)
        if not env_path.exists():
            return
        
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, _, value = line.partition("=")
                    key = key.strip()
                    # Strip optional `export ` prefix and surrounding quotes.
                    if key.lower().startswith("export "):
                        key = key[7:].strip()
                    value = value.strip()
                    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                        value = value[1:-1]
                    if key and key not in os.environ:
                        os.environ[key] = value
    
    def can_trade(self) -> bool:
        """Check if trading is enabled at all."""
        return self.TRADING_ENABLED
    
    def can_paper_trade(self) -> bool:
        """Check if paper trading is enabled."""
        return self.PAPER_TRADING_ENABLED and self.TRADING_ENABLED
    
    def can_live_trade(self) -> bool:
        """Check if live trading is enabled."""
        return self.LIVE_TRADING_ENABLED and self.TRADING_ENABLED
    
    def validate_trading_safety(self) -> tuple[bool, str]:
        """Validate that trading safety controls are properly set.

        Fail-closed: any enabled sub-switch without the master switch
        is a misconfiguration and returns False.

        Returns:
            Tuple of (is_safe, message)
        """
        if self.LIVE_TRADING_ENABLED and not self.TRADING_ENABLED:
            return False, "CRITICAL: Live trading enabled without main trading switch!"
        
        if self.PAPER_TRADING_ENABLED and not self.TRADING_ENABLED:
            return False, "CRITICAL: Paper trading enabled without main trading switch!"
        
        return True, "Trading safety controls OK"
    
    def status(self) -> dict:
        """Return current configuration status."""
        return {
            "app_name": self.APP_NAME,
            "environment": self.ENVIRONMENT,
            "trading_enabled": self.TRADING_ENABLED,
            "paper_trading_enabled": self.PAPER_TRADING_ENABLED,
            "live_trading_enabled": self.LIVE_TRADING_ENABLED,
            "has_api_key": bool(self.EXCHANGE_API_KEY),
        }
    
    def __repr__(self) -> str:
        """String representation without secrets."""
        safe_status = self.validate_trading_safety()
        return (
            f"Config(app={self.APP_NAME}, env={self.ENVIRONMENT}, "
            f"trading={self.TRADING_ENABLED}, "
            f"paper={self.PAPER_TRADING_ENABLED}, "
            f"live={self.LIVE_TRADING_ENABLED}, "
            f"safe={safe_status[0]})"
        )


# Global config instance
_config: Optional[Config] = None


def get_config(env_file: Optional[str] = None) -> Config:
    """Get or create global configuration instance.
    
    Args:
        env_file: Optional path to .env file.
        
    Returns:
        Config instance
    """
    global _config
    if _config is None:
        _config = Config(env_file)
    return _config


def reset_config() -> None:
    """Reset global configuration (useful for testing)."""
    global _config
    _config = None
