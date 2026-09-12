"""WellPaiD Trader - Trading Research Foundation

RESEARCH ONLY - No real trading, no broker connections, no order execution.
This module provides the foundation for market data analysis and strategy research.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Any
from enum import Enum


class AssetType(Enum):
    """Asset types for trading research."""
    STOCK = "stock"
    CRYPTO = "crypto"
    FOREX = "forex"
    COMMODITY = "commodity"
    INDEX = "index"


class OrderSide(Enum):
    """Order side for research simulation."""
    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    """Order types for research simulation."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


@dataclass
class OHLCV:
    """Open, High, Low, Close, Volume data."""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class MarketData:
    """Market data for a single asset."""
    symbol: str
    asset_type: AssetType
    data: list[OHLCV]
    metadata: dict[str, Any]


@dataclass
class Signal:
    """Trading signal for research."""
    symbol: str
    side: OrderSide
    strength: float  # 0.0 to 1.0
    timestamp: datetime
    metadata: dict[str, Any]


class DataProvider(ABC):
    """Abstract base class for data providers."""
    
    @abstractmethod
    def get_historical_data(
        self,
        symbol: str,
        asset_type: AssetType,
        start_date: datetime,
        end_date: datetime,
    ) -> Optional[MarketData]:
        """Get historical market data.
        
        Args:
            symbol: Asset symbol
            asset_type: Type of asset
            start_date: Start date for data
            end_date: End date for data
            
        Returns:
            MarketData or None if unavailable
        """
        pass
    
    @abstractmethod
    def get_current_price(self, symbol: str, asset_type: AssetType) -> Optional[float]:
        """Get current price for an asset.
        
        Args:
            symbol: Asset symbol
            asset_type: Type of asset
            
        Returns:
            Current price or None if unavailable
        """
        pass


class MockDataProvider(DataProvider):
    """Mock data provider for testing and development.
    
    Provides sample market data without connecting to real exchanges.
    Pass a seed for deterministic, reproducible series.
    """
    
    def __init__(self, seed: Optional[int] = None) -> None:
        """Initialize mock provider.
        
        Args:
            seed: Random seed for reproducible data (None = non-deterministic).
        """
        self.seed = seed

    def get_historical_data(
        self,
        symbol: str,
        asset_type: AssetType,
        start_date: datetime,
        end_date: datetime,
    ) -> Optional[MarketData]:
        """Generate mock historical data."""
        import random

        rng = random.Random(self.seed)
        
        # Generate sample OHLCV data
        data = []
        current_date = start_date
        base_price = 100.0
        
        while current_date <= end_date:
            # Random walk for price
            change = rng.uniform(-0.05, 0.05)
            close = base_price * (1 + change)
            high = close * (1 + rng.uniform(0, 0.02))
            low = close * (1 - rng.uniform(0, 0.02))
            volume = rng.uniform(1000, 10000)
            
            data.append(OHLCV(
                timestamp=current_date,
                open=base_price,
                high=high,
                low=low,
                close=close,
                volume=volume,
            ))
            
            base_price = close
            current_date = current_date + timedelta(days=1)
        
        return MarketData(
            symbol=symbol,
            asset_type=asset_type,
            data=data,
            metadata={"source": "mock", "generated": datetime.now().isoformat()},
        )
    
    def get_current_price(self, symbol: str, asset_type: AssetType) -> Optional[float]:
        """Get mock current price."""
        return 100.0  # Mock price


class IndicatorEngine:
    """Calculate technical indicators from market data."""
    
    @staticmethod
    def sma(data: list[OHLCV], period: int) -> list[float]:
        """Calculate Simple Moving Average.
        
        Args:
            data: List of OHLCV data
            period: SMA period
            
        Returns:
            List of SMA values
        """
        if len(data) < period:
            return []
        
        closes = [d.close for d in data]
        sma_values = []
        
        for i in range(period - 1, len(closes)):
            window = closes[i - period + 1:i + 1]
            sma_values.append(sum(window) / period)
        
        return sma_values
    
    @staticmethod
    def ema(data: list[OHLCV], period: int) -> list[float]:
        """Calculate Exponential Moving Average.
        
        Args:
            data: List of OHLCV data
            period: EMA period
            
        Returns:
            List of EMA values
        """
        if len(data) < period:
            return []
        
        closes = [d.close for d in data]
        multiplier = 2 / (period + 1)
        
        # Start with SMA
        ema_values = [sum(closes[:period]) / period]
        
        for i in range(period, len(closes)):
            ema = (closes[i] - ema_values[-1]) * multiplier + ema_values[-1]
            ema_values.append(ema)
        
        return ema_values
    
    @staticmethod
    def rsi(data: list[OHLCV], period: int = 14) -> list[float]:
        """Calculate Relative Strength Index.
        
        Args:
            data: List of OHLCV data
            period: RSI period
            
        Returns:
            List of RSI values
        """
        if len(data) < period + 1:
            return []
        
        closes = [d.close for d in data]
        changes = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        
        gains = [max(c, 0) for c in changes]
        losses = [abs(min(c, 0)) for c in changes]
        
        rsi_values = []
        
        for i in range(period, len(changes)):
            avg_gain = sum(gains[i-period:i]) / period
            avg_loss = sum(losses[i-period:i]) / period
            
            if avg_loss == 0:
                rsi = 100.0
            else:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))
            
            rsi_values.append(rsi)
        
        return rsi_values


class StrategyBase(ABC):
    """Abstract base class for trading strategies."""
    
    @abstractmethod
    def generate_signals(self, data: MarketData) -> list[Signal]:
        """Generate trading signals from market data.
        
        Args:
            data: Market data
            
        Returns:
            List of trading signals
        """
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """Get strategy name."""
        pass


class SMAcrossoverStrategy(StrategyBase):
    """Simple Moving Average Crossover Strategy.
    
    Research only - not intended for live trading.
    """
    
    def __init__(self, short_period: int = 20, long_period: int = 50) -> None:
        """Initialize strategy.
        
        Args:
            short_period: Short SMA period
            long_period: Long SMA period
        """
        self.short_period = short_period
        self.long_period = long_period
    
    def get_name(self) -> str:
        """Get strategy name."""
        return f"SMA Crossover ({self.short_period}/{self.long_period})"
    
    def generate_signals(self, data: MarketData) -> list[Signal]:
        """Generate signals based on SMA crossover."""
        if len(data.data) < self.long_period:
            return []
        
        short_sma = IndicatorEngine.sma(data.data, self.short_period)
        long_sma = IndicatorEngine.sma(data.data, self.long_period)
        
        if not short_sma or not long_sma:
            return []
        
        signals = []
        
        # Compare SMAs (simplified)
        if short_sma[-1] > long_sma[-1] and short_sma[-2] <= long_sma[-2]:
            signals.append(Signal(
                symbol=data.symbol,
                side=OrderSide.BUY,
                strength=0.7,
                timestamp=data.data[-1].timestamp,
                metadata={"strategy": self.get_name(), "reason": "SMA crossover up"},
            ))
        elif short_sma[-1] < long_sma[-1] and short_sma[-2] >= long_sma[-2]:
            signals.append(Signal(
                symbol=data.symbol,
                side=OrderSide.SELL,
                strength=0.7,
                timestamp=data.data[-1].timestamp,
                metadata={"strategy": self.get_name(), "reason": "SMA crossover down"},
            ))
        
        return signals


class BacktestResult:
    """Results from a backtest run."""
    
    def __init__(self) -> None:
        """Initialize backtest result."""
        self.trades: list[dict] = []
        self.total_return: float = 0.0
        self.sharpe_ratio: float = 0.0
        self.max_drawdown: float = 0.0
        self.win_rate: float = 0.0
        self.metadata: dict[str, Any] = {}


class Backtester:
    """Backtesting engine for research.
    
    Simulates strategy performance on historical data.
    For research purposes only - past performance does not indicate future results.
    """
    
    def __init__(
        self,
        initial_capital: float = 10000.0,
        fee_bps: float = 0.0,
        slippage_bps: float = 0.0,
    ) -> None:
        """Initialize backtester.
        
        Args:
            initial_capital: Starting capital for simulation
            fee_bps: Commission per fill in basis points of notional
                (e.g. 10.0 = 0.10% per side).
            slippage_bps: Adverse price move per fill in basis points
                (buys fill higher, sells fill lower).
        """
        if initial_capital <= 0:
            raise ValueError("initial_capital must be positive")
        if fee_bps < 0 or slippage_bps < 0:
            raise ValueError("fee_bps and slippage_bps must be non-negative")
        self.initial_capital = initial_capital
        self.fee_bps = fee_bps
        self.slippage_bps = slippage_bps

    def _fill_price(self, quoted: float, side: OrderSide) -> float:
        """Apply slippage: buys worse (higher), sells worse (lower)."""
        slip = quoted * self.slippage_bps / 10_000.0
        return quoted + slip if side == OrderSide.BUY else quoted - slip
    
    def run(
        self,
        strategy: StrategyBase,
        data: MarketData,
    ) -> BacktestResult:
        """Run backtest on historical data.
        
        Args:
            strategy: Strategy to test
            data: Historical market data
            
        Returns:
            BacktestResult with performance metrics
        """
        signals = strategy.generate_signals(data)
        result = BacktestResult()
        
        # Simplified backtest logic (close-price fills + costs)
        capital = self.initial_capital
        position = 0.0
        total_fees = 0.0
        
        for signal in signals:
            if signal.side == OrderSide.BUY and capital > 0:
                # Buy
                fill = self._fill_price(data.data[-1].close, OrderSide.BUY)
                fee = capital * self.fee_bps / 10_000.0
                total_fees += fee
                shares = (capital - fee) / fill
                position = shares
                capital = 0.0
                result.trades.append({
                    "type": "buy",
                    "price": fill,
                    "shares": shares,
                    "fee": fee,
                    "timestamp": signal.timestamp.isoformat(),
                })
            elif signal.side == OrderSide.SELL and position > 0:
                # Sell
                fill = self._fill_price(data.data[-1].close, OrderSide.SELL)
                proceeds = position * fill
                fee = proceeds * self.fee_bps / 10_000.0
                total_fees += fee
                capital = proceeds - fee
                result.trades.append({
                    "type": "sell",
                    "price": fill,
                    "shares": position,
                    "fee": fee,
                    "timestamp": signal.timestamp.isoformat(),
                })
                position = 0.0
        
        # Calculate final value
        final_value = capital + (position * data.data[-1].close if data.data else 0)
        result.total_return = (final_value - self.initial_capital) / self.initial_capital
        
        # Win rate
        if result.trades:
            wins = len([t for t in result.trades if t.get("type") == "sell"])
            result.win_rate = wins / len(result.trades) if result.trades else 0
        
        result.metadata = {
            "strategy": strategy.get_name(),
            "initial_capital": self.initial_capital,
            "final_value": final_value,
            "total_trades": len(result.trades),
            "total_fees": total_fees,
            "fee_bps": self.fee_bps,
            "slippage_bps": self.slippage_bps,
            "disclaimer": "Past performance does not indicate future results",
        }
        
        return result
