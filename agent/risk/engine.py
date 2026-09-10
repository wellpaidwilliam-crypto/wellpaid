"""WellPaiD Trader - Risk Engine

Risk management system that can approve or reject trade decisions.
The risk engine has authority to veto any trade, including those proposed by the AI.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Any
from enum import Enum


class RiskDecision(Enum):
    """Risk engine decision."""
    APPROVED = "approved"
    REJECTED = "rejected"
    CONDITIONAL = "conditional"


@dataclass
class RiskCheck:
    """Result of a risk check."""
    decision: RiskDecision
    reason: str
    violations: list[str]
    metadata: dict[str, Any]


@dataclass
class TradeProposal:
    """Trade proposal for risk evaluation."""
    symbol: str
    side: str  # "buy" or "sell"
    quantity: float
    price: float
    order_type: str  # "market", "limit", etc.
    timestamp: datetime
    metadata: dict[str, Any]


class RiskEngine:
    """Risk management engine with authority to approve/reject trades.
    
    The risk engine has absolute authority over trade execution.
    Even if the AI proposes a trade, the risk engine can veto it.
    """
    def __init__(
        self,
        max_position_size: float = 1000.0,
        max_daily_loss: float = 500.0,
        max_drawdown: float = 0.1,
        max_trades_per_day: int = 10,
        max_total_exposure: float = 10000.0,
        max_notional_per_trade: float = 100000.0,
        max_total_notional_exposure: float = 500000.0,
    ) -> None:
        """Initialize risk engine.
        
        Args:
            max_position_size: Maximum size per position
            max_daily_loss: Maximum loss per day
            max_drawdown: Maximum drawdown percentage (0.0 to 1.0)
            max_trades_per_day: Maximum number of trades per day
            max_total_exposure: Maximum total exposure
            max_notional_per_trade: Maximum notional (qty x price) per trade
            max_total_notional_exposure: Maximum portfolio notional exposure
        """
        self.max_position_size = max_position_size
        self.max_daily_loss = max_daily_loss
        self.max_drawdown = max_drawdown
        self.max_trades_per_day = max_trades_per_day
        self.max_total_exposure = max_total_exposure
        self.max_notional_per_trade = max_notional_per_trade
        self.max_total_notional_exposure = max_total_notional_exposure
        
        # Tracking
        self.daily_trades: list[datetime] = []
        self.daily_pnl: float = 0.0
        self.peak_value: float = 0.0
        self.current_value: float = 0.0
        self.positions: dict[str, float] = {}
        # Track last price per symbol for notional exposure accounting.
        self.position_prices: dict[str, float] = {}

    @classmethod
    def from_config(cls, config) -> "RiskEngine":
        """Build a risk engine from app configuration.

        Reads MAX_POSITION_SIZE, MAX_DAILY_LOSS, MAX_DRAWDOWN and
        MAX_TRADES_PER_DAY (plus optional MAX_NOTIONAL_PER_TRADE and
        MAX_TOTAL_NOTIONAL_EXPOSURE) so the env-backed safety knobs in
        `.env` actually take effect. Missing optional attrs fall back
        to constructor defaults.

        Args:
            config: An `agent.core.config.Config` instance.
        """
        return cls(
            max_position_size=getattr(config, "MAX_POSITION_SIZE", 1000),
            max_daily_loss=getattr(config, "MAX_DAILY_LOSS", 500),
            max_drawdown=getattr(config, "MAX_DRAWDOWN", 0.1),
            max_trades_per_day=getattr(config, "MAX_TRADES_PER_DAY", 10),
            max_notional_per_trade=getattr(
                config, "MAX_NOTIONAL_PER_TRADE", 100000.0
            ),
            max_total_notional_exposure=getattr(
                config, "MAX_TOTAL_NOTIONAL_EXPOSURE", 500000.0
            ),
        )
    
    def evaluate(self, proposal: TradeProposal) -> RiskCheck:
        """Evaluate a trade proposal against risk limits.
        
        Args:
            proposal: Trade proposal to evaluate
            
        Returns:
            RiskCheck with decision and reason
        """
        violations = []

        # Check 0: Proposal well-formedness (fail-closed on garbage input)
        if proposal.side not in ("buy", "sell"):
            violations.append(
                f"Invalid order side {proposal.side!r}: must be 'buy' or 'sell'"
            )
        if not isinstance(proposal.quantity, (int, float)) or proposal.quantity <= 0:
            violations.append(
                f"Invalid quantity {proposal.quantity!r}: must be positive"
            )
        if proposal.price is None or proposal.price < 0:
            violations.append(
                f"Invalid price {proposal.price!r}: must be non-negative"
            )
        if violations:
            return RiskCheck(
                decision=RiskDecision.REJECTED,
                reason="Trade rejected: malformed proposal",
                violations=violations,
                metadata={
                    "proposal": {
                        "symbol": proposal.symbol,
                        "side": proposal.side,
                        "quantity": proposal.quantity,
                    },
                    "timestamp": datetime.now().isoformat(),
                },
            )
        
        # Check 1: Position size
        if proposal.quantity > self.max_position_size:
            violations.append(
                f"Position size {proposal.quantity} exceeds max {self.max_position_size}"
            )
        
        # Check 2: Daily trade count
        self._cleanup_old_trades()
        if len(self.daily_trades) >= self.max_trades_per_day:
            violations.append(
                f"Daily trade count {len(self.daily_trades)} exceeds max {self.max_trades_per_day}"
            )
        
        # Check 3: Daily loss limit
        if self.daily_pnl < -self.max_daily_loss:
            violations.append(
                f"Daily loss {abs(self.daily_pnl)} exceeds max {self.max_daily_loss}"
            )
        
        # Check 4: Drawdown
        if self.peak_value > 0:
            drawdown = (self.peak_value - self.current_value) / self.peak_value
            if drawdown > self.max_drawdown:
                violations.append(
                    f"Drawdown {drawdown:.2%} exceeds max {self.max_drawdown:.2%}"
                )
        
        # Check 5: Total exposure
        total_exposure = sum(abs(v) for v in self.positions.values())
        if total_exposure + proposal.quantity > self.max_total_exposure:
            violations.append(
                f"Total exposure {total_exposure + proposal.quantity} exceeds max {self.max_total_exposure}"
            )

        # Check 6: Per-trade notional (quantity x price)
        notional = proposal.quantity * proposal.price
        if notional > self.max_notional_per_trade:
            violations.append(
                f"Trade notional {notional} exceeds max {self.max_notional_per_trade}"
            )

        # Check 7: Total notional exposure across tracked positions
        total_notional = sum(
            abs(qty) * self.position_prices.get(sym, 0.0)
            for sym, qty in self.positions.items()
        )
        if total_notional + notional > self.max_total_notional_exposure:
            violations.append(
                f"Total notional exposure {total_notional + notional} exceeds max "
                f"{self.max_total_notional_exposure}"
            )
        
        # Make decision
        if violations:
            return RiskCheck(
                decision=RiskDecision.REJECTED,
                reason=f"Trade rejected: {len(violations)} violation(s)",
                violations=violations,
                metadata={
                    "proposal": {
                        "symbol": proposal.symbol,
                        "side": proposal.side,
                        "quantity": proposal.quantity,
                    },
                    "timestamp": datetime.now().isoformat(),
                },
            )
        
        return RiskCheck(
            decision=RiskDecision.APPROVED,
            reason="Trade approved",
            violations=[],
            metadata={
                "proposal": {
                    "symbol": proposal.symbol,
                    "side": proposal.side,
                    "quantity": proposal.quantity,
                },
                "timestamp": datetime.now().isoformat(),
            },
        )
    
    def record_trade(self, proposal: TradeProposal) -> None:
        """Record a trade for tracking purposes.
        
        Args:
            proposal: Executed trade proposal
        """
        self.daily_trades.append(datetime.now())
        
        # Update positions
        current = self.positions.get(proposal.symbol, 0.0)
        if proposal.side == "buy":
            self.positions[proposal.symbol] = current + proposal.quantity
        else:
            self.positions[proposal.symbol] = current - proposal.quantity
        # Track last price for notional exposure accounting.
        if proposal.price is not None and proposal.price > 0:
            self.position_prices[proposal.symbol] = proposal.price
    
    def update_pnl(self, pnl: float) -> None:
        """Update daily P&L.
        
        Args:
            pnl: Profit/loss amount
        """
        self.daily_pnl += pnl
        self.current_value += pnl
        if self.current_value > self.peak_value:
            self.peak_value = self.current_value
    
    def _cleanup_old_trades(self) -> None:
        """Remove trades older than 24 hours."""
        cutoff = datetime.now() - timedelta(hours=24)
        self.daily_trades = [t for t in self.daily_trades if t > cutoff]
    
    def reset_daily(self) -> None:
        """Reset daily counters."""
        self.daily_trades = []
        self.daily_pnl = 0.0
    
    def get_status(self) -> dict:
        """Get current risk engine status."""
        self._cleanup_old_trades()
        total_exposure = sum(abs(v) for v in self.positions.values())
        total_notional = sum(
            abs(qty) * self.position_prices.get(sym, 0.0)
            for sym, qty in self.positions.items()
        )
        drawdown = 0.0
        if self.peak_value > 0:
            drawdown = (self.peak_value - self.current_value) / self.peak_value
        
        return {
            "daily_trades": len(self.daily_trades),
            "max_trades_per_day": self.max_trades_per_day,
            "daily_pnl": self.daily_pnl,
            "max_daily_loss": self.max_daily_loss,
            "current_drawdown": drawdown,
            "max_drawdown": self.max_drawdown,
            "total_exposure": total_exposure,
            "max_total_exposure": self.max_total_exposure,
            "total_notional_exposure": total_notional,
            "max_total_notional_exposure": self.max_total_notional_exposure,
            "max_notional_per_trade": self.max_notional_per_trade,
            "positions": dict(self.positions),
        }
