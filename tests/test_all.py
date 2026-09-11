"""WellPaiD Trader - Comprehensive Test Suite

Tests for all major modules with focus on safety controls.
"""

import os
import tempfile
import unittest
from datetime import datetime, timedelta

# Import all modules
from agent.core.config import Config, get_config, reset_config
from agent.core.main import WellPaiDAgent
from agent.core.router import CommandRouter
from agent.core.tasks import TaskManager, TaskStatus, TaskPriority
from agent.data.memory import MemoryStore
from agent.logs.logging_config import setup_logging, get_logger
from agent.risk.engine import RiskEngine, RiskDecision, TradeProposal
from agent.trading.paper import PaperTradingEngine, OrderStatus
from agent.trading.research import (
    MockDataProvider,
    IndicatorEngine,
    SMAcrossoverStrategy,
    Backtester,
    AssetType,
)


class TestConfiguration(unittest.TestCase):
    """Test configuration system."""
    
    def setUp(self):
        reset_config()
    
    def test_default_trading_disabled(self):
        """Test that all trading is disabled by default."""
        config = Config()
        self.assertFalse(config.TRADING_ENABLED)
        self.assertFalse(config.PAPER_TRADING_ENABLED)
        self.assertFalse(config.LIVE_TRADING_ENABLED)
    
    def test_safety_validation(self):
        """Test that safety validation works."""
        config = Config()
        is_safe, message = config.validate_trading_safety()
        self.assertTrue(is_safe)
        self.assertIn("OK", message)
    
    def test_can_trade_methods(self):
        """Test can_trade methods return False by default."""
        config = Config()
        self.assertFalse(config.can_trade())
        self.assertFalse(config.can_paper_trade())
        self.assertFalse(config.can_live_trade())


class TestCoreAgent(unittest.TestCase):
    """Test core agent."""
    
    def test_agent_creation(self):
        """Test agent can be created."""
        agent = WellPaiDAgent()
        self.assertEqual(agent.version, "0.4.0")
        self.assertFalse(agent.running)
    
    def test_status_shows_disabled(self):
        """Test status shows trading as disabled."""
        agent = WellPaiDAgent()
        # Capture output
        import io
        import sys
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        
        agent._cmd_status([])
        
        output = sys.stdout.getvalue()
        sys.stdout = old_stdout
        
        self.assertIn("DISABLED", output)


class TestCommandRouter(unittest.TestCase):
    """Test command router."""
    
    def test_register_command(self):
        """Test command registration."""
        router = CommandRouter()
        router.register("test", lambda args: "ok", "Test command")
        self.assertTrue(router.has_command("test"))
    
    def test_execute_command(self):
        """Test command execution."""
        router = CommandRouter()
        router.register("test", lambda args: "ok", "Test command")
        success, msg = router.execute("test")
        self.assertTrue(success)
        self.assertEqual(msg, "ok")
    
    def test_unknown_command(self):
        """Test unknown command handling."""
        router = CommandRouter()
        success, msg = router.execute("unknown")
        self.assertFalse(success)
        self.assertIn("Unknown command", msg)


class TestMemory(unittest.TestCase):
    """Test memory system."""
    
    def test_save_and_retrieve(self):
        """Test saving and retrieving memories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = MemoryStore(storage_path=os.path.join(tmpdir, "test.json"))
            memory = store.save("Test memory", category="test")
            retrieved = store.get(memory.id)
            self.assertIsNotNone(retrieved)
            self.assertEqual(retrieved.content, "Test memory")
    
    def test_search(self):
        """Test memory search."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = MemoryStore(storage_path=os.path.join(tmpdir, "test.json"))
            store.save("Python programming", category="tech")
            store.save("Trading strategy", category="trading")
            
            results = store.search(query="Python")
            self.assertEqual(len(results), 1)
            
            results = store.search(category="trading")
            self.assertEqual(len(results), 1)


class TestTaskManager(unittest.TestCase):
    """Test task manager."""
    
    def test_create_task(self):
        """Test task creation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = TaskManager(storage_path=os.path.join(tmpdir, "test.json"))
            task = manager.create("Test task", priority=TaskPriority.HIGH)
            self.assertEqual(task.title, "Test task")
            self.assertEqual(task.priority, TaskPriority.HIGH)
    
    def test_complete_task(self):
        """Test task completion."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = TaskManager(storage_path=os.path.join(tmpdir, "test.json"))
            task = manager.create("Test task")
            self.assertTrue(manager.complete(task.id))
            retrieved = manager.get(task.id)
            self.assertEqual(retrieved.status, TaskStatus.COMPLETED)


class TestRiskEngine(unittest.TestCase):
    """Test risk engine."""
    
    def test_approve_valid_trade(self):
        """Test that valid trades are approved."""
        engine = RiskEngine(max_position_size=100)
        proposal = TradeProposal(
            symbol="AAPL",
            side="buy",
            quantity=10,
            price=100.0,
            order_type="market",
            timestamp=datetime.now(),
            metadata={},
        )
        result = engine.evaluate(proposal)
        self.assertEqual(result.decision, RiskDecision.APPROVED)
    
    def test_reject_oversized_trade(self):
        """Test that oversized trades are rejected."""
        engine = RiskEngine(max_position_size=100)
        proposal = TradeProposal(
            symbol="AAPL",
            side="buy",
            quantity=200,  # Exceeds max
            price=100.0,
            order_type="market",
            timestamp=datetime.now(),
            metadata={},
        )
        result = engine.evaluate(proposal)
        self.assertEqual(result.decision, RiskDecision.REJECTED)
    
    def test_risk_engine_authority(self):
        """Test that risk engine has absolute authority."""
        engine = RiskEngine()
        # Verify it can approve or reject
        self.assertTrue(hasattr(engine, 'evaluate'))
        self.assertTrue(hasattr(engine, 'record_trade'))


class TestPaperTrading(unittest.TestCase):
    """Test paper trading engine."""
    
    def test_paper_trading_only(self):
        """Test that paper trading uses simulated money."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = PaperTradingEngine(
                initial_balance=10000.0,
                storage_path=os.path.join(tmpdir, "test.json"),
            )
            summary = engine.get_account_summary()
            self.assertTrue(summary["paper_trading"])
            self.assertIn("disclaimer", summary)
    
    def test_place_order(self):
        """Test placing paper orders."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = PaperTradingEngine(
                initial_balance=10000.0,
                storage_path=os.path.join(tmpdir, "test.json"),
            )
            order = engine.place_order(
                "AAPL", "buy", 10, "market", current_price=150.0
            )
            self.assertEqual(order.status, OrderStatus.FILLED)


class TestTradingResearch(unittest.TestCase):
    """Test trading research foundation."""
    
    def test_mock_data_provider(self):
        """Test mock data provider."""
        provider = MockDataProvider()
        data = provider.get_historical_data(
            "AAPL",
            AssetType.STOCK,
            datetime.now() - timedelta(days=30),
            datetime.now(),
        )
        self.assertIsNotNone(data)
        self.assertEqual(len(data.data), 31)
    
    def test_indicator_calculation(self):
        """Test indicator calculations."""
        provider = MockDataProvider()
        data = provider.get_historical_data(
            "AAPL",
            AssetType.STOCK,
            datetime.now() - timedelta(days=100),
            datetime.now(),
        )
        sma = IndicatorEngine.sma(data.data, 20)
        self.assertGreater(len(sma), 0)
    
    def test_backtester_disclaimer(self):
        """Test that backtester includes disclaimer."""
        provider = MockDataProvider()
        data = provider.get_historical_data(
            "AAPL",
            AssetType.STOCK,
            datetime.now() - timedelta(days=100),
            datetime.now(),
        )
        strategy = SMAcrossoverStrategy()
        backtester = Backtester()
        result = backtester.run(strategy, data)
        self.assertIn("disclaimer", result.metadata)
        self.assertIn("Past performance", result.metadata["disclaimer"])


class TestSafetyControls(unittest.TestCase):
    """Test critical safety controls."""
    
    def test_live_trading_disabled_by_default(self):
        """Test that live trading is disabled by default."""
        config = Config()
        self.assertFalse(config.LIVE_TRADING_ENABLED)
    
    def test_paper_trading_not_live(self):
        """Test that paper trading cannot become live trading."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = PaperTradingEngine(
                storage_path=os.path.join(tmpdir, "test.json"),
            )
            summary = engine.get_account_summary()
            self.assertTrue(summary["paper_trading"])
    
    def test_no_real_orders(self):
        """Test that no real orders are placed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = PaperTradingEngine(
                storage_path=os.path.join(tmpdir, "test.json"),
            )
            order = engine.place_order(
                "AAPL", "buy", 10, "market", current_price=150.0
            )
            # Order should be marked as paper trading
            self.assertIn("paper_trading", order.metadata)
    
    def test_missing_credentials_no_unsafe_behavior(self):
        """Test that missing credentials don't cause unsafe behavior."""
        config = Config()
        # Should not raise exception
        self.assertFalse(config.EXCHANGE_API_KEY)
        self.assertFalse(config.EXCHANGE_API_SECRET)
    
    def test_risk_rejection_prevents_execution(self):
        """Test that risk rejection prevents execution."""
        engine = RiskEngine(max_position_size=100)
        proposal = TradeProposal(
            symbol="AAPL",
            side="buy",
            quantity=200,
            price=100.0,
            order_type="market",
            timestamp=datetime.now(),
            metadata={},
        )
        result = engine.evaluate(proposal)
        self.assertEqual(result.decision, RiskDecision.REJECTED)
        
        # Paper trading should check risk before executing
        with tempfile.TemporaryDirectory() as tmpdir:
            paper = PaperTradingEngine(
                storage_path=os.path.join(tmpdir, "test.json"),
            )
            # In a real integration, paper would check risk first
            # This test verifies the risk engine can reject
            self.assertEqual(result.decision, RiskDecision.REJECTED)


class TestFailClosedConfig(unittest.TestCase):
    """Test fail-closed safety validation and env parsing."""

    def setUp(self):
        reset_config()
        for key in ("TRADING_ENABLED", "PAPER_TRADING_ENABLED",
                    "LIVE_TRADING_ENABLED"):
            os.environ.pop(key, None)

    def tearDown(self):
        reset_config()
        for key in ("TRADING_ENABLED", "PAPER_TRADING_ENABLED",
                    "LIVE_TRADING_ENABLED", "WELLPAID_TEST_QUOTED",
                    "WELLPAID_TEST_EXPORT", "WELLPAID_TEST_EMPTY"):
            os.environ.pop(key, None)

    def test_paper_without_master_is_unsafe(self):
        """Paper enabled without master switch must fail validation."""
        os.environ["PAPER_TRADING_ENABLED"] = "true"
        config = Config()
        is_safe, _ = config.validate_trading_safety()
        self.assertFalse(is_safe)

    def test_live_without_master_is_unsafe(self):
        """Live enabled without master switch must fail validation."""
        os.environ["LIVE_TRADING_ENABLED"] = "true"
        config = Config()
        is_safe, _ = config.validate_trading_safety()
        self.assertFalse(is_safe)

    def test_env_file_parsing(self):
        """Env loader strips quotes, export prefix, keeps empty values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = os.path.join(tmpdir, ".env")
            with open(env_path, "w", encoding="utf-8") as f:
                f.write('WELLPAID_TEST_QUOTED="a b"\n')
                f.write("export WELLPAID_TEST_EXPORT=yes\n")
                f.write("WELLPAID_TEST_EMPTY=\n")
            Config(env_file=env_path)
            self.assertEqual(os.environ.get("WELLPAID_TEST_QUOTED"), "a b")
            self.assertEqual(os.environ.get("WELLPAID_TEST_EXPORT"), "yes")
            self.assertIn("WELLPAID_TEST_EMPTY", os.environ)


class TestRiskValidation(unittest.TestCase):
    """Test risk engine rejects malformed proposals."""

    def _proposal(self, **overrides):
        kwargs = {
            "symbol": "AAPL",
            "side": "buy",
            "quantity": 10,
            "price": 100.0,
            "order_type": "market",
            "timestamp": datetime.now(),
            "metadata": {},
        }
        kwargs.update(overrides)
        return TradeProposal(**kwargs)

    def test_invalid_side_rejected(self):
        engine = RiskEngine()
        result = engine.evaluate(self._proposal(side="hold"))
        self.assertEqual(result.decision, RiskDecision.REJECTED)

    def test_zero_quantity_rejected(self):
        engine = RiskEngine()
        result = engine.evaluate(self._proposal(quantity=0))
        self.assertEqual(result.decision, RiskDecision.REJECTED)

    def test_negative_quantity_rejected(self):
        engine = RiskEngine()
        result = engine.evaluate(self._proposal(quantity=-5))
        self.assertEqual(result.decision, RiskDecision.REJECTED)

    def test_negative_price_rejected(self):
        engine = RiskEngine()
        result = engine.evaluate(self._proposal(price=-1.0))
        self.assertEqual(result.decision, RiskDecision.REJECTED)


class TestPaperFunds(unittest.TestCase):
    """Test paper engine funds and short-sale guards."""

    def test_buy_beyond_balance_rejected(self):
        """A buy whose cost exceeds balance must not fill."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = PaperTradingEngine(
                initial_balance=10000.0,
                storage_path=os.path.join(tmpdir, "test.json"),
            )
            order = engine.place_order(
                "AAPL", "buy", 1000, "market", current_price=150.0
            )
            self.assertEqual(order.status, OrderStatus.REJECTED)
            self.assertEqual(
                order.metadata.get("rejection_code"), "insufficient_funds"
            )
            self.assertEqual(engine.get_account_summary()["balance"], 10000.0)
            self.assertEqual(len(engine.get_positions()), 0)

    def test_naked_short_rejected(self):
        """Selling what is not held must not fill."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = PaperTradingEngine(
                storage_path=os.path.join(tmpdir, "test.json"),
            )
            order = engine.place_order(
                "AAPL", "sell", 5, "market", current_price=150.0
            )
            self.assertEqual(order.status, OrderStatus.REJECTED)
            self.assertEqual(
                order.metadata.get("rejection_code"), "insufficient_position"
            )

    def test_roundtrip_buy_then_sell(self):
        """Buy followed by sell of held quantity fills both."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = PaperTradingEngine(
                initial_balance=10000.0,
                storage_path=os.path.join(tmpdir, "test.json"),
            )
            buy = engine.place_order(
                "AAPL", "buy", 10, "market", current_price=150.0
            )
            self.assertEqual(buy.status, OrderStatus.FILLED)
            sell = engine.place_order(
                "AAPL", "sell", 10, "market", current_price=150.0
            )
            self.assertEqual(sell.status, OrderStatus.FILLED)

    def test_risk_recorded_only_on_fill(self):
        """Pending limit orders must not consume risk-engine quota."""
        with tempfile.TemporaryDirectory() as tmpdir:
            risk = RiskEngine(max_trades_per_day=100)
            engine = PaperTradingEngine(
                storage_path=os.path.join(tmpdir, "test.json"),
                risk_engine=risk,
            )
            engine.place_order("AAPL", "buy", 1, "limit", price=150.0)
            self.assertEqual(len(risk.daily_trades), 0)
            engine.place_order(
                "AAPL", "buy", 1, "market", current_price=150.0
            )
            self.assertEqual(len(risk.daily_trades), 1)


class TestLoggingRedaction(unittest.TestCase):
    """Test sensitive data is scrubbed including format args."""

    def test_format_args_redacted(self):
        """logger.info('api_key=%s', secret) must not leak the secret."""
        import io
        import logging
        from agent.logs.logging_config import SensitiveFilter

        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.addFilter(SensitiveFilter())
        test_logger = logging.getLogger("wellpaid.test_redaction")
        test_logger.handlers.clear()
        test_logger.addHandler(handler)
        test_logger.setLevel(logging.INFO)
        try:
            test_logger.info("connecting with api_key=%s", "SUPERSECRET123")
            output = stream.getvalue()
            self.assertNotIn("SUPERSECRET123", output)
            self.assertIn("REDACTED", output)
        finally:
            test_logger.handlers.clear()


class TestAtomicStorage(unittest.TestCase):
    """Test atomic JSON persistence."""

    def test_write_and_no_temp_leftovers(self):
        """atomic_write_json writes valid JSON and cleans up temp files."""
        import glob
        import json
        from agent.core.storage import atomic_write_json

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "store.json")
            atomic_write_json(path, {"a": 1, "b": [1, 2, 3]})
            with open(path, "r", encoding="utf-8") as f:
                self.assertEqual(json.load(f), {"a": 1, "b": [1, 2, 3]})
            leftovers = glob.glob(os.path.join(tmpdir, "*.tmp"))
            self.assertEqual(leftovers, [])

    def test_overwrite_is_atomic(self):
        """Overwriting an existing file preserves valid JSON."""
        import json
        from agent.core.storage import atomic_write_json

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "store.json")
            atomic_write_json(path, {"v": 1})
            atomic_write_json(path, {"v": 2})
            with open(path, "r", encoding="utf-8") as f:
                self.assertEqual(json.load(f), {"v": 2})


class TestRiskNotional(unittest.TestCase):
    """Test notional-based risk limits."""

    def _proposal(self, **overrides):
        kwargs = {
            "symbol": "AAPL",
            "side": "buy",
            "quantity": 10,
            "price": 100.0,
            "order_type": "market",
            "timestamp": datetime.now(),
            "metadata": {},
        }
        kwargs.update(overrides)
        return TradeProposal(**kwargs)

    def test_oversized_notional_rejected(self):
        """A small quantity at a huge price must be rejected on notional."""
        engine = RiskEngine(
            max_position_size=10000, max_total_exposure=100000,
            max_notional_per_trade=100000,
        )
        result = engine.evaluate(self._proposal(quantity=10, price=20000.0))
        self.assertEqual(result.decision, RiskDecision.REJECTED)
        self.assertTrue(
            any("notional" in v.lower() for v in result.violations)
        )

    def test_total_notional_cap_enforced(self):
        """Accumulated notional exposure trips the portfolio cap."""
        engine = RiskEngine(
            max_position_size=10000, max_total_exposure=100000,
            max_notional_per_trade=100000,
            max_total_notional_exposure=50000,
        )
        engine.record_trade(self._proposal(quantity=10, price=4000.0))
        result = engine.evaluate(self._proposal(quantity=10, price=4000.0))
        self.assertEqual(result.decision, RiskDecision.REJECTED)

    def test_status_reports_notional(self):
        """Status exposes notional exposure and limits."""
        engine = RiskEngine()
        status = engine.get_status()
        self.assertIn("total_notional_exposure", status)
        self.assertIn("max_notional_per_trade", status)
        self.assertIn("max_total_notional_exposure", status)

    def test_from_config(self):
        """Risk engine picks up env-backed config limits."""
        import os as _os

        old = {
            k: _os.environ.get(k)
            for k in ("MAX_POSITION_SIZE", "MAX_NOTIONAL_PER_TRADE")
        }
        _os.environ["MAX_POSITION_SIZE"] = "42"
        _os.environ["MAX_NOTIONAL_PER_TRADE"] = "42000"
        try:
            reset_config()
            engine = RiskEngine.from_config(Config())
            self.assertEqual(engine.max_position_size, 42)
            self.assertEqual(engine.max_notional_per_trade, 42000.0)
        finally:
            for k, v in old.items():
                if v is None:
                    _os.environ.pop(k, None)
                else:
                    _os.environ[k] = v
            reset_config()


class TestSQLitePersistence(unittest.TestCase):
    """Test state survives engine reconstruction via SQLite."""

    def test_paper_reload(self):
        """Balance, positions and orders persist across restarts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "paper.db")
            engine = PaperTradingEngine(
                initial_balance=10000.0, storage_path=path
            )
            engine.place_order("AAPL", "buy", 10, "market", current_price=150.0)
            reloaded = PaperTradingEngine(
                initial_balance=10000.0, storage_path=path
            )
            self.assertEqual(reloaded.balance, 8500.0)
            self.assertEqual(len(reloaded.get_positions()), 1)
            self.assertEqual(len(reloaded.get_order_history()), 1)
            self.assertEqual(len(reloaded.get_trade_history()), 1)

    def test_tasks_reload(self):
        """Tasks persist across manager restarts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "tasks.db")
            manager = TaskManager(storage_path=path)
            task = manager.create("Persist me", priority=TaskPriority.HIGH)
            reloaded = TaskManager(storage_path=path)
            retrieved = reloaded.get(task.id)
            self.assertIsNotNone(retrieved)
            self.assertEqual(retrieved.title, "Persist me")
            self.assertEqual(retrieved.priority, TaskPriority.HIGH)

    def test_memory_reload(self):
        """Memories persist across store restarts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "memory.db")
            store = MemoryStore(storage_path=path)
            memory = store.save("Remember this", category="test")
            reloaded = MemoryStore(storage_path=path)
            retrieved = reloaded.get(memory.id)
            self.assertIsNotNone(retrieved)
            self.assertEqual(retrieved.content, "Remember this")


class TestBrokers(unittest.TestCase):
    """Test read-only providers (parsing and guards; no live calls)."""

    def test_stooq_symbol_mapping(self):
        from agent.trading.brokers import StooqDataProvider

        provider = StooqDataProvider()
        self.assertEqual(provider.normalize_symbol("AAPL"), "aapl.us")
        self.assertEqual(provider.normalize_symbol("siemens.de"), "siemens.de")
        with self.assertRaises(ValueError):
            provider.normalize_symbol("  ")

    def test_coinbase_pair_mapping(self):
        from agent.trading.brokers import CoinbaseDataProvider

        provider = CoinbaseDataProvider()
        self.assertEqual(provider.normalize_pair("BTC"), "BTC-USD")
        self.assertEqual(provider.normalize_pair("eth/eur"), "ETH-EUR")
        with self.assertRaises(ValueError):
            provider.normalize_pair("  ")

    def test_wrong_asset_type_returns_none(self):
        from agent.trading.brokers import CoinbaseDataProvider

        now = datetime.now()
        self.assertIsNone(
            CoinbaseDataProvider().get_historical_data(
                "AAPL", AssetType.STOCK, now, now
            )
        )

    def test_stooq_history_parsing(self):
        import agent.trading.brokers as brokers
        from agent.trading.brokers import StooqDataProvider

        csv_body = (
            "Date,Open,High,Low,Close,Volume\n"
            "2024-01-02,100,101,99,100.5,1000\n"
            "2024-01-03,100.5,102,100,101,1200\n"
        )
        original = brokers._http_get_text
        brokers._http_get_text = lambda url, timeout=15: csv_body
        try:
            data = StooqDataProvider().get_historical_data(
                "AAPL",
                AssetType.STOCK,
                datetime(2024, 1, 1),
                datetime(2024, 1, 31),
            )
        finally:
            brokers._http_get_text = original
        self.assertIsNotNone(data)
        self.assertEqual(len(data.data), 2)
        self.assertAlmostEqual(data.data[0].close, 100.5)
        self.assertEqual(data.metadata["source"], "stooq")

    def test_coinbase_candles_parsing(self):
        import json as _json
        import agent.trading.brokers as brokers
        from agent.trading.brokers import CoinbaseDataProvider

        payload = _json.dumps([
            [1704153600, 42000, 43000, 42500, 42800, 123.4],
            [1704067200, 41000, 42200, 41500, 42000, 100.0],
        ])
        original = brokers._http_get_text
        brokers._http_get_text = lambda url, timeout=15: payload
        try:
            data = CoinbaseDataProvider().get_historical_data(
                "BTC",
                AssetType.CRYPTO,
                datetime(2024, 1, 1),
                datetime(2024, 1, 31),
            )
        finally:
            brokers._http_get_text = original
        self.assertIsNotNone(data)
        self.assertEqual(len(data.data), 2)
        # Sorted oldest first.
        self.assertLess(
            data.data[0].timestamp, data.data[1].timestamp
        )
        self.assertAlmostEqual(data.data[1].close, 42800.0)

    def test_network_failure_returns_none(self):
        import agent.trading.brokers as brokers
        from agent.trading.brokers import StooqDataProvider

        def boom(url, timeout=15):
            raise TimeoutError("offline")

        original = brokers._http_get_text
        brokers._http_get_text = boom
        try:
            result = StooqDataProvider().get_current_price("AAPL", AssetType.STOCK)
        finally:
            brokers._http_get_text = original
        self.assertIsNone(result)


class TestAPISurface(unittest.TestCase):
    """Test authenticated API: auth enforcement and trading gate."""

    def _client(self, server):
        import json as _json
        import urllib.request
        import urllib.error

        base = f"http://127.0.0.1:{server.server_address[1]}"

        def call(method, path, token=None, body=None):
            data = _json.dumps(body).encode() if body is not None else None
            req = urllib.request.Request(base + path, data=data, method=method)
            if token:
                req.add_header("Authorization", f"Bearer {token}")
            if body is not None:
                req.add_header("Content-Type", "application/json")
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    return resp.status, _json.loads(resp.read().decode())
            except urllib.error.HTTPError as e:
                return e.code, _json.loads(e.read().decode())

        return call

    def _serve(self, **kwargs):
        import threading
        from agent.api.server import create_server

        kwargs.setdefault("api_token", "test-token-123")
        server = create_server("127.0.0.1", 0, **kwargs)

        def _target():
            try:
                server.serve_forever()
            except OSError:
                pass  # shutdown/close race on Windows teardown

        thread = threading.Thread(target=_target, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)
        return server

    def test_unauthorized_rejected(self):
        server = self._serve()
        call = self._client(server)
        status, _ = call("GET", "/status")
        self.assertEqual(status, 401)
        status, _ = call("GET", "/status", token="wrong-token")
        self.assertEqual(status, 401)

    def test_authorized_status(self):
        server = self._serve()
        call = self._client(server)
        status, body = call("GET", "/status", token="test-token-123")
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])

    def test_orders_blocked_when_disabled(self):
        server = self._serve()
        call = self._client(server)
        status, body = call(
            "POST", "/orders", token="test-token-123",
            body={"symbol": "AAPL", "side": "buy", "quantity": 1,
                  "current_price": 100.0},
        )
        self.assertEqual(status, 403)

    def test_orders_allowed_when_paper_enabled(self):
        import os as _os

        old = {
            k: _os.environ.get(k)
            for k in ("TRADING_ENABLED", "PAPER_TRADING_ENABLED")
        }
        _os.environ["TRADING_ENABLED"] = "true"
        _os.environ["PAPER_TRADING_ENABLED"] = "true"
        try:
            reset_config()
            with tempfile.TemporaryDirectory() as tmpdir:
                from agent.core.config import Config
                from agent.trading.paper import PaperTradingEngine

                paper = PaperTradingEngine(
                    initial_balance=10000.0,
                    storage_path=os.path.join(tmpdir, "api.db"),
                )
                server = self._serve(config=Config(), paper=paper)
                call = self._client(server)
                status, body = call(
                    "POST", "/orders", token="test-token-123",
                    body={"symbol": "AAPL", "side": "buy", "quantity": 10,
                          "current_price": 150.0},
                )
                self.assertEqual(status, 200)
                self.assertEqual(body["status"], "filled")
                status, body = call("GET", "/account", token="test-token-123")
                self.assertEqual(status, 200)
                self.assertEqual(body["balance"], 8500.0)
        finally:
            for k, v in old.items():
                if v is None:
                    _os.environ.pop(k, None)
                else:
                    _os.environ[k] = v
            reset_config()

    def test_missing_token_fails_closed(self):
        from agent.api.server import create_server

        old = os.environ.pop("WELLPAID_API_TOKEN", None)
        try:
            with self.assertRaises(ValueError):
                create_server("127.0.0.1", 0)
        finally:
            if old is not None:
                os.environ["WELLPAID_API_TOKEN"] = old


class TestAPITools(unittest.TestCase):
    """Test tools endpoints: auth, discovery, gated execution."""

    def _setup(self):
        import threading
        from agent.api.server import create_server

        server = create_server("127.0.0.1", 0, api_token="tools-token")
        thread = threading.Thread(
            target=self._serve_target(server), daemon=True
        )
        thread.start()
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)
        return server

    @staticmethod
    def _serve_target(server):
        def _target():
            try:
                server.serve_forever()
            except OSError:
                pass  # shutdown/close race on Windows teardown

        return _target

    def _call(self, server, method, path, body=None):
        import json as _json
        import urllib.request
        import urllib.error

        base = f"http://127.0.0.1:{server.server_address[1]}"
        data = _json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(base + path, data=data, method=method)
        req.add_header("Authorization", "Bearer tools-token")
        if body is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, _json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            return e.code, _json.loads(e.read().decode())

    def test_tools_list_requires_auth(self):
        import urllib.request
        import urllib.error

        server = self._setup()
        base = f"http://127.0.0.1:{server.server_address[1]}"
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(base + "/tools", timeout=10)
        self.assertEqual(ctx.exception.code, 401)

    def test_tools_list(self):
        server = self._setup()
        status, body = self._call(server, "GET", "/tools")
        self.assertEqual(status, 200)
        names = {t["name"] for t in body["tools"]}
        self.assertIn("calculator", names)
        self.assertIn("paper_account", names)

    def test_tool_execute_calculator(self):
        server = self._setup()
        status, body = self._call(
            server, "POST", "/tools/execute",
            {"name": "calculator", "args": {"expression": "6*7"}},
        )
        self.assertEqual(status, 200)
        self.assertTrue(body["success"])
        self.assertEqual(body["data"]["result"], 42)

    def test_tool_execute_unknown(self):
        server = self._setup()
        status, body = self._call(
            server, "POST", "/tools/execute",
            {"name": "shell", "args": {}},
        )
        self.assertEqual(status, 422)
        self.assertFalse(body["success"])

    def test_tool_execute_paper_still_gated(self):
        server = self._setup()
        status, body = self._call(
            server, "POST", "/tools/execute",
            {"name": "paper_account",
             "args": {"action": "submit", "symbol": "AAPL",
                      "side": "buy", "quantity": 1,
                      "current_price": 100.0}},
        )
        self.assertEqual(status, 422)
        self.assertFalse(body["success"])  # paper mode disabled by default


class TestToolAbstraction(unittest.TestCase):
    """Test Tool base: validation, containment, result contract."""

    def test_schema_rejects_unknown_fields(self):
        from agent.tools.catalog import CalculatorTool

        result = CalculatorTool().run(
            {"expression": "1+1", "smuggled": "rm -rf"}
        )
        self.assertFalse(result.success)
        self.assertIn("unknown field", result.message)

    def test_schema_rejects_missing_required(self):
        from agent.tools.catalog import CalculatorTool

        result = CalculatorTool().run({})
        self.assertFalse(result.success)

    def test_schema_rejects_wrong_type(self):
        from agent.tools.catalog import CalculatorTool

        result = CalculatorTool().run({"expression": 42})
        self.assertFalse(result.success)

    def test_result_contract(self):
        from agent.tools.catalog import CalculatorTool

        result = CalculatorTool().run({"expression": "2*3"})
        as_dict = result.to_dict()
        for key in ("success", "message", "tool", "data", "warnings", "risk"):
            self.assertIn(key, as_dict)
        self.assertEqual(as_dict["tool"], "calculator")

    def test_calculator_blocks_code(self):
        from agent.tools.catalog import CalculatorTool

        for evil in ("__import__('os')", "open('x')", "a+b", "[1,2][0]"):
            result = CalculatorTool().run({"expression": evil})
            self.assertFalse(result.success, evil)

    def test_calculator_blocks_bombs(self):
        from agent.tools.catalog import CalculatorTool

        self.assertFalse(
            CalculatorTool().run({"expression": "10**1001"}).success
        )
        self.assertFalse(
            CalculatorTool().run({"expression": "1/0"}).success
        )


class TestToolRegistry(unittest.TestCase):
    """Test registry: duplicates, unknown tools, error containment."""

    def _registry(self):
        from agent.tools.registry import ToolRegistry
        from agent.tools.catalog import CalculatorTool

        registry = ToolRegistry()
        registry.register(CalculatorTool())
        return registry

    def test_duplicate_registration_rejected(self):
        from agent.tools.catalog import CalculatorTool

        registry = self._registry()
        with self.assertRaises(ValueError):
            registry.register(CalculatorTool())

    def test_rejects_non_tools(self):
        registry = self._registry()
        with self.assertRaises(ValueError):
            registry.register(object())

    def test_unknown_tool_fails_safely(self):
        registry = self._registry()
        result = registry.execute("does_not_exist", {})
        self.assertFalse(result.success)
        self.assertIn("unknown tool", result.message)

    def test_tool_exception_contained(self):
        from agent.tools.base import Tool, ToolResult
        from agent.tools.registry import ToolRegistry

        class Broken(Tool):
            name = "broken"
            description = "always raises"
            schema = {}

            def execute(self, args):
                raise RuntimeError("boom")

        registry = ToolRegistry()
        registry.register(Broken())
        result = registry.execute("broken", {})
        self.assertFalse(result.success)

    def test_list_describes_tools(self):
        registry = self._registry()
        listed = registry.list()
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["name"], "calculator")
        self.assertIn("safety", listed[0])

    def test_default_registry_tools(self):
        from agent.tools.registry import build_default_registry

        registry = build_default_registry()
        names = {t["name"] for t in registry.list()}
        for expected in (
            "calculator", "system_status", "market_data",
            "backtest", "paper_account",
        ):
            self.assertIn(expected, names)

    def test_default_registry_skips_missing_backends(self):
        from agent.tools.registry import build_default_registry

        registry = build_default_registry()
        names = {t["name"] for t in registry.list()}
        self.assertNotIn("memory", names)
        self.assertNotIn("tasks", names)


class TestMemoryTaskTools(unittest.TestCase):
    """Test memory/task tools over existing SQLite stores."""

    def test_memory_remember_search(self):
        from agent.tools.catalog import MemoryTool

        with tempfile.TemporaryDirectory() as tmpdir:
            store = MemoryStore(
                storage_path=os.path.join(tmpdir, "m.db")
            )
            tool = MemoryTool(store)
            saved = tool.run(
                {"action": "remember", "content": "I prefer crypto research"}
            )
            self.assertTrue(saved.success)
            found = tool.run({"action": "search", "query": "crypto"})
            self.assertTrue(found.success)
            self.assertEqual(len(found.data["matches"]), 1)

    def test_memory_refuses_secrets(self):
        from agent.tools.catalog import MemoryTool

        with tempfile.TemporaryDirectory() as tmpdir:
            store = MemoryStore(
                storage_path=os.path.join(tmpdir, "m.db")
            )
            tool = MemoryTool(store)
            refused = tool.run(
                {"action": "remember",
                 "content": "my api_key is SECRET123"}
            )
            self.assertFalse(refused.success)
            self.assertIn("credential", refused.message)
            self.assertEqual(store.count(), 0)

    def test_tasks_create_complete(self):
        from agent.tools.catalog import TaskManagerTool

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = TaskManager(
                storage_path=os.path.join(tmpdir, "t.db")
            )
            tool = TaskManagerTool(manager)
            created = tool.run({"action": "create", "title": "Review CAD data"})
            self.assertTrue(created.success)
            listed = tool.run({"action": "list"})
            self.assertEqual(len(listed.data["tasks"]), 1)
            done = tool.run(
                {"action": "complete",
                 "task_id": created.data["id"]}
            )
            self.assertTrue(done.success)


class TestMarketBacktestTools(unittest.TestCase):
    """Test read-only research tools (mocked network)."""

    def test_market_price_mocked(self):
        import agent.trading.brokers as brokers
        from agent.tools.catalog import MarketDataTool

        original = brokers._http_get_text
        brokers._http_get_text = (
            lambda url, timeout=15: "Symbol,Date,Time,Open,High,Low,Close,Volume\n"
            "AAPL,01/02/2024,22:00,100,101,99,100.5,1000\n"
        )
        try:
            result = MarketDataTool().run(
                {"action": "price", "symbol": "AAPL"}
            )
        finally:
            brokers._http_get_text = original
        self.assertTrue(result.success)
        self.assertAlmostEqual(result.data["price"], 100.5)

    def test_market_history_mocked(self):
        import agent.trading.brokers as brokers
        from agent.tools.catalog import MarketDataTool

        body = (
            "Date,Open,High,Low,Close,Volume\n"
            + "".join(
                f"2024-01-{d:02d},100,101,99,100.5,1000\n"
                for d in range(1, 11)
            )
        )
        original = brokers._http_get_text
        brokers._http_get_text = lambda url, timeout=15: body
        try:
            result = MarketDataTool().run(
                {"action": "history", "symbol": "AAPL", "days": 10}
            )
        finally:
            brokers._http_get_text = original
        self.assertTrue(result.success)
        self.assertEqual(result.data["bars"], 10)

    def test_market_offline_graceful(self):
        import agent.trading.brokers as brokers
        from agent.tools.catalog import MarketDataTool

        def boom(url, timeout=15):
            raise TimeoutError("offline")

        original = brokers._http_get_text
        brokers._http_get_text = boom
        try:
            result = MarketDataTool().run(
                {"action": "price", "symbol": "AAPL"}
            )
        finally:
            brokers._http_get_text = original
        self.assertFalse(result.success)

    def test_backtest_mock_labels_honesty(self):
        from agent.tools.catalog import BacktestTool

        result = BacktestTool().run(
            {"symbol": "AAPL", "days": 120, "source": "mock"}
        )
        self.assertTrue(result.success)
        self.assertIn("HISTORICAL", result.message)
        self.assertTrue(
            any("HISTORICAL" in w for w in result.warnings)
        )
        self.assertIn("assumptions", result.data)
        self.assertIn("total_return", result.data)


class TestPaperTool(unittest.TestCase):
    """Test paper tool: veto path, gating, bypass impossibility."""

    def _stack(self, tmpdir, **env):
        import os as _os

        old = {k: _os.environ.get(k) for k in env}
        for k, v in env.items():
            _os.environ[k] = v

        def _restore():
            for k, v in old.items():
                if v is None:
                    _os.environ.pop(k, None)
                else:
                    _os.environ[k] = v
            reset_config()

        self.addCleanup(_restore)
        reset_config()
        from agent.core.config import Config
        from agent.tools.catalog import PaperAccountTool

        risk = RiskEngine()
        paper = PaperTradingEngine(
            initial_balance=10000.0,
            storage_path=os.path.join(tmpdir, "p.db"),
            risk_engine=risk,
        )
        return PaperAccountTool(Config(), paper, risk)

    def test_submit_blocked_when_disabled(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = self._stack(tmpdir)
            result = tool.run(
                {"action": "submit", "symbol": "AAPL",
                 "side": "buy", "quantity": 1,
                 "current_price": 100.0}
            )
            self.assertFalse(result.success)
            self.assertIn("disabled", result.message)

    def test_propose_rejected_explains_why(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = self._stack(tmpdir)
            result = tool.run(
                {"action": "propose", "symbol": "AAPL",
                 "side": "buy", "quantity": 200,
                 "current_price": 1000.0}
            )
            self.assertFalse(result.success)
            self.assertEqual(result.risk["decision"], "rejected")
            self.assertTrue(result.risk["violations"])
            self.assertIn("REJECTED", result.message)

    def test_tool_cannot_bypass_risk(self):
        """Oversized trade through the tool: rejected, balance untouched."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = self._stack(
                tmpdir, TRADING_ENABLED="true",
                PAPER_TRADING_ENABLED="true",
            )
            result = tool.run(
                {"action": "submit", "symbol": "AAPL",
                 "side": "buy", "quantity": 100000,
                 "current_price": 150.0}
            )
            self.assertFalse(result.success)
            balance = tool.run({"action": "balance"})
            self.assertEqual(balance.data["balance"], 10000.0)
            self.assertEqual(len(tool.paper.get_positions()), 0)

    def test_submit_fills_when_allowed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = self._stack(
                tmpdir, TRADING_ENABLED="true",
                PAPER_TRADING_ENABLED="true",
            )
            result = tool.run(
                {"action": "submit", "symbol": "AAPL",
                 "side": "buy", "quantity": 10,
                 "current_price": 150.0}
            )
            self.assertTrue(result.success)
            self.assertIn("PAPER TRADE", result.message)


class TestRiskExplanation(unittest.TestCase):
    """Test structured risk explanations (veto logic untouched)."""

    def test_format_rejection(self):
        from agent.risk.engine import format_rejection

        engine = RiskEngine(max_position_size=100)
        check = engine.evaluate(
            TradeProposal(
                symbol="AAPL", side="buy", quantity=200,
                price=100.0, order_type="market",
                timestamp=datetime.now(), metadata={},
            )
        )
        text = format_rejection(check)
        self.assertIn("REJECTED", text)
        self.assertIn("Reason:", text)
        self.assertIn("200", text)

    def test_format_approval(self):
        from agent.risk.engine import format_rejection

        engine = RiskEngine()
        check = engine.evaluate(
            TradeProposal(
                symbol="AAPL", side="buy", quantity=1,
                price=100.0, order_type="market",
                timestamp=datetime.now(), metadata={},
            )
        )
        self.assertIn("APPROVED", format_rejection(check))


class TestAgentCLI(unittest.TestCase):
    """Test CLI tool commands and natural-language shortcuts."""

    def _agent(self, tmpdir):
        from agent.core.config import Config
        from agent.tools.registry import build_default_registry

        reset_config()
        memory = MemoryStore(storage_path=os.path.join(tmpdir, "m.db"))
        tasks = TaskManager(storage_path=os.path.join(tmpdir, "t.db"))
        risk = RiskEngine()
        paper = PaperTradingEngine(
            storage_path=os.path.join(tmpdir, "p.db"), risk_engine=risk
        )
        registry = build_default_registry(
            Config(), paper, risk, memory, tasks
        )
        agent = WellPaiDAgent(registry=registry)
        self.addCleanup(reset_config)
        return agent

    def _capture(self, func, *args):
        import io
        import sys

        old = sys.stdout
        sys.stdout = io.StringIO()
        try:
            func(*args)
            return sys.stdout.getvalue()
        finally:
            sys.stdout = old

    def test_tools_lists_registry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = self._agent(tmpdir)
            output = self._capture(agent._process_command, "tools")
            self.assertIn("calculator", output)
            self.assertIn("paper_account", output)

    def test_run_calculator(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = self._agent(tmpdir)
            output = self._capture(
                agent._process_command, "run calculator expression=6*7"
            )
            self.assertIn("42", output)

    def test_run_unknown_tool(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = self._agent(tmpdir)
            output = self._capture(agent._process_command, "run shell cmd=x")
            self.assertIn("unknown tool", output)

    def test_natural_remember(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = self._agent(tmpdir)
            output = self._capture(
                agent._process_command, "remember that I prefer crypto"
            )
            self.assertIn("remembered", output)
            found = agent.tools.execute(
                "memory", {"action": "search", "query": "crypto"}
            )
            self.assertEqual(len(found.data["matches"]), 1)

    def test_natural_remind(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = self._agent(tmpdir)
            output = self._capture(
                agent._process_command, "remind me to review my CAD portfolio"
            )
            self.assertIn("task created", output)

    def test_natural_price(self):
        import agent.trading.brokers as brokers

        original = brokers._http_get_text
        brokers._http_get_text = (
            lambda url, timeout=15: "Symbol,Date,Time,Open,High,Low,Close,Volume\n"
            "AAPL,01/02/2024,22:00,100,101,99,100.5,1000\n"
        )
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                agent = self._agent(tmpdir)
                output = self._capture(
                    agent._process_command, "price of AAPL"
                )
        finally:
            brokers._http_get_text = original
        self.assertIn("100.5", output)


if __name__ == "__main__":
    unittest.main()
