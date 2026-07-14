"""Duplicate-safe registry and resolution API for scan universes."""

from __future__ import annotations

from dataclasses import replace

from backend.domain import AssetClass
from backend.services.universe.catalog import (
    ALL_STOCK_SYMBOLS,
    CRYPTO_SYMBOLS,
    NASDAQ_SYMBOLS,
    NYSE_SYMBOLS,
)
from backend.services.universe.providers import (
    CryptoVolumeUniverseProvider,
    EquityVolumeUniverseProvider,
    UniverseProvider,
    UniverseResolution,
)


class DuplicateUniverseError(ValueError):
    pass


class UnknownUniverseError(ValueError):
    pass


class UnsupportedUniverseError(ValueError):
    pass


class UniverseRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, UniverseProvider] = {}
        self._defaults: dict[AssetClass, str] = {}

    def register(self, provider: UniverseProvider, *, default=False):
        if provider.universe_key in self._providers:
            raise DuplicateUniverseError(
                f"Universe '{provider.universe_key}' is already registered"
            )
        self._providers[provider.universe_key] = provider
        if default:
            self._defaults[provider.asset_class] = provider.universe_key
        return provider

    def get(self, universe_key: str) -> UniverseProvider:
        try:
            return self._providers[universe_key]
        except KeyError as exc:
            raise UnknownUniverseError(f"Unknown universe '{universe_key}'") from exc

    def default_key(self, asset_class: AssetClass | str) -> str:
        parsed = AssetClass.from_wire(asset_class)
        try:
            return self._defaults[parsed]
        except KeyError as exc:
            raise UnknownUniverseError(
                f"No default universe is registered for '{parsed.value}'"
            ) from exc

    def validate(self, asset_class: AssetClass | str, universe_key: str | None) -> str:
        parsed = AssetClass.from_wire(asset_class)
        resolved_key = universe_key or self.default_key(parsed)
        provider = self.get(resolved_key)
        if provider.asset_class is not parsed:
            raise UnsupportedUniverseError(
                f"Universe '{resolved_key}' does not support {parsed.value}"
            )
        return resolved_key

    def resolve(
        self,
        asset_class: AssetClass | str,
        universe_key: str | None = None,
        *,
        fallback_symbols=(),
    ) -> UniverseResolution:
        resolved_key = self.validate(asset_class, universe_key)
        return self.get(resolved_key).resolve(fallback_symbols)

    def all(self) -> tuple[UniverseProvider, ...]:
        return tuple(self._providers.values())


registry = UniverseRegistry()
registry.register(
    EquityVolumeUniverseProvider(
        "us_stocks_top", "All US Top Volume", ("nasdaq_top", "nyse_top")
    ),
    default=True,
)
registry.register(
    EquityVolumeUniverseProvider(
        "nasdaq_top", "NASDAQ Top Volume", ("nasdaq_top",)
    )
)
registry.register(
    EquityVolumeUniverseProvider("nyse_top", "NYSE Top Volume", ("nyse_top",))
)
registry.register(
    CryptoVolumeUniverseProvider(
        "crypto_static",
        "Crypto Top USD Pairs",
    ),
    default=True,
)


def fallback_for_universe(universe_key: str):
    return {
        "us_stocks_top": ALL_STOCK_SYMBOLS,
        "nasdaq_top": NASDAQ_SYMBOLS,
        "nyse_top": NYSE_SYMBOLS,
        "crypto_static": CRYPTO_SYMBOLS,
    }[universe_key]


def resolve_scan_universe(asset_class, universe_key=None):
    resolved_key = registry.validate(asset_class, universe_key)
    resolution = registry.resolve(
        asset_class,
        resolved_key,
        fallback_symbols=fallback_for_universe(resolved_key),
    )
    if resolution.symbol_venues:
        return resolution
    if resolution.asset_class is AssetClass.CRYPTO:
        venues = tuple((symbol, "GLOBAL_CRYPTO") for symbol in resolution.symbols)
    elif resolved_key == "nasdaq_top":
        venues = tuple((symbol, "XNAS") for symbol in resolution.symbols)
    elif resolved_key == "nyse_top":
        venues = tuple((symbol, "XNYS") for symbol in resolution.symbols)
    else:
        nasdaq = set(NASDAQ_SYMBOLS)
        venues = tuple(
            (symbol, "XNAS" if symbol in nasdaq else "XNYS")
            for symbol in resolution.symbols
        )
    return replace(resolution, symbol_venues=venues)


__all__ = [
    "DuplicateUniverseError",
    "UnknownUniverseError",
    "UnsupportedUniverseError",
    "UniverseRegistry",
    "registry",
    "resolve_scan_universe",
]
