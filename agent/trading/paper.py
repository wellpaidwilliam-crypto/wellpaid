"""WellPaiD Trader - Paper Trading Engine

Simulated trading engine using fake money only.
Never connects to real brokers or exchanges.
Clearly identifies itself as PAPER TRADING.
"""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass
from enum import Enum

try:
    from agent.risk.engine import RiskEngine, TradeProposal, RiskDecision
except ImportError:  # support `python -m agent.core.main` relative layout
    from ..risk.engine import RiskEngine, TradeProposal, RiskDecision

try:
    from agent.core.storage import sqlite_db
except ImportError:
    from ..core.storage import sqlite_db


class OrderStatus(Enum):
    """Order status values."""
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass
class PaperOrder:
    """Represents a paper trading order."""
    id: str
    symbol: str
    side: str  # "buy" or "sell"
    quantity: float
    order_type: str  # "market" or "limit"
    price: Optional[float]
    status: OrderStatus
    created_at: str
    filled_at: Optional[str]
    filled_price: Optional[float]
    filled_quantity: float
    metadata: dict[str, Any]


@dataclass
class PaperPosition:
    """Represents a paper trading position."""
    symbol: str
    quantity: float
    avg_entry_price: float
    current_price: float
    unrealized_pnl: float
    realized_pnl: float


class PaperTradingEngine:
    """Paper trading engine using simulated money.
    
    This engine NEVER connects to real brokers or exchanges.
    All trades are simulated with fake money.
    Clearly identifies itself as PAPER TRADING.

    When a RiskEngine is attached, every order is evaluated BEFORE
    execution. A REJECTED decision prevents any fill, balance change,
    or position update — the risk engine has absolute veto authority.
    """
    
    def __init__(
        self,
        initial_balance: float = 10000.0,
        storage_path: str = "agent/data/paper_trading.db",
        risk_engine: Optional[RiskEngine] = None,
    ) -> None:
        """Initialize paper trading engine.

        State is persisted in SQLite (write-through on every mutation).
        A legacy V1 JSON file at the same path is moved aside to
        `<name>.bak`, never parsed.

        Args:
            initial_balance: Starting balance for paper trading
            storage_path: Path to SQLite database file
            risk_engine: Optional RiskEngine with veto authority.
                If None, orders execute without a risk check
                (backward compatible with existing usage/tests).
        """
        self.initial_balance = initial_balance
        self.storage_path = Path(storage_path)
        self.risk_engine = risk_engine

        # Account state
        self.balance: float = initial_balance
        self.positions: dict[str, PaperPosition] = {}
        self.orders: list[PaperOrder] = []
        self.trade_history: list[dict] = []

        self._init_db()

    def _connect(self):
        """Open a short-lived, auto-closing connection to the store."""
        return sqlite_db(self.storage_path)

    def _init_db(self) -> None:
        """Create schema and load persisted state into memory."""
        with self._connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS account"
                "(key TEXT PRIMARY KEY, value REAL)"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS positions"
                "(symbol TEXT PRIMARY KEY, quantity REAL, "
                "avg_entry_price REAL, current_price REAL, "
                "unrealized_pnl REAL, realized_pnl REAL)"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS orders"
                "(id TEXT PRIMARY KEY, symbol TEXT, side TEXT, "
                "quantity REAL, order_type TEXT, price REAL, status TEXT, "
                "created_at TEXT, filled_at TEXT, filled_price REAL, "
                "filled_quantity REAL, metadata TEXT)"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS trades"
                "(id TEXT PRIMARY KEY, symbol TEXT, side TEXT, "
                "quantity REAL, price REAL, timestamp TEXT, paper_trading INTEGER)"
            )
            row = conn.execute(
                "SELECT value FROM account WHERE key='balance'"
            ).fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO account(key, value) VALUES('balance', ?)",
                    (self.initial_balance,),
                )
                self.balance = self.initial_balance
            else:
                self.balance = row["value"]
            for r in conn.execute("SELECT * FROM positions"):
                self.positions[r["symbol"]] = PaperPosition(
                    symbol=r["symbol"],
                    quantity=r["quantity"],
                    avg_entry_price=r["avg_entry_price"],
                    current_price=r["current_price"],
                    unrealized_pnl=r["unrealized_pnl"],
                    realized_pnl=r["realized_pnl"],
                )
            for r in conn.execute("SELECT * FROM orders ORDER BY created_at"):
                import json as _json

                self.orders.append(
                    PaperOrder(
                        id=r["id"],
                        symbol=r["symbol"],
                        side=r["side"],
                        quantity=r["quantity"],
                        order_type=r["order_type"],
                        price=r["price"],
                        status=OrderStatus(r["status"]),
                        created_at=r["created_at"],
                        filled_at=r["filled_at"],
                        filled_price=r["filled_price"],
                        filled_quantity=r["filled_quantity"],
                        metadata=_json.loads(r["metadata"] or "{}"),
                    )
                )
            for r in conn.execute("SELECT * FROM trades ORDER BY timestamp"):
                self.trade_history.append(
                    {
                        "id": r["id"],
                        "symbol": r["symbol"],
                        "side": r["side"],
                        "quantity": r["quantity"],
                        "price": r["price"],
                        "timestamp": r["timestamp"],
                        "paper_trading": bool(r["paper_trading"]),
                    }
                )

    def _persist_balance(self) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE account SET value=? WHERE key='balance'",
                (self.balance,),
            )

    def _persist_position(self, symbol: str) -> None:
        pos = self.positions[symbol]
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO positions VALUES(?,?,?,?,?,?)",
                (
                    pos.symbol,
                    pos.quantity,
                    pos.avg_entry_price,
                    pos.current_price,
                    pos.unrealized_pnl,
                    pos.realized_pnl,
                ),
            )

    def _persist_order(self, order: PaperOrder) -> None:
        import json as _json

        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO orders VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    order.id,
                    order.symbol,
                    order.side,
                    order.quantity,
                    order.order_type,
                    order.price,
                    order.status.value,
                    order.created_at,
                    order.filled_at,
                    order.filled_price,
                    order.filled_quantity,
                    _json.dumps(order.metadata),
                ),
            )

    def _persist_trade(self, trade: dict) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO trades VALUES(?,?,?,?,?,?,?)",
                (
                    trade["id"],
                    trade["symbol"],
                    trade["side"],
                    trade["quantity"],
                    trade["price"],
                    trade["timestamp"],
                    1 if trade.get("paper_trading") else 0,
                ),
            )

    def _load(self) -> None:
        """Legacy entry point: state is loaded by _init_db at construction."""
        return None

    def _save(self) -> None:
        """Legacy entry point: persistence is write-through per mutation."""
        return None
    
    def _reject_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str,
        price: Optional[float],
        reason_code: str,
        reason: str,
    ) -> PaperOrder:
        """Create a REJECTED order without mutating balance or positions."""
        order = PaperOrder(
            id=str(uuid.uuid4()),
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
            price=price,
            status=OrderStatus.REJECTED,
            created_at=datetime.now().isoformat(),
            filled_at=None,
            filled_price=None,
            filled_quantity=0.0,
            metadata={
                "paper_trading": True,
                "rejection_code": reason_code,
                "rejection_reason": reason,
            },
        )
        self.orders.append(order)
        self._persist_order(order)
        return order
    
    def place_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = "market",
        price: Optional[float] = None,
        current_price: Optional[float] = None,
    ) -> PaperOrder:
        """Place a paper trading order.
        
        Args:
            symbol: Asset symbol
            side: "buy" or "sell"
            quantity: Order quantity
            order_type: "market" or "limit"
            price: Limit price (if applicable)
            current_price: Current market price (for market orders)
            
        Returns:
            PaperOrder object
        """
        effective_price = current_price if current_price is not None else (price or 0.0)

        # Risk veto: evaluate BEFORE any state mutation.
        proposal = None
        if self.risk_engine is not None:
            proposal = TradeProposal(
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=effective_price,
                order_type=order_type,
                timestamp=datetime.now(),
                metadata={"paper_trading": True},
            )
            check = self.risk_engine.evaluate(proposal)
            if check.decision == RiskDecision.REJECTED:
                order = PaperOrder(
                    id=str(uuid.uuid4()),
                    symbol=symbol,
                    side=side,
                    quantity=quantity,
                    order_type=order_type,
                    price=price,
                    status=OrderStatus.REJECTED,
                    created_at=datetime.now().isoformat(),
                    filled_at=None,
                    filled_price=None,
                    filled_quantity=0.0,
                    metadata={
                        "paper_trading": True,
                        "risk_rejected": True,
                        "risk_reason": check.reason,
                        "risk_violations": list(check.violations),
                    },
                )
                self.orders.append(order)
                self._persist_order(order)
                return order
            # NOTE: the approved trade is recorded on the risk engine only
            # once it actually fills (below), so pending limit orders do
            # not inflate daily counts/exposure.

        # Funds / position check BEFORE creating a fillable order.
        # V1 policy: no margin, no naked shorts.
        if order_type == "market" and current_price:
            if side == "buy" and quantity * current_price > self.balance:
                return self._reject_order(
                    symbol, side, quantity, order_type, price,
                    "insufficient_funds",
                    f"Order cost {quantity * current_price} exceeds balance {self.balance}",
                )
            if side == "sell":
                held = self.positions[symbol].quantity if symbol in self.positions else 0.0
                if quantity > held:
                    return self._reject_order(
                        symbol, side, quantity, order_type, price,
                        "insufficient_position",
                        f"Sell quantity {quantity} exceeds held position {held} (naked shorts disabled)",
                    )

        # Create order
        order = PaperOrder(
            id=str(uuid.uuid4()),
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
            price=price,
            status=OrderStatus.PENDING,
            created_at=datetime.now().isoformat(),
            filled_at=None,
            filled_price=None,
            filled_quantity=0.0,
            metadata={"paper_trading": True},
        )
        
        # For market orders, fill immediately
        if order_type == "market" and current_price:
            fill_price = current_price
            order.status = OrderStatus.FILLED
            order.filled_at = datetime.now().isoformat()
            order.filled_price = fill_price
            order.filled_quantity = quantity
            
            # Update balance
            if side == "buy":
                cost = quantity * fill_price
                self.balance -= cost
            else:
                revenue = quantity * fill_price
                self.balance += revenue
            
            # Update positions
            self._update_position(symbol, side, quantity, fill_price)

            # Filled: now record on the risk engine so daily counts
            # and exposure track executed trades only.
            if self.risk_engine is not None and proposal is not None:
                self.risk_engine.record_trade(proposal)
            
            # Record trade
            self.trade_history.append({
                "id": order.id,
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "price": fill_price,
                "timestamp": order.filled_at,
                "paper_trading": True,
            })
            self._persist_trade(self.trade_history[-1])
        
        self.orders.append(order)
        self._persist_order(order)
        if order.status == OrderStatus.FILLED:
            self._persist_balance()
            self._persist_position(symbol)
        return order
    
    def _update_position(
        self, symbol: str, side: str, quantity: float, price: float
    ) -> None:
        """Update position after a trade."""
        if symbol not in self.positions:
            self.positions[symbol] = PaperPosition(
                symbol=symbol,
                quantity=0.0,
                avg_entry_price=0.0,
                current_price=price,
                unrealized_pnl=0.0,
                realized_pnl=0.0,
            )
        
        pos = self.positions[symbol]
        
        if side == "buy":
            # Calculate new average entry price
            total_cost = (pos.quantity * pos.avg_entry_price) + (quantity * price)
            pos.quantity += quantity
            if pos.quantity > 0:
                pos.avg_entry_price = total_cost / pos.quantity
        else:
            # Sell
            if pos.quantity > 0:
                # Calculate realized P&L
                pnl = (price - pos.avg_entry_price) * quantity
                pos.realized_pnl += pnl
                # Balance already updated in place_order with full revenue
            pos.quantity -= quantity
        
        pos.current_price = price
        pos.unrealized_pnl = (price - pos.avg_entry_price) * pos.quantity
    
    def get_account_summary(self) -> dict:
        """Get account summary.
        
        Returns:
            Account summary dictionary
        """
        total_unrealized = sum(p.unrealized_pnl for p in self.positions.values())
        total_realized = sum(p.realized_pnl for p in self.positions.values())
        total_value = self.balance + sum(
            p.quantity * p.current_price for p in self.positions.values()
        )
        
        return {
            "balance": self.balance,
            "total_value": total_value,
            "unrealized_pnl": total_unrealized,
            "realized_pnl": total_realized,
            "total_pnl": total_unrealized + total_realized,
            "positions": len(self.positions),
            "orders": len(self.orders),
            "trades": len(self.trade_history),
            "paper_trading": True,
            "disclaimer": "This is paper trading. No real money at risk.",
        }
    
    def get_positions(self) -> list[PaperPosition]:
        """Get all positions."""
        return list(self.positions.values())
    
    def get_order_history(self, limit: int = 50) -> list[PaperOrder]:
        """Get order history."""
        return self.orders[-limit:]
    
    def get_trade_history(self, limit: int = 50) -> list[dict]:
        """Get trade history."""
        return self.trade_history[-limit:]
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order."""
        for order in self.orders:
            if order.id == order_id and order.status == OrderStatus.PENDING:
                order.status = OrderStatus.CANCELLED
                self._persist_order(order)
                return True
        return False
    
    def reset(self) -> None:
        """Reset paper trading account to initial state."""
        self.balance = self.initial_balance
        self.positions = {}
        self.orders = []
        self.trade_history = []
        with self._connect() as conn:
            conn.execute("DELETE FROM positions")
            conn.execute("DELETE FROM orders")
            conn.execute("DELETE FROM trades")
            conn.execute(
                "UPDATE account SET value=? WHERE key='balance'",
                (self.initial_balance,),
            )
