import pytest

from backend.domain import AssetClass
from backend.extensions import db
from backend.models.scan import ScanHistory, ScanResult
from backend.models.universe import UniverseSymbol
from backend.services import scans
from backend.services.universe.providers import StaticUniverseProvider
from backend.services.universe.registry import (
    DuplicateUniverseError,
    UniverseRegistry,
    registry,
    resolve_scan_universe,
)


def _bars(marker):
    return [
        {
            "t": index,
            "o": marker,
            "h": marker + 1,
            "l": marker - 1,
            "c": marker,
            "v": 1000,
        }
        for index in range(140)
    ]


def _analysis_for_marker(marker):
    macd_line = 2.0 if marker == 2 else 0.0
    return {
        "price": {
            "last": 100,
            "change_pct": 0,
            "open": 100,
            "high": 101,
            "low": 99,
            "volume": 1000,
        },
        "indicators": {
            "rsi": 25,
            "macd": {"line": macd_line, "signal": 1.0, "histogram": 0},
            "ema": {"ema_9": None, "ema_20": None, "ema_50": None, "ema_200": None},
            "sma": {"sma_20": None, "sma_50": None, "sma_200": None},
            "bollinger_bands": {"upper": None, "middle": None, "lower": None},
            "stochastic": {"k": None, "d": None},
        },
        "fibonacci": None,
        "patterns": {"candlestick": [], "chart": []},
        "signals": [],
        "overall_signal": "bullish",
        "trade_setup": None,
    }


def test_registry_defaults_and_asset_validation(app):
    assert registry.default_key(AssetClass.EQUITY) == "us_stocks_top"
    assert registry.default_key(AssetClass.CRYPTO) == "crypto_static"

    with app.app_context():
        db.session.add_all(
            [
                UniverseSymbol(
                    symbol="AAPL",
                    asset_class="equity",
                    venue="XNAS",
                    universe_key="nasdaq_top",
                    exchange="NASDAQ",
                    avg_daily_volume=2000,
                    rank=1,
                ),
                UniverseSymbol(
                    symbol="JPM",
                    asset_class="equity",
                    venue="XNYS",
                    universe_key="nyse_top",
                    exchange="NYSE",
                    avg_daily_volume=1500,
                    rank=1,
                ),
            ]
        )
        db.session.commit()

        assert resolve_scan_universe(AssetClass.EQUITY).symbols == ("AAPL", "JPM")
        assert resolve_scan_universe(AssetClass.EQUITY, "nasdaq_top").symbols == (
            "AAPL",
        )
        assert resolve_scan_universe(AssetClass.EQUITY, "nyse_top").symbols == (
            "JPM",
        )

    with pytest.raises(ValueError, match="does not support crypto"):
        registry.validate(AssetClass.CRYPTO, "nyse_top")


def test_registry_rejects_duplicate_universe_keys():
    local = UniverseRegistry()
    provider = StaticUniverseProvider(
        "test_static", AssetClass.CRYPTO, "Test", ("X:BTCUSD",)
    )
    local.register(provider, default=True)
    with pytest.raises(DuplicateUniverseError):
        local.register(provider)


def test_global_result_cap_allows_later_nyse_candidate_to_win(
    app, fake_provider, monkeypatch
):
    fake_provider.bars_by_symbol = {
        "AAPL": _bars(1),
        "JPM": _bars(2),
    }
    monkeypatch.setattr(
        scans.ta,
        "full_analysis",
        lambda bars, features=None, timeframe=None: _analysis_for_marker(bars[0]["c"]),
    )

    with app.app_context():
        db.session.add_all(
            [
                UniverseSymbol(
                    symbol="AAPL",
                    asset_class="equity",
                    venue="XNAS",
                    universe_key="nasdaq_top",
                    exchange="NASDAQ",
                    avg_daily_volume=2000,
                    rank=1,
                ),
                UniverseSymbol(
                    symbol="JPM",
                    asset_class="equity",
                    venue="XNYS",
                    universe_key="nyse_top",
                    exchange="NYSE",
                    avg_daily_volume=1500,
                    rank=1,
                ),
            ]
        )
        db.session.commit()

        payload = scans.scan_market(
            "stocks",
            ["rsi_oversold", "macd_bullish"],
            "1D",
            1,
            universe_key="us_stocks_top",
        )
        persisted = ScanResult.query.all()
        history = ScanHistory.query.one()

    assert payload["meta"]["total_attempted"] == 2
    assert payload["meta"]["total_candidate_matches"] == 2
    assert payload["meta"]["total_matched"] == 1
    assert [result["provider_symbol"] for result in payload["results"]] == ["JPM"]
    assert [row.provider_symbol for row in persisted] == ["JPM"]
    assert history.total_scanned == 2
    assert history.total_matched == 1
