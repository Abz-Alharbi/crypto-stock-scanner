"""Helpers for faithful wrappers around the legacy boolean filters."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from backend.domain import AssetClass
from backend.domain.timeframes import CANONICAL_TIMEFRAMES, Timeframe
from backend.strategies.base import LegacyFilterStrategy, SignalDirection
from backend.strategies.registry import registry

ALL_ASSET_CLASSES = frozenset(AssetClass)
ALL_TIMEFRAMES = frozenset(Timeframe(value) for value in CANONICAL_TIMEFRAMES)


def register_legacy(
    *,
    identifier: str,
    display_name: str,
    description: str,
    category: str,
    predicate: Callable[[Mapping[str, Any]], bool],
    direction: SignalDirection,
    required_history: int = 30,
    required_indicators: tuple[str, ...] = (),
    required_features: frozenset[str] = frozenset(),
) -> LegacyFilterStrategy:
    return registry.register(
        LegacyFilterStrategy(
            identifier=identifier,
            version="1.0.0",
            display_name=display_name,
            description=description,
            category=category,
            parameter_schema={},
            required_history=required_history,
            required_indicators=required_indicators,
            required_features=required_features,
            supported_asset_classes=ALL_ASSET_CLASSES,
            supported_timeframes=ALL_TIMEFRAMES,
            predicate=predicate,
            matched_direction=direction,
        )
    )
