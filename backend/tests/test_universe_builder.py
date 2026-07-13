from datetime import date, datetime

from backend.extensions import db
from backend.models.universe import UniverseSymbol
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

    assert payload == {
        "total_symbols": 2,
        "nasdaq_count": 1,
        "nyse_count": 1,
        "last_computed_at": "2026-01-01T12:00:00",
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


def test_current_empty_universe_save_replaces_good_rows_and_activates_fallback(app):
    with app.app_context():
        db.session.add(
            UniverseSymbol(symbol="AAA", exchange="NASDAQ", avg_daily_volume=1000, rank=1, computed_at=datetime.utcnow())
        )
        db.session.commit()

        universe_builder.save_universe([])

        assert UniverseSymbol.query.count() == 0
        assert universe_builder.get_scan_universe_symbols(["AAPL", "MSFT"]) == ["AAPL", "MSFT"]
