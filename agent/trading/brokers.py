"""WellPaiD Trader - Read-only market data providers.

RESEARCH ONLY - no order execution, no trading endpoints, no credentials.

These providers fetch public market data over HTTPS with the standard
library only (urllib, no API keys required):

- StooqDataProvider: global stocks/ETFs/forex via Stooq free CSV feeds.
- CoinbaseDataProvider: crypto spot prices and candles via Coinbase
  public market-data endpoints.

Read-only guarantee: every URL below is a public quote/history path.
No provider in this module calls any order, account, or trading endpoint,
and none accepts or stores credentials.
"""

import csv
import io
import json
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Optional

try:
    from agent.trading.research import (
        AssetType,
        DataProvider,
        MarketData,
        OHLCV,
    )
except ImportError:
    from .research import (
        AssetType,
        DataProvider,
        MarketData,
        OHLCV,
    )

_HTTP_TIMEOUT = 15
_USER_AGENT = "WellPaiD-Trader/0.3 (research; read-only market data)"


def _http_get_text(url: str, timeout: int = _HTTP_TIMEOUT) -> str:
    """GET a URL and return the decoded body."""
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def _parse_decimal(value: str) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class StooqDataProvider(DataProvider):
    """Global stock/ETF/forex quotes and daily history via Stooq.

    Symbol format: "AAPL" defaults to the US listing ("aapl.us").
    Pass a qualified symbol ("siemens.de", "7203.jp") for other venues,
    or forex pairs ("eurusd").
    """

    QUOTE_URL = "https://stooq.com/q/l/?s={symbols}&f=sd2t2ohlcv&h&e=csv"
    HISTORY_URL = (
        "https://stooq.com/q/d/l/?s={symbol}&d1={start}&d2={end}&i=d"
    )

    def normalize_symbol(self, symbol: str) -> str:
        """Map a bare symbol to a Stooq-qualified listing."""
        cleaned = symbol.strip().lower()
        if not cleaned:
            raise ValueError("Empty symbol")
        if "." not in cleaned and not (
            len(cleaned) == 6 and cleaned.isalpha()
        ):
            cleaned += ".us"
        return cleaned

    def get_historical_data(
        self,
        symbol: str,
        asset_type: AssetType,
        start_date: datetime,
        end_date: datetime,
    ) -> Optional[MarketData]:
        """Fetch daily OHLCV bars between two dates (inclusive)."""
        if asset_type not in (
            AssetType.STOCK,
            AssetType.INDEX,
            AssetType.FOREX,
            AssetType.COMMODITY,
        ):
            return None
        try:
            stooq_symbol = self.normalize_symbol(symbol)
        except ValueError:
            return None
        url = self.HISTORY_URL.format(
            symbol=urllib.parse.quote(stooq_symbol),
            start=start_date.strftime("%Y%m%d"),
            end=end_date.strftime("%Y%m%d"),
        )
        try:
            body = _http_get_text(url)
        except Exception:
            return None
        rows = list(csv.DictReader(io.StringIO(body)))
        data = []
        for row in rows:
            try:
                timestamp = datetime.strptime(row["Date"], "%Y-%m-%d")
            except (KeyError, ValueError):
                continue
            open_ = _parse_decimal(row.get("Open", ""))
            high = _parse_decimal(row.get("High", ""))
            low = _parse_decimal(row.get("Low", ""))
            close = _parse_decimal(row.get("Close", ""))
            volume = _parse_decimal(row.get("Volume", "")) or 0.0
            if None in (open_, high, low, close):
                continue
            data.append(
                OHLCV(
                    timestamp=timestamp,
                    open=open_,
                    high=high,
                    low=low,
                    close=close,
                    volume=volume,
                )
            )
        if not data:
            return None
        return MarketData(
            symbol=symbol,
            asset_type=asset_type,
            data=data,
            metadata={
                "source": "stooq",
                "stooq_symbol": stooq_symbol,
                "generated": datetime.now().isoformat(),
            },
        )

    def get_current_price(
        self, symbol: str, asset_type: AssetType
    ) -> Optional[float]:
        """Fetch the latest quoted close price."""
        try:
            stooq_symbol = self.normalize_symbol(symbol)
        except ValueError:
            return None
        url = self.QUOTE_URL.format(
            symbols=urllib.parse.quote(stooq_symbol)
        )
        try:
            body = _http_get_text(url)
        except Exception:
            return None
        rows = list(csv.DictReader(io.StringIO(body)))
        if not rows:
            return None
        return _parse_decimal(rows[0].get("Close", ""))


class CoinbaseDataProvider(DataProvider):
    """Crypto spot prices and daily candles via Coinbase public endpoints.

    Symbol format: "BTC" or "BTC-USD". Bare codes default to USD.
    """

    SPOT_URL = "https://api.coinbase.com/v2/prices/{pair}/spot"
    CANDLES_URL = (
        "https://api.exchange.coinbase.com/products/{pair}/candles"
        "?granularity=86400&start={start}&end={end}"
    )

    def normalize_pair(self, symbol: str) -> str:
        """Map a bare code to a Coinbase product pair."""
        cleaned = symbol.strip().upper().replace("/", "-")
        if not cleaned:
            raise ValueError("Empty symbol")
        if "-" not in cleaned:
            cleaned += "-USD"
        return cleaned

    def get_historical_data(
        self,
        symbol: str,
        asset_type: AssetType,
        start_date: datetime,
        end_date: datetime,
    ) -> Optional[MarketData]:
        """Fetch daily candles between two dates (inclusive)."""
        if asset_type != AssetType.CRYPTO:
            return None
        try:
            pair = self.normalize_pair(symbol)
        except ValueError:
            return None
        url = self.CANDLES_URL.format(
            pair=urllib.parse.quote(pair),
            start=start_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            end=end_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        try:
            body = _http_get_text(url)
            raw = json.loads(body)
        except Exception:
            return None
        if not isinstance(raw, list):
            return None
        data = []
        # Coinbase returns [time, low, high, open, close, volume], newest first.
        for entry in sorted(raw, key=lambda e: e[0]):
            try:
                timestamp = datetime.fromtimestamp(int(entry[0]))
                low, high, open_, close, volume = (
                    float(entry[1]),
                    float(entry[2]),
                    float(entry[3]),
                    float(entry[4]),
                    float(entry[5]),
                )
            except (IndexError, TypeError, ValueError):
                continue
            data.append(
                OHLCV(
                    timestamp=timestamp,
                    open=open_,
                    high=high,
                    low=low,
                    close=close,
                    volume=volume,
                )
            )
        if not data:
            return None
        return MarketData(
            symbol=symbol,
            asset_type=asset_type,
            data=data,
            metadata={
                "source": "coinbase",
                "pair": pair,
                "generated": datetime.now().isoformat(),
            },
        )

    def get_current_price(
        self, symbol: str, asset_type: AssetType
    ) -> Optional[float]:
        """Fetch the latest spot price."""
        try:
            pair = self.normalize_pair(symbol)
        except ValueError:
            return None
        url = self.SPOT_URL.format(pair=urllib.parse.quote(pair))
        try:
            body = _http_get_text(url)
            payload = json.loads(body)
        except Exception:
            return None
        try:
            return float(payload["data"]["amount"])
        except (KeyError, TypeError, ValueError):
            return None
