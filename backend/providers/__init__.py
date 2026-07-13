from contextlib import contextmanager
from contextvars import ContextVar

from backend.providers.base import MarketDataProvider
from backend.providers.errors import ProviderError, ProviderFailureContext
from backend.providers.polygon_provider import PolygonProvider

_provider_override = ContextVar("market_data_provider_override", default=None)
_default_provider = PolygonProvider()


def get_provider() -> MarketDataProvider:
    return _provider_override.get() or _default_provider


@contextmanager
def provider_override(provider: MarketDataProvider):
    if not isinstance(provider, MarketDataProvider):
        raise TypeError("provider must satisfy MarketDataProvider")
    token = _provider_override.set(provider)
    try:
        yield provider
    finally:
        _provider_override.reset(token)


__all__ = [
    "MarketDataProvider",
    "PolygonProvider",
    "ProviderError",
    "ProviderFailureContext",
    "get_provider",
    "provider_override",
]
