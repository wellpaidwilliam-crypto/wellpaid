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
        self.equity_curve: list[float] = []
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
        
        The strategy is evaluated incrementally: at each bar, it sees
        only bars up to that point (no lookahead), and any signal it
        emits executes at that bar's close (plus costs). This yields a
        per-bar equity curve for drawdown/Sharpe statistics.
        
        Args:
            strategy: Strategy to test
            data: Historical market data
            
        Returns:
            BacktestResult with performance metrics
        """
        result = BacktestResult()
        bars = data.data
        if not bars:
            result.metadata = self._metadata(strategy, self.initial_capital, 0.0)
            return result
        
        capital = self.initial_capital
        position = 0.0
        total_fees = 0.0
        equity = []
        
        for i in range(len(bars)):
            window = MarketData(
                symbol=data.symbol,
                asset_type=data.asset_type,
                data=bars[: i + 1],
                metadata={},
            )
            try:
                signals = strategy.generate_signals(window)
            except Exception:
                signals = []
            for signal in signals:
                if signal.side == OrderSide.BUY and capital > 0:
                    # Buy at this bar's close
                    fill = self._fill_price(bars[i].close, OrderSide.BUY)
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
                        "timestamp": bars[i].timestamp.isoformat(),
                    })
                elif signal.side == OrderSide.SELL and position > 0:
                    # Sell at this bar's close
                    fill = self._fill_price(bars[i].close, OrderSide.SELL)
                    proceeds = position * fill
                    fee = proceeds * self.fee_bps / 10_000.0
                    total_fees += fee
                    capital = proceeds - fee
                    result.trades.append({
                        "type": "sell",
                        "price": fill,
                        "shares": position,
                        "fee": fee,
                        "timestamp": bars[i].timestamp.isoformat(),
                    })
                    position = 0.0
            equity.append(capital + position * bars[i].close)
        
        result.equity_curve = equity
        final_value = equity[-1] if equity else self.initial_capital
        result.total_return = (final_value - self.initial_capital) / self.initial_capital
        result.max_drawdown = self._max_drawdown(equity)
        result.sharpe_ratio = self._sharpe(equity)
        
        # Win rate
        if result.trades:
            wins = len([t for t in result.trades if t.get("type") == "sell"])
            result.win_rate = wins / len(result.trades) if result.trades else 0
        
        result.metadata = self._metadata(
            strategy, final_value, total_fees, bars=len(bars),
            total_trades=len(result.trades),
        )
        
        return result

    def walk_forward(
        self,
        strategy: StrategyBase,
        data: MarketData,
        folds: int = 3,
    ) -> dict[str, Any]:
        """Run the strategy on chronological folds for regime robustness.

        This is NOT optimization: no parameters are tuned. The same
        strategy runs on each contiguous fold so inconsistent results
        across folds warn against overfitting to one regime.

        Args:
            strategy: Strategy to test (same instance every fold).
            data: Full historical market data.
            folds: Number of contiguous folds (2..5).

        Returns:
            Dict with per-fold returns/trades plus a consistency note.
        """
        if not 2 <= folds <= 5:
            raise ValueError("folds must be 2..5")
        bars = data.data
        if len(bars) < folds:
            raise ValueError("not enough bars for walk-forward folds")
        chunk = len(bars) // folds
        fold_results = []
        for f in range(folds):
            start = f * chunk
            end = start + chunk if f < folds - 1 else len(bars)
            window = MarketData(
                symbol=data.symbol,
                asset_type=data.asset_type,
                data=bars[start:end],
                metadata={},
            )
            res = self.run(strategy, window)
            fold_results.append(
                {
                    "fold": f + 1,
                    "bars": end - start,
                    "total_return": res.total_return,
                    "max_drawdown": res.max_drawdown,
                    "trades": len(res.trades),
                }
            )
        returns = [f["total_return"] for f in fold_results]
        consistent = (
            all(r >= 0 for r in returns) or all(r < 0 for r in returns)
        )
        return {
            "folds": fold_results,
            "consistent_sign": consistent,
            "note": (
                "Same strategy, no tuning: agreement across folds suggests "
                "regime robustness; disagreement warns of overfitting. "
                "Still historical, never predictive."
            ),
        }

    @staticmethod
    def _max_drawdown(equity: list[float]) -> float:
        """Peak-to-trough decline as a fraction of the peak."""
        peak = float("-inf")
        worst = 0.0
        for value in equity:
            if value > peak:
                peak = value
            if peak > 0:
                worst = min(worst, (value - peak) / peak)
        return abs(worst)

    @staticmethod
    def _sharpe(equity: list[float]) -> float:
        """Mean/std of per-bar simple returns (risk-free = 0).

        Returns 0.0 when undefined (fewer than 2 bars or zero variance)
        rather than inventing a number.
        """
        if len(equity) < 2:
            return 0.0
        rets = [
            (equity[i] - equity[i - 1]) / equity[i - 1]
            for i in range(1, len(equity))
            if equity[i - 1] != 0
        ]
        if len(rets) < 2:
            return 0.0
        mean = sum(rets) / len(rets)
        var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
        if var <= 0:
            return 0.0
        return mean / (var ** 0.5)

    def _metadata(
        self,
        strategy: StrategyBase,
        final_value: float,
        total_fees: float,
        bars: int = 0,
        total_trades: int = 0,
    ) -> dict[str, Any]:
        """Standard result metadata incl. the honesty disclaimer."""
        return {
            "strategy": strategy.get_name(),
            "initial_capital": self.initial_capital,
            "final_value": final_value,
            "total_trades": total_trades,
            "total_fees": total_fees,
            "fee_bps": self.fee_bps,
            "slippage_bps": self.slippage_bps,
            "bars": bars,
            "disclaimer": "Past performance does not indicate future results",
        }
