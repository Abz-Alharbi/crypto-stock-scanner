from datetime import date, datetime, timedelta

import pytest

from backend.extensions import db
from backend.models.universe import UniverseSymbol
from backend.providers import ProviderError
from backend.services.universe import universe_builder


def test_build_and_save_universe_ranks_common_stocks_by_average_volume(app, monkeypatch, fake_provider):
    fake_provider.reference_results.update(
        {
            "XNAS": [
                {"ticker": "AAA", "type": "CS"},
                {"ticker": "BBB", "type": "CS"},
                {"ticker": "QQQ", "type": "ETF"},
            ],
            "XNYS": [
                {"ticker": "CCC", "type": "CS"},
                {"ticker": "DDD", "type": "CS"},
            ],
        }
    )
    grouped_rows = [
        {"T": "AAA", "v": 1000},
        {"T": "BBB", "v": 5000},
        {"T": "CCC", "v": 3000},
        {"T": "DDD", "v": 100},
        {"T": "QQQ", "v": 999999},
    ]
    fake_provider.grouped_daily_results.update(
        {
            "2026-01-01": grouped_rows,
            "2026-01-02": [],
            "2026-01-03": grouped_rows,
        }
    )
    monkeypatch.setattr(
        universe_builder,
        "_date_range",
        lambda _days: [date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3)],
    )
    app.config.update(UNIVERSE_NASDAQ_SIZE=2, UNIVERSE_NYSE_SIZE=1, UNIVERSE_LOOKBACK_DAYS=3)

    with app.app_context():
        payload = universe_builder.build_and_save_universe()
        rows = UniverseSymbol.query.order_by(UniverseSymbol.exchange, UniverseSymbol.rank).all()

    assert payload["reference_counts"] == {"NASDAQ": 2, "NYSE": 2}
    assert payload["processed_days"] == 2
    assert payload["skipped_days"] == 1
    assert payload["final_counts"] == {"NASDAQ": 2, "NYSE": 1}
    assert [(row.exchange, row.rank, row.symbol) for row in rows] == [
        ("NASDAQ", 1, "BBB"),
        ("NASDAQ", 2, "AAA"),
        ("NYSE", 1, "CCC"),
    ]
    assert all(row.asset_class == "equity" for row in rows)
    assert [(row.venue, row.universe_key) for row in rows] == [
        ("XNAS", "nasdaq_top"),
        ("XNAS", "nasdaq_top"),
        ("XNYS", "nyse_top"),
    ]


def test_universe_status_payload_counts_rows(app):
    with app.app_context():
        computed_at = datetime(2026, 1, 1, 12, 0, 0)
        db.session.add_all(
            [
                UniverseSymbol(symbol="AAA", exchange="NASDAQ", avg_daily_volume=1000, rank=1, computed_at=computed_at),
                UniverseSymbol(symbol="CCC", exchange="NYSE", avg_daily_volume=3000, rank=1, computed_at=computed_at),
            ]
        )
        db.session.commit()

        payload = universe_builder.status_payload()

    assert {key: payload[key] for key in (
        "total_symbols",
        "nasdaq_count",
        "nyse_count",
        "last_computed_at",
    )} == {
        "total_symbols": 2,
        "nasdaq_count": 1,
        "nyse_count": 1,
        "last_computed_at": "2026-01-01T12:00:00",
    }
    assert payload["universes"]["us_stocks_top"]["count"] == 2
    assert payload["universes"]["nasdaq_top"]["count"] == 1
    assert payload["universes"]["nyse_top"]["count"] == 1
    assert payload["universes"]["crypto_static"] == {
        "key": "crypto_static",
        "name": "Crypto Top USD Pairs",
        "asset_class": "crypto",
        "count": 15,
        "source": "fallback",
        "degraded": True,
        "degraded_reason": "stored universe is empty",
        "last_computed_at": None,
    }


def test_universe_status_route(client, app):
    with app.app_context():
        db.session.add(
            UniverseSymbol(symbol="AAA", exchange="NASDAQ", avg_daily_volume=1000, rank=1, computed_at=datetime.utcnow())
        )
        db.session.commit()

    response = client.get("/api/universe/status")

    assert response.status_code == 200
    assert response.get_json()["total_symbols"] == 1


def test_health_payload_reports_active_and_fallback_universe_counts(client, app):
    with app.app_context():
        computed_at = datetime(2026, 1, 2, 12, 0, 0)
        db.session.add_all(
            [
                UniverseSymbol(symbol="AAA", exchange="NASDAQ", avg_daily_volume=1000, rank=1, computed_at=computed_at),
                UniverseSymbol(symbol="CCC", exchange="NYSE", avg_daily_volume=900, rank=1, computed_at=computed_at),
            ]
        )
        db.session.commit()

    response = client.get("/api/health")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["stock_symbols"] == 2
    assert payload["crypto_symbols"] == 15
    assert payload["fallback_stock_symbols"] == 80
    assert payload["fallback_crypto_symbols"] == 15
    assert payload["universe_counts"]["stocks"] == {
        "active": 2,
        "dynamic": 2,
        "fallback": 80,
        "using_fallback": False,
        "nasdaq": 1,
        "nyse": 1,
        "last_computed_at": "2026-01-02T12:00:00",
    }
    assert payload["universe_counts"]["crypto"] == {
        "active": 15,
        "dynamic": 0,
        "fallback": 15,
        "using_fallback": True,
        "last_computed_at": None,
    }


def test_persisted_crypto_rows_do_not_change_equity_health_payload(client, app):
    with app.app_context():
        computed_at = datetime(2026, 1, 2, 12, 0, 0)
        db.session.add_all(
            [
                UniverseSymbol(
                    symbol="AAA",
                    exchange="NASDAQ",
                    avg_daily_volume=1000,
                    rank=1,
                    computed_at=computed_at,
                ),
                UniverseSymbol(
                    symbol="CCC",
                    exchange="NYSE",
                    avg_daily_volume=900,
                    rank=1,
                    computed_at=computed_at,
                ),
            ]
        )
        db.session.commit()

    before = client.get("/api/health").get_json()

    with app.app_context():
        db.session.add(
            UniverseSymbol(
                symbol="X:BTCUSD",
                asset_class="crypto",
                venue="GLOBAL_CRYPTO",
                quote_currency="USD",
                universe_key="crypto_static",
                avg_daily_volume=10_000_000,
                rank=1,
                computed_at=datetime(2026, 1, 3, 12, 0, 0),
            )
        )
        db.session.commit()

    after = client.get("/api/health").get_json()

    assert after["stock_symbols"] == before["stock_symbols"]
    assert after["fallback_stock_symbols"] == before["fallback_stock_symbols"]
    assert after["universe_counts"]["stocks"] == before["universe_counts"]["stocks"]


def test_crypto_only_refresh_replaces_crypto_rows_without_touching_equities(
    app, monkeypatch, fake_provider
):
    """The Phase 8 critical regression: crypto replacement is strictly scoped."""
    symbols = [f"X:C{index:03d}USD" for index in range(101)]
    fake_provider.reference_results["crypto"] = [
        {
            "ticker": symbol,
            "currency_symbol": "USD",
            "base_currency_symbol": symbol.removeprefix("X:").removesuffix("USD"),
        }
        for symbol in symbols
    ] + [
        {
            "ticker": "X:RAWUSD",
            "currency_symbol": "USD",
            "base_currency_symbol": "RAW",
        },
        {
            "ticker": "X:BTCEUR",
            "currency_symbol": "EUR",
            "base_currency_symbol": "BTC",
        },
    ]
    dates = [date(2026, 1, 1) + timedelta(days=index) for index in range(90)]
    fake_provider.grouped_daily_crypto_results.update(
        {
            day.isoformat(): [
                {"T": symbol, "v": 1, "vw": 200_000 - index}
                for index, symbol in enumerate(symbols)
            ]
            for day in dates
        }
    )
    # Raw token volume is much larger, but USD notional is deliberately lower.
    for rows in fake_provider.grouped_daily_crypto_results.values():
        rows.append({"T": "X:RAWUSD", "v": 1_000_000, "vw": 0.01})
    monkeypatch.setattr(
        universe_builder,
        "_date_range",
        lambda _days: dates,
    )
    app.config.update(
        UNIVERSE_CRYPTO_SIZE=100,
        UNIVERSE_CRYPTO_LOOKBACK_DAYS=90,
    )

    with app.app_context():
        equity_time = datetime(2025, 12, 31, 12, 0, 0)
        equity = UniverseSymbol(
            symbol="AAPL",
            asset_class="equity",
            venue="XNAS",
            universe_key="nasdaq_top",
            exchange="NASDAQ",
            avg_daily_volume=1234,
            rank=1,
            computed_at=equity_time,
        )
        db.session.add_all(
            [
                equity,
                UniverseSymbol(
                    symbol="X:OLDUSD",
                    asset_class="crypto",
                    venue="GLOBAL_CRYPTO",
                    quote_currency="USD",
                    universe_key="crypto_static",
                    avg_daily_volume=1,
                    rank=1,
                ),
            ]
        )
        db.session.commit()
        equity_before = equity.to_dict()

        payload = universe_builder.build_and_save_crypto_universe()

        equity_after = UniverseSymbol.query.filter_by(symbol="AAPL").one().to_dict()
        crypto_rows = (
            UniverseSymbol.query.filter_by(asset_class="crypto")
            .order_by(UniverseSymbol.rank)
            .all()
        )

    assert payload["status"] == "healthy"
    assert payload["lookback_days"] == 90
    assert payload["ranking_metric"] == "average_daily_usd_notional_volume"
    assert equity_after == equity_before
    assert len(crypto_rows) == 100
    assert crypto_rows[0].symbol == "X:C000USD"
    assert crypto_rows[0].avg_daily_volume == pytest.approx(200_000)
    assert all(row.quote_currency == "USD" for row in crypto_rows)
    assert "X:OLDUSD" not in {row.symbol for row in crypto_rows}
    assert "X:BTCEUR" not in {row.symbol for row in crypto_rows}


def test_empty_crypto_rebuild_serves_static_fallback_with_degraded_state(
    app, monkeypatch
):
    monkeypatch.setattr(
        universe_builder,
        "_date_range",
        lambda _days: [date(2026, 1, 1)],
    )
    app.config.update(UNIVERSE_CRYPTO_SIZE=100, UNIVERSE_CRYPTO_LOOKBACK_DAYS=90)

    with app.app_context():
        payload = universe_builder.build_and_save_crypto_universe()
        status = universe_builder.status_payload()["universes"]["crypto_static"]

    assert payload["status"] == "degraded"
    assert payload["retained_previous"] is True
    assert "candidate universe is empty" in payload["degraded_reason"]
    assert status["source"] == "fallback"
    assert status["degraded"] is True
    assert status["degraded_reason"] == "stored universe is empty"
    assert status["count"] == 15


def test_crypto_rebuild_rejects_partial_lookback_instead_of_persisting_it(
    app, monkeypatch, fake_provider
):
    fake_provider.reference_results["crypto"] = [
        {
            "ticker": "X:BTCUSD",
            "currency_symbol": "USD",
            "base_currency_symbol": "BTC",
        }
    ]
    fake_provider.grouped_daily_crypto_results.update(
        {
            "2026-01-01": [{"T": "X:BTCUSD", "v": 2, "vw": 50_000}],
            "2026-01-02": [{"T": "X:BTCUSD", "v": 3, "vw": 50_000}],
            "2026-01-03": [],
        }
    )
    monkeypatch.setattr(
        universe_builder,
        "_date_range",
        lambda _days: [
            date(2026, 1, 1),
            date(2026, 1, 2),
            date(2026, 1, 3),
        ],
    )
    app.config.update(UNIVERSE_CRYPTO_SIZE=1, UNIVERSE_CRYPTO_LOOKBACK_DAYS=3)

    with app.app_context():
        payload = universe_builder.build_and_save_crypto_universe()
        stored_count = UniverseSymbol.query.filter_by(asset_class="crypto").count()

    assert payload["status"] == "degraded"
    assert "processed 2 days; required 3" in payload["degraded_reason"]
    assert stored_count == 0


def test_crypto_rebuild_retries_only_failed_dates_before_persisting(
    app, monkeypatch, fake_provider
):
    fake_provider.reference_results["crypto"] = [
        {
            "ticker": "X:BTCUSD",
            "currency_symbol": "USD",
            "base_currency_symbol": "BTC",
        }
    ]
    attempts = {}

    def grouped(day):
        attempts[day] = attempts.get(day, 0) + 1
        if day == "2026-01-02" and attempts[day] == 1:
            return []
        return [{"T": "X:BTCUSD", "v": 2, "vw": 50_000}]

    monkeypatch.setattr(fake_provider, "grouped_daily_crypto", grouped)
    monkeypatch.setattr(
        universe_builder,
        "_date_range",
        lambda _days: [
            date(2026, 1, 1),
            date(2026, 1, 2),
            date(2026, 1, 3),
        ],
    )
    app.config.update(
        UNIVERSE_CRYPTO_SIZE=1,
        UNIVERSE_CRYPTO_LOOKBACK_DAYS=3,
        UNIVERSE_CRYPTO_DATE_MAX_ATTEMPTS=2,
    )

    with app.app_context():
        payload = universe_builder.build_and_save_crypto_universe()

    assert payload["status"] == "healthy"
    assert payload["processed_days"] == 3
    assert payload["skipped_days"] == 0
    assert attempts == {
        "2026-01-01": 1,
        "2026-01-02": 2,
        "2026-01-03": 1,
    }


def test_crypto_ranking_averages_notional_over_the_full_window(app):
    app.config["UNIVERSE_CRYPTO_SIZE"] = 2
    with app.app_context():
        rows, counts = universe_builder.rank_crypto_symbols(
            {"X:ESTABLISHEDUSD", "X:NEWUSD"},
            {"X:ESTABLISHEDUSD": 900, "X:NEWUSD": 100},
            {"X:ESTABLISHEDUSD": 90, "X:NEWUSD": 1},
            datetime.utcnow(),
            window_days=90,
        )

    assert counts == {"crypto_static": 2}
    assert [row.symbol for row in rows] == ["X:ESTABLISHEDUSD", "X:NEWUSD"]
    assert [row.avg_daily_volume for row in rows] == pytest.approx([10, 100 / 90])


def test_empty_universe_candidate_retains_good_rows(app):
    with app.app_context():
        db.session.add(
            UniverseSymbol(symbol="AAA", exchange="NASDAQ", avg_daily_volume=1000, rank=1, computed_at=datetime.utcnow())
        )
        db.session.commit()

        with pytest.raises(
            universe_builder.UniverseCandidateError,
            match="candidate universe is empty",
        ):
            universe_builder.save_universe([])

        assert UniverseSymbol.query.count() == 1
        assert universe_builder.get_scan_universe_symbols(["AAPL", "MSFT"]) == ["AAA"]


def test_undersized_rebuild_retains_last_known_good_rows(
    app, monkeypatch, fake_provider
):
    app.config.update(
        UNIVERSE_NASDAQ_SIZE=2,
        UNIVERSE_NYSE_SIZE=1,
        UNIVERSE_LOOKBACK_DAYS=1,
    )
    fake_provider.reference_results.update(
        {
            "XNAS": [{"ticker": "NEW", "type": "CS"}],
            "XNYS": [{"ticker": "NY", "type": "CS"}],
        }
    )
    fake_provider.grouped_daily_results["2026-01-01"] = [
        {"T": "NEW", "v": 5000},
        {"T": "NY", "v": 4000},
    ]
    monkeypatch.setattr(
        universe_builder,
        "_date_range",
        lambda _days: [date(2026, 1, 1)],
    )

    with app.app_context():
        db.session.add(
            UniverseSymbol(
                symbol="LKG",
                exchange="NASDAQ",
                avg_daily_volume=1000,
                rank=1,
            )
        )
        db.session.commit()

        payload = universe_builder.build_and_save_universe()
        stored = [row.symbol for row in UniverseSymbol.query.all()]

    assert payload["status"] == "degraded"
    assert payload["retained_previous"] is True
    assert "NASDAQ count 1 is below required 2" in payload["degraded_reason"]
    assert stored == ["LKG"]


def test_stale_candidate_retains_last_known_good_rows(app):
    app.config.update(
        UNIVERSE_NASDAQ_SIZE=1,
        UNIVERSE_NYSE_SIZE=1,
        UNIVERSE_MAX_CANDIDATE_AGE_SECONDS=60,
    )
    stale_at = datetime(2020, 1, 1)
    candidate = [
        UniverseSymbol(
            symbol="NEWNAS",
            asset_class="equity",
            venue="XNAS",
            universe_key="nasdaq_top",
            exchange="NASDAQ",
            avg_daily_volume=2000,
            rank=1,
            computed_at=stale_at,
        ),
        UniverseSymbol(
            symbol="NEWNYSE",
            asset_class="equity",
            venue="XNYS",
            universe_key="nyse_top",
            exchange="NYSE",
            avg_daily_volume=1900,
            rank=1,
            computed_at=stale_at,
        ),
    ]

    with app.app_context():
        db.session.add(
            UniverseSymbol(
                symbol="LKG",
                exchange="NASDAQ",
                avg_daily_volume=1000,
                rank=1,
            )
        )
        db.session.commit()

        with pytest.raises(universe_builder.UniverseCandidateError, match="stale"):
            universe_builder.save_universe(
                candidate,
                final_counts={"NASDAQ": 1, "NYSE": 1},
                computed_at=stale_at,
                processed_days=1,
            )
        stored = [row.symbol for row in UniverseSymbol.query.all()]

    assert stored == ["LKG"]


def test_failed_rebuild_retains_last_known_good_and_records_reason(
    app, fake_provider
):
    fake_provider.fail(
        "reference_universe",
        message="reference endpoint unavailable",
        error_type="http_error",
        status_code=503,
    )

    with app.app_context():
        db.session.add(
            UniverseSymbol(
                symbol="LKG",
                exchange="NASDAQ",
                avg_daily_volume=1000,
                rank=1,
            )
        )
        db.session.commit()

        with pytest.raises(ProviderError, match="reference endpoint unavailable"):
            universe_builder.build_and_save_universe()
        stored = [row.symbol for row in UniverseSymbol.query.all()]
        status = universe_builder.status_payload()["last_build"]

    assert stored == ["LKG"]
    assert status["status"] == "failed"
    assert status["retained_previous"] is True
    assert "reference endpoint unavailable" in status["degraded_reason"]
