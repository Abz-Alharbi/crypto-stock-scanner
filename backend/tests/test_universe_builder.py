from datetime import date, datetime

from backend.extensions import db
from backend.models.universe import UniverseSymbol
from backend.services.universe import universe_builder


class FakeUniversePolygon:
    max_concurrent_requests = 2

    def get_reference_tickers(self, exchange, limit=1000):
        if exchange == "XNAS":
            return [
                {"ticker": "AAA", "type": "CS"},
                {"ticker": "BBB", "type": "CS"},
                {"ticker": "QQQ", "type": "ETF"},
            ]
        if exchange == "XNYS":
            return [
                {"ticker": "CCC", "type": "CS"},
                {"ticker": "DDD", "type": "CS"},
            ]
        return []

    def get_grouped_daily_stocks(self, day):
        if day == "2026-01-02":
            return []
        return [
            {"T": "AAA", "v": 1000},
            {"T": "BBB", "v": 5000},
            {"T": "CCC", "v": 3000},
            {"T": "DDD", "v": 100},
            {"T": "QQQ", "v": 999999},
        ]


def test_build_and_save_universe_ranks_common_stocks_by_average_volume(app, monkeypatch):
    monkeypatch.setattr(universe_builder, "polygon", FakeUniversePolygon())
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
