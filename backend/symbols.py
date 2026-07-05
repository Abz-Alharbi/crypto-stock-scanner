from dataclasses import dataclass


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
    if market:
        return str(market).lower().strip()
    return "crypto" if str(symbol or "").upper().strip().startswith("X:") else "stocks"


def canonicalize_symbol(symbol, market=None):
    provider_symbol = str(symbol or "").upper().strip()
    inferred_market = infer_market(provider_symbol, market)

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


def canonical_symbol_payload(symbol, market=None):
    return canonicalize_symbol(symbol, market).to_dict()
