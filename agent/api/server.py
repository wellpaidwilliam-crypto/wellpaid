"""WellPaiD Trader - Authenticated HTTP API surface.

Minimal stdlib-only API (http.server) for monitoring and controlled
paper trading. Security rules:

- Every request requires `Authorization: Bearer <token>`, compared with
  `secrets.compare_digest`. The server refuses to start without a token
  (fail-closed); pass it explicitly or set WELLPAID_API_TOKEN.
- Binds 127.0.0.1 by default. Exposing it beyond localhost requires an
  explicit host argument and is the operator's responsibility (use TLS).
- POST /orders is gated by the trading safety flags: it returns 403
  unless `TRADING_ENABLED` and `PAPER_TRADING_ENABLED` are both true.
  Live trading is NEVER exposed here — the paper engine has no broker
  connection by construction.
- Request bodies are size-capped (64 KiB) to bound resource abuse.
"""

import json
import os
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Optional
from urllib.parse import urlparse, parse_qs

try:
    from agent.core.config import Config
    from agent.trading.brokers import CoinbaseDataProvider, StooqDataProvider
    from agent.trading.paper import OrderStatus, PaperTradingEngine
    from agent.trading.research import AssetType
    from agent.risk.engine import RiskEngine
except ImportError:
    from ..core.config import Config
    from ..trading.brokers import CoinbaseDataProvider, StooqDataProvider
    from ..trading.paper import OrderStatus, PaperTradingEngine
    from ..trading.research import AssetType
    from ..risk.engine import RiskEngine

MAX_BODY_BYTES = 64 * 1024


def resolve_token(explicit: Optional[str] = None) -> str:
    """Resolve the API token or raise (fail-closed on missing token)."""
    token = explicit if explicit is not None else os.getenv("WELLPAID_API_TOKEN", "")
    if not token:
        raise ValueError(
            "API token is required: pass api_token or set WELLPAID_API_TOKEN"
        )
    return token


class WellPaiDHandler(BaseHTTPRequestHandler):
    """Request handler. Context is attached as class attributes by factory."""

    config: Config = None  # type: ignore[assignment]
    paper: PaperTradingEngine = None  # type: ignore[assignment]
    risk: Optional[RiskEngine] = None
    stooq: StooqDataProvider = None  # type: ignore[assignment]
    coinbase: CoinbaseDataProvider = None  # type: ignore[assignment]
    tools: Any = None  # ToolRegistry, attached by factory

    server_version = "WellPaiD/0.3"

    def log_message(self, *args: Any) -> None:
        """Suppress default stderr logging (no request lines on console)."""

    # -- helpers ------------------------------------------------------
    def _send(self, status: int, payload: Any) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        expected = self.server.api_token  # type: ignore[attr-defined]
        provided = self.headers.get("Authorization", "")
        if not provided.startswith("Bearer "):
            return False
        return secrets.compare_digest(provided[7:], expected)

    def _read_json(self) -> Optional[dict]:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return None
        if length <= 0 or length > MAX_BODY_BYTES:
            return None
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None

    # -- routing ------------------------------------------------------
    def do_GET(self) -> None:
        if not self._authorized():
            self._send(401, {"error": "unauthorized"})
            return
        parsed = urlparse(self.path)
        if parsed.path == "/status":
            self._send(200, {"ok": True, "config": self.config.status()})
        elif parsed.path == "/account":
            self._send(200, self.paper.get_account_summary())
        elif parsed.path == "/positions":
            self._send(
                200,
                [
                    {
                        "symbol": p.symbol,
                        "quantity": p.quantity,
                        "avg_entry_price": p.avg_entry_price,
                        "current_price": p.current_price,
                        "unrealized_pnl": p.unrealized_pnl,
                        "realized_pnl": p.realized_pnl,
                    }
                    for p in self.paper.get_positions()
                ],
            )
        elif parsed.path == "/orders":
            self._send(
                200,
                [
                    {
                        "id": o.id,
                        "symbol": o.symbol,
                        "side": o.side,
                        "quantity": o.quantity,
                        "order_type": o.order_type,
                        "status": o.status.value,
                        "filled_price": o.filled_price,
                        "created_at": o.created_at,
                    }
                    for o in self.paper.get_order_history()
                ],
            )
        elif parsed.path == "/risk":
            if self.risk is None:
                self._send(200, {"risk_engine": False})
            else:
                self._send(200, {"risk_engine": True, **self.risk.get_status()})
        elif parsed.path == "/price":
            self._handle_price(parse_qs(parsed.query))
        elif parsed.path == "/tools":
            self._send(200, {"tools": self.tools.list()})
        else:
            self._send(404, {"error": "not found"})

    def _handle_tool_execute(self) -> None:
        """Run a registry tool. Auth already verified; each tool enforces
        its own gates (paper tool refuses unless paper mode is enabled)."""
        body = self._read_json()
        if not isinstance(body, dict) or not isinstance(body.get("name"), str):
            self._send(400, {"error": "tool name required"})
            return
        args = body.get("args") or {}
        if not isinstance(args, dict):
            self._send(400, {"error": "args must be an object"})
            return
        result = self.tools.execute(body["name"], args)
        self._send(200 if result.success else 422, result.to_dict())

    def _handle_price(self, query: dict) -> None:
        symbol = (query.get("symbol") or [""])[0].strip()
        type_name = (query.get("type") or ["stock"])[0].strip().lower()
        if not symbol:
            self._send(400, {"error": "symbol is required"})
            return
        try:
            asset_type = AssetType(type_name)
        except ValueError:
            self._send(
                400,
                {"error": f"unknown type; use one of {[t.value for t in AssetType]}"},
            )
            return
        provider = (
            self.coinbase if asset_type == AssetType.CRYPTO else self.stooq
        )
        try:
            price = provider.get_current_price(symbol, asset_type)
        except Exception:
            price = None
        if price is None:
            self._send(502, {"error": "quote unavailable"})
        else:
            self._send(200, {"symbol": symbol, "price": price})

    def do_POST(self) -> None:
        if not self._authorized():
            self._send(401, {"error": "unauthorized"})
            return
        parsed = urlparse(self.path)
        if parsed.path == "/tools/execute":
            self._handle_tool_execute()
            return
        if parsed.path != "/orders":
            self._send(404, {"error": "not found"})
            return
        if not self.config.can_paper_trade():
            self._send(
                403,
                {"error": "paper trading is disabled by configuration"},
            )
            return
        body = self._read_json()
        if not isinstance(body, dict):
            self._send(400, {"error": "invalid JSON body"})
            return
        try:
            symbol = str(body["symbol"])
            side = str(body["side"])
            quantity = float(body["quantity"])
            order_type = str(body.get("order_type", "market"))
            price = body.get("price")
            current_price = body.get("current_price")
        except (KeyError, TypeError, ValueError):
            self._send(400, {"error": "symbol, side, quantity required"})
            return
        order = self.paper.place_order(
            symbol,
            side,
            quantity,
            order_type,
            price=price,
            current_price=current_price,
        )
        self._send(
            200 if order.status == OrderStatus.FILLED else 422,
            {
                "id": order.id,
                "status": order.status.value,
                "symbol": order.symbol,
                "side": order.side,
                "quantity": order.quantity,
                "filled_price": order.filled_price,
                "metadata": order.metadata,
            },
        )


def create_server(
    host: str = "127.0.0.1",
    port: int = 0,
    config: Optional[Config] = None,
    paper: Optional[PaperTradingEngine] = None,
    risk: Optional[RiskEngine] = None,
    memory: Any = None,
    tasks: Any = None,
    api_token: Optional[str] = None,
) -> ThreadingHTTPServer:
    """Create (not start) the API server with shared context.

    Args:
        host: Bind address (default localhost only).
        port: Bind port (0 = ephemeral, read back via server_port).
        config: App config (fresh default if None).
        paper: Paper engine (fresh default if None).
        risk: Optional risk engine attached to the paper engine.
        memory: Optional MemoryStore (enables the memory tool).
        tasks: Optional TaskManager (enables the tasks tool).
        api_token: Bearer token, or WELLPAID_API_TOKEN env.

    Raises:
        ValueError: If no API token is configured (fail-closed).
    """
    try:
        from agent.tools.registry import build_default_registry
    except ImportError:
        from ..tools.registry import build_default_registry
    token = resolve_token(api_token)
    resolved_config = config or Config()
    resolved_paper = paper if paper is not None else PaperTradingEngine()
    handler = type(
        "BoundHandler",
        (WellPaiDHandler,),
        {
            "config": resolved_config,
            "paper": resolved_paper,
            "risk": risk,
            "stooq": StooqDataProvider(),
            "coinbase": CoinbaseDataProvider(),
            "tools": build_default_registry(
                resolved_config, resolved_paper, risk, memory, tasks
            ),
        },
    )
    server = ThreadingHTTPServer((host, port), handler)
    server.api_token = token  # type: ignore[attr-defined]
    server.daemon_threads = True
    return server
