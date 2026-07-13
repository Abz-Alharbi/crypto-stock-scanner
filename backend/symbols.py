from dataclasses import dataclass

from backend.domain.asset import AssetClass
from backend.domain.instrument import Instrument


@dataclass(frozen=True)
class CanonicalSymbol:
    provider_symbol: str
    display_symbol: str
    market: str

    def to_dict(self):
        return {
            "provider_symbol": self.provider_symbol,
            "display_symbol": self.display_symbol,
            "market": self.market,
        }


def infer_market(symbol, market=None):
    if isinstance(market, AssetClass):
        return market.wire_value
    if market:
        return str(market).lower().strip()
    return "crypto" if str(symbol or "").upper().strip().startswith("X:") else "stocks"


def _legacy_canonical_symbol(provider_symbol, inferred_market):
    if inferred_market == "crypto":
        if not provider_symbol.startswith("X:"):
            if not provider_symbol.endswith("USD"):
                provider_symbol = f"{provider_symbol}USD"
            provider_symbol = f"X:{provider_symbol}"
        display_symbol = provider_symbol[2:]
    else:
        display_symbol = provider_symbol

    return CanonicalSymbol(
        provider_symbol=provider_symbol,
        display_symbol=display_symbol,
        market=inferred_market,
    )


def canonicalize_symbol(symbol, market=None):
    provider_symbol = str(symbol or "").upper().strip()
    inferred_market = infer_market(provider_symbol, market)

    if inferred_market not in {AssetClass.EQUITY.value, AssetClass.CRYPTO.value}:
        # Preserve the legacy helper's behavior for internal callers that pass
        # a non-domain market. Public request schemas already reject it.
        return _legacy_canonical_symbol(provider_symbol, inferred_market)

    asset_class = AssetClass.from_wire(inferred_market)
    crypto_pair = provider_symbol[2:] if provider_symbol.startswith("X:") else provider_symbol
    cannot_form_explicit_instrument = not provider_symbol or (
        asset_class is AssetClass.CRYPTO
        and (
            (provider_symbol.startswith("X:") and not crypto_pair.endswith("USD"))
            or crypto_pair in {"USD", "USDUSD"}
        )
    )
    if cannot_form_explicit_instrument:
        # Invalid legacy inputs retain their historical output. Strict domain
        # constructors still reject them when used directly.
        return _legacy_canonical_symbol(provider_symbol, inferred_market)

    instrument = Instrument.from_legacy_symbol(provider_symbol, asset_class)

    return CanonicalSymbol(
        provider_symbol=instrument.provider_symbol,
        display_symbol=instrument.display_symbol,
        market=asset_class.wire_value,
    )


def canonical_symbol_payload(symbol, market=None):
    return canonicalize_symbol(symbol, market).to_dict()
