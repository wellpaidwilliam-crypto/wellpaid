"""WellPaiD Trader - Built-in personal-agent tools (V0.4).

Calculator, system status, memory, tasks, market data, backtest and
paper-account tools. All tools wrap EXISTING backends — no second
databases, no new execution paths. The paper tool routes every submit
through RiskEngine before the paper engine (which checks again).
"""

import ast
import operator
from datetime import datetime, timedelta
from typing import Any, Optional

try:
    from agent.tools.base import SafetyClass, Tool, ToolResult
except ImportError:
    from .base import SafetyClass, Tool, ToolResult

try:
    from agent.trading.brokers import CoinbaseDataProvider, StooqDataProvider
    from agent.trading.research import (
        AssetType,
        Backtester,
        IndicatorEngine,
        MockDataProvider,
        SMAcrossoverStrategy,
    )
except ImportError:
    from ..trading.brokers import CoinbaseDataProvider, StooqDataProvider
    from ..trading.research import (
        AssetType,
        Backtester,
        IndicatorEngine,
        MockDataProvider,
        SMAcrossoverStrategy,
    )


# -- calculator (safe AST, no eval) -----------------------------------
_SAFE_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_SAFE_UNARYOPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _safe_eval(node: ast.AST) -> float:
    """Evaluate an arithmetic AST. Only numbers and operators exist here:
    names, calls, attributes and subscripts are rejected before this runs."""
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _SAFE_BINOPS:
        if isinstance(node.op, ast.Pow):
            exp = _safe_eval(node.right)
            if abs(exp) > 1000:
                raise ValueError("exponent too large")
        return _SAFE_BINOPS[type(node.op)](
            _safe_eval(node.left), _safe_eval(node.right)
        )
    if isinstance(node, ast.UnaryOp) and type(node.op) in _SAFE_UNARYOPS:
        return _SAFE_UNARYOPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError("unsupported expression")


class CalculatorTool(Tool):
    """Deterministic arithmetic. No names, no calls, no evaluation of code."""

    name = "calculator"
    description = "Evaluate a basic arithmetic expression (+ - * / // % **)."
    safety = SafetyClass.READ_ONLY
    schema = {
        "expression": {
            "type": "string",
            "required": True,
            "description": "Arithmetic expression, e.g. '(150.5*10)+25'.",
        }
    }

    def execute(self, args: dict) -> ToolResult:
        expr = args["expression"]
        if len(expr) > 200:
            return ToolResult(False, "expression too long (max 200 chars)")
        try:
            tree = ast.parse(expr, mode="eval")
        except SyntaxError:
            return ToolResult(False, "invalid arithmetic expression")
        nodes = list(ast.walk(tree))
        if len(nodes) > 100:
            return ToolResult(False, "expression too complex")
        for node in nodes:
            if isinstance(node, (ast.Name, ast.Call, ast.Attribute, ast.Subscript)):
                return ToolResult(
                    False, "only numbers and operators are allowed"
                )
        try:
            result = _safe_eval(tree)
        except ZeroDivisionError:
            return ToolResult(False, "division by zero")
        except (ValueError, OverflowError, ArithmeticError) as exc:
            return ToolResult(False, f"cannot evaluate: {exc}")
        return ToolResult(True, f"= {result}", data={"result": result})


class SystemStatusTool(Tool):
    """Report agent configuration and mode. Read-only."""

    name = "system_status"
    description = "Show system status: mode, trading flags, environment."
    safety = SafetyClass.READ_ONLY
    schema = {}

    def __init__(self, config: Any = None) -> None:
        """Attach config (a default is built when omitted)."""
        if config is None:
            try:
                from agent.core.config import Config
            except ImportError:
                from ..core.config import Config
            config = Config()
        self.config = config

    def execute(self, args: dict) -> ToolResult:
        status = self.config.status()
        mode = "TRADING" if status.get("trading_enabled") else "RESEARCH ONLY"
        return ToolResult(
            True, f"Mode: {mode}", data={**status, "mode": mode}
        )


# -- memory ------------------------------------------------------------
SECRET_REFUSALS = (
    "password",
    "passwd",
    "api_key",
    "apikey",
    "api-secret",
    "secret key",
    "private key",
    "auth token",
    "bearer token",
    "credit card",
    "ssn",
    "social security",
)


class MemoryTool(Tool):
    """Personal memory over the existing SQLite MemoryStore.

    Refuses to store anything resembling credentials: there is no secure
    secrets system, so secrets must never enter the memory database.
    """

    name = "memory"
    description = (
        "Remember facts ('remember'), search memory ('search'), "
        "recall by id ('recall'), list categories ('categories')."
    )
    safety = SafetyClass.LOCAL_WRITE
    schema = {
        "action": {
            "type": "string",
            "required": True,
            "description": "remember|search|recall|categories",
        },
        "content": {
            "type": "string",
            "required": False,
            "description": "Fact to remember.",
        },
        "category": {
            "type": "string",
            "required": False,
            "description": "Memory category (default 'general').",
        },
        "query": {
            "type": "string",
            "required": False,
            "description": "Search text.",
        },
        "memory_id": {
            "type": "string",
            "required": False,
            "description": "Memory id for recall.",
        },
        "limit": {
            "type": "integer",
            "required": False,
            "description": "Max results (default 10).",
        },
    }

    def __init__(self, store: Any) -> None:
        """Attach an existing MemoryStore (never creates a second one)."""
        self.store = store

    @staticmethod
    def _looks_secret(text: str) -> bool:
        lowered = text.lower()
        return any(marker in lowered for marker in SECRET_REFUSALS)

    def execute(self, args: dict) -> ToolResult:
        action = args["action"]
        if action == "remember":
            content = args.get("content", "")
            if not content.strip():
                return ToolResult(False, "content is required to remember")
            if self._looks_secret(content):
                return ToolResult(
                    False,
                    "refused: that looks like a credential. "
                    "Passwords, keys and tokens are never stored in memory.",
                )
            memory = self.store.save(
                content, category=args.get("category", "general") or "general"
            )
            return ToolResult(
                True,
                f"remembered as {memory.id}",
                data={"id": memory.id, "category": memory.category},
            )
        if action == "search":
            results = self.store.search(
                query=args.get("query"),
                category=args.get("category"),
                limit=args.get("limit", 10),
            )
            return ToolResult(
                True,
                f"{len(results)} match(es)",
                data={
                    "matches": [
                        {
                            "id": m.id,
                            "content": m.content,
                            "category": m.category,
                            "created_at": m.created_at,
                        }
                        for m in results
                    ]
                },
            )
        if action == "recall":
            memory = self.store.get(args.get("memory_id", ""))
            if memory is None:
                return ToolResult(False, "memory not found")
            return ToolResult(
                True,
                memory.content,
                data={
                    "id": memory.id,
                    "content": memory.content,
                    "category": memory.category,
                },
            )
        if action == "categories":
            return ToolResult(
                True, "categories listed", data={"categories": self.store.list_categories()}
            )
        return ToolResult(False, f"unknown action: {action}")


class TaskManagerTool(Tool):
    """Personal tasks over the existing SQLite TaskManager."""

    name = "tasks"
    description = (
        "Manage tasks ('create' with title, 'list', 'complete'/'delete' "
        "with task_id)."
    )
    safety = SafetyClass.LOCAL_WRITE
    schema = {
        "action": {
            "type": "string",
            "required": True,
            "description": "create|list|complete|delete",
        },
        "title": {
            "type": "string",
            "required": False,
            "description": "Task title for create.",
        },
        "task_id": {
            "type": "string",
            "required": False,
            "description": "Task id for complete/delete.",
        },
        "limit": {
            "type": "integer",
            "required": False,
            "description": "Max results for list (default 50).",
        },
    }

    def __init__(self, manager: Any) -> None:
        """Attach an existing TaskManager (never creates a second one)."""
        self.manager = manager

    def execute(self, args: dict) -> ToolResult:
        action = args["action"]
        if action == "create":
            title = (args.get("title") or "").strip()
            if not title:
                return ToolResult(False, "title is required to create a task")
            task = self.manager.create(title)
            return ToolResult(
                True, f"task created: {task.id}", data={"id": task.id, "title": title}
            )
        if action == "list":
            found = self.manager.list_tasks(limit=args.get("limit", 50))
            return ToolResult(
                True,
                f"{len(found)} task(s)",
                data={
                    "tasks": [
                        {
                            "id": t.id,
                            "title": t.title,
                            "status": t.status.value,
                            "priority": t.priority.value,
                        }
                        for t in found
                    ]
                },
            )
        if action in ("complete", "delete"):
            task_id = args.get("task_id", "")
            if not task_id:
                return ToolResult(False, "task_id is required")
            ok = (
                self.manager.complete(task_id)
                if action == "complete"
                else self.manager.delete(task_id)
            )
            if not ok:
                return ToolResult(False, "task not found")
            return ToolResult(True, f"task {action}d", data={"id": task_id})
        return ToolResult(False, f"unknown action: {action}")


# -- market data (read-only) -------------------------------------------
def _provider_for(asset_type: AssetType):
    if asset_type == AssetType.CRYPTO:
        return CoinbaseDataProvider()
    return StooqDataProvider()


class MarketDataTool(Tool):
    """Read-only quotes and history. No transaction operations exist."""

    name = "market_data"
    description = (
        "Get a current price ('price') or daily history ('history', "
        "default 30 days) for stocks (Stooq) and crypto (Coinbase)."
    )
    safety = SafetyClass.READ_ONLY
    schema = {
        "action": {
            "type": "string",
            "required": True,
            "description": "price|history",
        },
        "symbol": {
            "type": "string",
            "required": True,
            "description": "e.g. AAPL, siemens.de, BTC",
        },
        "asset_type": {
            "type": "string",
            "required": False,
            "description": "stock|crypto|forex|commodity|index (default stock)",
        },
        "days": {
            "type": "integer",
            "required": False,
            "description": "History window in days (default 30, max 365).",
        },
    }

    def execute(self, args: dict) -> ToolResult:
        try:
            asset_type = AssetType(args.get("asset_type", "stock"))
        except ValueError:
            return ToolResult(False, "unknown asset_type")
        symbol = args["symbol"].strip()
        if not symbol:
            return ToolResult(False, "symbol is required")
        provider = _provider_for(asset_type)
        action = args["action"]
        try:
            if action == "price":
                price = provider.get_current_price(symbol, asset_type)
                if price is None:
                    return ToolResult(
                        False,
                        f"quote unavailable for {symbol}",
                        warnings=["provider unreachable or unknown symbol"],
                    )
                return ToolResult(
                    True, f"{symbol} = {price}", data={"symbol": symbol, "price": price}
                )
            if action == "history":
                days = args.get("days", 30)
                if days < 1 or days > 365:
                    return ToolResult(False, "days must be 1..365")
                end = datetime.now()
                data = provider.get_historical_data(
                    symbol, asset_type, end - timedelta(days=days), end
                )
                if data is None or not data.data:
                    return ToolResult(
                        False,
                        f"history unavailable for {symbol}",
                        warnings=["provider unreachable or unknown symbol"],
                    )
                closes = [bar.close for bar in data.data]
                return ToolResult(
                    True,
                    f"{symbol}: {len(closes)} daily bars, last close {closes[-1]}",
                    data={
                        "symbol": symbol,
                        "bars": len(closes),
                        "first": data.data[0].timestamp.isoformat(),
                        "last": data.data[-1].timestamp.isoformat(),
                        "last_close": closes[-1],
                        "closes": closes,
                        "source": data.metadata.get("source"),
                    },
                )
        except Exception as exc:  # noqa: BLE001 - network safety net
            return ToolResult(
                False,
                f"market data unavailable for {symbol}",
                warnings=[type(exc).__name__],
            )
        return ToolResult(False, f"unknown action: {action}")


class BacktestTool(Tool):
    """Research backtests with mandatory honesty labeling."""

    name = "backtest"
    description = (
        "Run an SMA-crossover research backtest on read-only history. "
        "Results are HISTORICAL, never predictions."
    )
    safety = SafetyClass.READ_ONLY
    schema = {
        "symbol": {"type": "string", "required": True, "description": "e.g. AAPL, BTC"},
        "asset_type": {
            "type": "string",
            "required": False,
            "description": "stock|crypto (default stock)",
        },
        "days": {
            "type": "integer",
            "required": False,
            "description": "History window in days (default 120, max 365).",
        },
        "source": {
            "type": "string",
            "required": False,
            "description": "auto|mock (mock = synthetic data for offline use)",
        },
    }

    HONESTY = (
        "HISTORICAL RESULT, not a future prediction. "
        "Past performance does not indicate future results. "
        "Simplified execution (close-price fills, no fees/slippage)."
    )

    def execute(self, args: dict) -> ToolResult:
        try:
            asset_type = AssetType(args.get("asset_type", "stock"))
        except ValueError:
            return ToolResult(False, "unknown asset_type")
        symbol = args["symbol"].strip()
        if not symbol:
            return ToolResult(False, "symbol is required")
        days = args.get("days", 120)
        if isinstance(days, bool) or not isinstance(days, int) or days < 60 or days > 365:
            return ToolResult(False, "days must be 60..365")
        end = datetime.now()
        start = end - timedelta(days=days)
        try:
            if args.get("source", "auto") == "mock":
                market = MockDataProvider().get_historical_data(
                    symbol, asset_type, start, end
                )
                source = "mock"
            else:
                provider = _provider_for(asset_type)
                market = provider.get_historical_data(symbol, asset_type, start, end)
                source = market.metadata.get("source") if market else "none"
        except Exception as exc:  # noqa: BLE001 - network safety net
            return ToolResult(
                False,
                f"market data unavailable for {symbol}",
                warnings=[type(exc).__name__, self.HONESTY],
            )
        if market is None or not market.data:
            return ToolResult(
                False,
                f"market data unavailable for {symbol}",
                warnings=[self.HONESTY],
            )
        strategy = SMAcrossoverStrategy()
        result = Backtester().run(strategy, market)
        closes = [b.close for b in market.data]
        sma20 = IndicatorEngine.sma(market.data, 20)
        return ToolResult(
            True,
            f"{symbol}: {strategy.get_name()}, return {result.total_return:.2%} "
            f"over {len(market.data)} bars. {self.HONESTY}",
            data={
                "symbol": symbol,
                "strategy": strategy.get_name(),
                "bars": len(market.data),
                "total_return": result.total_return,
                "win_rate": result.win_rate,
                "trades": len(result.trades),
                "last_close": closes[-1],
                "sma20_last": sma20[-1] if sma20 else None,
                "source": source,
                "assumptions": [
                    "fills at bar close",
                    "no fees, spread or slippage",
                    "single position, full capital per signal",
                ],
            },
            warnings=[self.HONESTY],
        )


class PaperAccountTool(Tool):
    """Paper-money account. Every submit passes RiskEngine first.

    There is deliberately no top-up/withdraw/deposit action and no live
    mode: the underlying engine has no broker connection.
    """

    name = "paper_account"
    description = (
        "Inspect paper account ('balance'|'positions'|'orders'), "
        "risk-check a trade without executing ('propose'), or execute a "
        "simulated trade ('submit', requires paper mode enabled). "
        "All activity is labeled PAPER TRADE."
    )
    safety = SafetyClass.PAPER_TRADE
    schema = {
        "action": {
            "type": "string",
            "required": True,
            "description": "balance|positions|orders|propose|submit",
        },
        "symbol": {"type": "string", "required": False, "description": "e.g. AAPL"},
        "side": {"type": "string", "required": False, "description": "buy|sell"},
        "quantity": {"type": "number", "required": False, "description": "Trade size."},
        "current_price": {
            "type": "number",
            "required": False,
            "description": "Market price for market fills.",
        },
    }

    def __init__(self, config: Any = None, paper: Any = None, risk: Any = None) -> None:
        """Attach config, paper engine and risk engine."""
        if config is None:
            try:
                from agent.core.config import Config
            except ImportError:
                from ..core.config import Config
            config = Config()
        if paper is None:
            try:
                from agent.trading.paper import PaperTradingEngine
            except ImportError:
                from ..trading.paper import PaperTradingEngine
            paper = PaperTradingEngine()
        self.config = config
        self.paper = paper
        self.risk = risk

    def _proposal(self, args: dict) -> Optional[Any]:
        try:
            from agent.risk.engine import TradeProposal
        except ImportError:
            from ..risk.engine import TradeProposal
        symbol = (args.get("symbol") or "").strip()
        side = args.get("side")
        quantity = args.get("quantity")
        if not symbol or side not in ("buy", "sell"):
            return None
        if isinstance(quantity, bool) or not isinstance(quantity, (int, float)):
            return None
        price = args.get("current_price") or 0.0
        return TradeProposal(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            order_type="market",
            timestamp=datetime.now(),
            metadata={"paper_trading": True, "via": "paper_account_tool"},
        )

    def execute(self, args: dict) -> ToolResult:
        action = args["action"]
        if action == "balance":
            summary = self.paper.get_account_summary()
            return ToolResult(
                True,
                f"PAPER balance {summary['balance']}",
                data=summary,
                warnings=["PAPER TRADE account: simulated money only."],
            )
        if action == "positions":
            positions = [
                {
                    "symbol": p.symbol,
                    "quantity": p.quantity,
                    "avg_entry_price": p.avg_entry_price,
                    "unrealized_pnl": p.unrealized_pnl,
                    "realized_pnl": p.realized_pnl,
                }
                for p in self.paper.get_positions()
            ]
            return ToolResult(
                True,
                f"PAPER positions: {len(positions)}",
                data={"positions": positions},
                warnings=["PAPER TRADE account: simulated money only."],
            )
        if action == "orders":
            orders = [
                {
                    "id": o.id,
                    "symbol": o.symbol,
                    "side": o.side,
                    "quantity": o.quantity,
                    "status": o.status.value,
                }
                for o in self.paper.get_order_history()
            ]
            return ToolResult(
                True,
                f"PAPER orders: {len(orders)}",
                data={"orders": orders},
                warnings=["PAPER TRADE account: simulated money only."],
            )
        if action == "propose":
            if self.risk is None:
                return ToolResult(False, "risk engine unavailable: cannot propose")
            proposal = self._proposal(args)
            if proposal is None:
                return ToolResult(False, "symbol, side (buy|sell) and quantity required")
            check = self.risk.evaluate(proposal)
            try:
                from agent.risk.engine import format_rejection
            except ImportError:
                from ..risk.engine import format_rejection
            approved = check.decision.value == "approved"
            return ToolResult(
                approved,
                ("PROPOSED PAPER TRADE approved by risk"
                 if approved else f"PROPOSED PAPER TRADE rejected:\n{format_rejection(check)}"),
                data={
                    "symbol": proposal.symbol,
                    "side": proposal.side,
                    "quantity": proposal.quantity,
                },
                warnings=["PAPER TRADE proposal: no money moved."],
                risk={
                    "decision": check.decision.value,
                    "reason": check.reason,
                    "violations": list(check.violations),
                },
            )
        if action == "submit":
            if not self.config.can_paper_trade():
                return ToolResult(
                    False,
                    "refused: paper trading is disabled by configuration",
                )
            proposal = self._proposal(args)
            if proposal is None:
                return ToolResult(False, "symbol, side (buy|sell) and quantity required")
            order = self.paper.place_order(
                proposal.symbol,
                proposal.side,
                proposal.quantity,
                "market",
                current_price=args.get("current_price"),
            )
            filled = order.status.value == "filled"
            return ToolResult(
                filled,
                f"PAPER TRADE {order.status.value}: {proposal.side} "
                f"{proposal.quantity} {proposal.symbol}",
                data={"order_id": order.id, "status": order.status.value},
                warnings=["PAPER TRADE: simulated money only."],
                risk={
                    "rejected": order.status.value == "rejected",
                    "metadata": order.metadata,
                },
            )
        return ToolResult(False, f"unknown action: {action}")
