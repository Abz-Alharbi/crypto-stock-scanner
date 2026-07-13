from datetime import datetime, timezone

import pytest

from backend.domain import (
    AssetClass,
    Instrument,
    MarketDataRequest,
    ScanContext,
    ScanScope,
    Timeframe,
    parse_timeframe,
)
from backend.domain.instrument import GLOBAL_CRYPTO_VENUE, US_EQUITIES_VENUE
from backend.market_config import CANONICAL_TIMEFRAMES, TIMEFRAME_MAP
from backend.symbols import canonicalize_symbol


@pytest.mark.parametrize(
    ("symbol", "market", "provider_symbol", "display_symbol", "wire_market"),
    [
        ("AAPL", None, "AAPL", "AAPL", "stocks"),
        (" aapl ", "stocks", "AAPL", "AAPL", "stocks"),
        ("X:BTCUSD", None, "X:BTCUSD", "BTCUSD", "crypto"),
        ("X:BTCUSD", "crypto", "X:BTCUSD", "BTCUSD", "crypto"),
        ("BTCUSD", "crypto", "X:BTCUSD", "BTCUSD", "crypto"),
        ("BTC", "crypto", "X:BTCUSD", "BTCUSD", "crypto"),
        ("BTC", AssetClass.CRYPTO, "X:BTCUSD", "BTCUSD", "crypto"),
        ("X:BTCUSD", "stocks", "X:BTCUSD", "X:BTCUSD", "stocks"),
        ("X:BTCEUR", "crypto", "X:BTCEUR", "BTCEUR", "crypto"),
        ("", None, "", "", "stocks"),
        ("", "crypto", "X:USD", "USD", "crypto"),
    ],
)
def test_legacy_symbol_shim_preserves_wire_behavior(
    symbol,
    market,
    provider_symbol,
    display_symbol,
    wire_market,
):
    canonical = canonicalize_symbol(symbol, market)

    assert canonical.provider_symbol == provider_symbol
    assert canonical.display_symbol == display_symbol
    assert canonical.market == wire_market


@pytest.mark.parametrize(
    ("wire_symbol", "asset_class", "quote"),
    [
        ("AAPL", AssetClass.EQUITY, None),
        ("X:BTCUSD", AssetClass.CRYPTO, "USD"),
    ],
)
def test_canonical_symbols_round_trip_through_instrument(wire_symbol, asset_class, quote):
    instrument = Instrument.from_wire(wire_symbol, asset_class, quote=quote)

    assert instrument.to_wire() == wire_symbol
    assert Instrument.from_wire(instrument.to_wire(), asset_class, quote=quote) == instrument


def test_crypto_pair_construction_is_explicit_and_lossless():
    instrument = Instrument.for_crypto("btc", quote="eur", venue="example_exchange")

    assert instrument.asset_class is AssetClass.CRYPTO
    assert instrument.base == "BTC"
    assert instrument.quote == "EUR"
    assert instrument.venue == "EXAMPLE_EXCHANGE"
    assert instrument.pair == "BTC/EUR"
    assert instrument.provider_symbol == "X:BTCEUR"
    assert instrument.display_symbol == "BTCEUR"
    assert instrument.instrument_id == "crypto:EXAMPLE_EXCHANGE:BTC/EUR"


def test_default_constructors_preserve_current_market_defaults():
    equity = Instrument.for_equity("msft")
    crypto = Instrument.for_crypto("eth")

    assert (equity.provider_symbol, equity.venue) == ("MSFT", US_EQUITIES_VENUE)
    assert (crypto.provider_symbol, crypto.venue) == ("X:ETHUSD", GLOBAL_CRYPTO_VENUE)


@pytest.mark.parametrize("wire_value", ["stocks", "crypto"])
def test_asset_class_wire_values_round_trip(wire_value):
    asset_class = AssetClass.from_wire(wire_value)

    assert asset_class.wire_value == wire_value


def test_market_data_request_carries_typed_instrument_and_timeframe():
    instrument = Instrument.for_crypto("btc")
    request = MarketDataRequest(
        instrument=instrument,
        timeframe="4H",
        start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end=datetime(2026, 1, 2, tzinfo=timezone.utc),
        required_bars=120,
    )

    assert request.instrument is instrument
    assert request.asset_class is AssetClass.CRYPTO
    assert request.venue == GLOBAL_CRYPTO_VENUE
    assert request.timeframe == Timeframe("4H")


def test_timeframe_domain_reexports_existing_canonical_configuration():
    assert tuple(Timeframe(value).to_wire() for value in CANONICAL_TIMEFRAMES) == CANONICAL_TIMEFRAMES
    assert parse_timeframe("1m").config is TIMEFRAME_MAP["1m"]
    assert parse_timeframe("1M").config is TIMEFRAME_MAP["1M"]
    assert parse_timeframe("4H").is_intraday is True


def test_internally_inconsistent_domain_context_is_rejected():
    crypto = Instrument.for_crypto("btc")

    with pytest.raises(ValueError, match="quote currency"):
        Instrument(AssetClass.CRYPTO, "BTC", None, GLOBAL_CRYPTO_VENUE)
    with pytest.raises(ValueError, match="cannot define a quote"):
        Instrument(AssetClass.EQUITY, "AAPL", "USD", US_EQUITIES_VENUE)
    with pytest.raises(ValueError, match="asset class"):
        ScanContext(
            asset_class=AssetClass.EQUITY,
            venue=GLOBAL_CRYPTO_VENUE,
            timeframe=Timeframe("1D"),
            scope=ScanScope.INSTRUMENT,
            instrument=crypto,
        )
    with pytest.raises(ValueError, match="only a universe"):
        ScanContext(
            asset_class=AssetClass.CRYPTO,
            venue=GLOBAL_CRYPTO_VENUE,
            timeframe=Timeframe("1D"),
            scope=ScanScope.UNIVERSE,
            universe="crypto-usd",
            instrument=crypto,
        )


@pytest.mark.parametrize("value", ["1h", "1MIN", "", None])
def test_invalid_timeframes_are_rejected_without_case_coercion(value):
    with pytest.raises(ValueError, match="Unsupported timeframe"):
        Timeframe(value)


def test_invalid_market_data_ranges_and_history_are_rejected():
    instrument = Instrument.for_equity("AAPL")
    start = datetime(2026, 1, 2, tzinfo=timezone.utc)
    end = datetime(2026, 1, 1, tzinfo=timezone.utc)

    with pytest.raises(ValueError, match="start must be before end"):
        MarketDataRequest(instrument, Timeframe("1D"), start=start, end=end)
    with pytest.raises(ValueError, match="positive"):
        MarketDataRequest(instrument, Timeframe("1D"), required_bars=0)
