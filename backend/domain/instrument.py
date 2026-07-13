from dataclasses import dataclass

from backend.domain.asset import AssetClass


US_EQUITIES_VENUE = "US_EQUITIES"
GLOBAL_CRYPTO_VENUE = "GLOBAL_CRYPTO"


def _required_upper(value, field_name):
    normalized = str(value or "").upper().strip()
    if not normalized:
        raise ValueError(f"{field_name} is required")
    return normalized


@dataclass(frozen=True)
class Instrument:
    """Provider-neutral tradable identity with explicit pair semantics."""

    asset_class: AssetClass
    base: str
    quote: str | None
    venue: str

    def __post_init__(self):
        asset_class = AssetClass.from_wire(self.asset_class)
        base = _required_upper(self.base, "base")
        quote = str(self.quote).upper().strip() if self.quote is not None else None
        venue = _required_upper(self.venue, "venue")

        if asset_class is AssetClass.CRYPTO and not quote:
            raise ValueError("Crypto instruments require a quote currency")
        if asset_class is AssetClass.EQUITY and quote is not None:
            raise ValueError("Equity instruments cannot define a quote currency")
        if quote and base == quote:
            raise ValueError("Instrument base and quote currencies must differ")

        object.__setattr__(self, "asset_class", asset_class)
        object.__setattr__(self, "base", base)
        object.__setattr__(self, "quote", quote)
        object.__setattr__(self, "venue", venue)

    @classmethod
    def for_equity(cls, symbol, venue=US_EQUITIES_VENUE):
        return cls(
            asset_class=AssetClass.EQUITY,
            base=_required_upper(symbol, "symbol"),
            quote=None,
            venue=venue,
        )

    @classmethod
    def for_crypto(cls, base, quote="USD", venue=GLOBAL_CRYPTO_VENUE):
        return cls(
            asset_class=AssetClass.CRYPTO,
            base=base,
            quote=quote,
            venue=venue,
        )

    @classmethod
    def from_wire(cls, symbol, asset_class, *, quote=None, venue=None):
        """Parse an already canonical provider symbol without guessing a pair."""

        parsed_asset_class = AssetClass.from_wire(asset_class)
        normalized = _required_upper(symbol, "symbol")
        if parsed_asset_class is AssetClass.EQUITY:
            return cls.for_equity(normalized, venue or US_EQUITIES_VENUE)

        if not normalized.startswith("X:"):
            raise ValueError("Canonical crypto provider symbols must start with 'X:'")
        pair = normalized[2:]
        normalized_quote = _required_upper(quote or "USD", "quote")
        if not pair.endswith(normalized_quote) or len(pair) <= len(normalized_quote):
            raise ValueError("Crypto provider symbol is inconsistent with its quote currency")
        return cls.for_crypto(
            pair[: -len(normalized_quote)],
            normalized_quote,
            venue or GLOBAL_CRYPTO_VENUE,
        )

    @classmethod
    def from_legacy_symbol(cls, symbol, asset_class, *, venue=None):
        """Apply the legacy USD heuristic at the compatibility boundary only."""

        parsed_asset_class = AssetClass.from_wire(asset_class)
        normalized = _required_upper(symbol, "symbol")
        if parsed_asset_class is AssetClass.EQUITY:
            return cls.for_equity(normalized, venue or US_EQUITIES_VENUE)

        prefixed = normalized.startswith("X:")
        pair = normalized[2:] if prefixed else normalized
        if prefixed and (not pair.endswith("USD") or len(pair) <= 3):
            raise ValueError("Legacy prefixed crypto symbol has no explicit supported quote")
        if pair.endswith("USD") and len(pair) > 3:
            base = pair[:-3]
        else:
            base = pair
        return cls.for_crypto(base, "USD", venue or GLOBAL_CRYPTO_VENUE)

    @property
    def provider_symbol(self):
        if self.asset_class is AssetClass.CRYPTO:
            return f"X:{self.base}{self.quote}"
        return self.base

    @property
    def display_symbol(self):
        if self.asset_class is AssetClass.CRYPTO:
            return f"{self.base}{self.quote}"
        return self.base

    @property
    def pair(self):
        if self.asset_class is not AssetClass.CRYPTO:
            return None
        return f"{self.base}/{self.quote}"

    @property
    def instrument_id(self):
        identity = self.pair or self.base
        return f"{self.asset_class.value}:{self.venue}:{identity}"

    def to_wire(self):
        return self.provider_symbol
