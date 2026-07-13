"""Compatibility facade between scan/API code and the strategy registry."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from backend.domain import AssetClass, Timeframe
from backend.domain.timeframes import CANONICAL_TIMEFRAMES
from backend.strategies import (
    LegacyFilterStrategy,
    Strategy,
    StrategyContext,
    StrategyStatus,
    registry,
)
from backend.strategies.capabilities import (
    get_plan_capabilities,
    strategy_enabled,
)
from backend.strategies.presets import FILTER_PRESETS


def get_flat_filters() -> dict[str, dict[str, Any]]:
    """Expose only the 22 legacy filters through the old compatibility API."""

    result: dict[str, dict[str, Any]] = {}
    for strategy in registry.all():
        if not isinstance(strategy, LegacyFilterStrategy):
            continue
        result[strategy.identifier] = {
            "name": strategy.display_name,
            "description": strategy.description,
            "category": strategy.category,
            "check": strategy.legacy_match,
        }
    return result


def get_strategies(strategy_ids: Iterable[str]) -> tuple[Strategy, ...]:
    return tuple(registry.get(strategy_id) for strategy_id in strategy_ids)


def required_features(strategies: Iterable[Strategy]) -> frozenset[str]:
    return frozenset(
        feature for strategy in strategies for feature in strategy.required_features
    )


def available_timeframes() -> frozenset[str]:
    return frozenset(get_plan_capabilities()["timeframes"])


def validate_strategy_selection(
    strategy_ids: Iterable[str],
    *,
    asset_class: AssetClass,
    timeframe: Timeframe,
    parameters: Mapping[str, Mapping[str, Any]] | None = None,
) -> None:
    parameter_map = parameters or {}
    plan = get_plan_capabilities()
    if asset_class.value not in plan["asset_classes"]:
        raise ValueError(
            f"Asset class '{asset_class.value}' is unavailable on the configured plan"
        )
    if timeframe.value not in plan["timeframes"]:
        raise ValueError(
            f"Timeframe '{timeframe.value}' is unavailable on the configured plan"
        )
    for strategy_id in strategy_ids:
        strategy = registry.get(strategy_id)
        if not strategy_enabled(strategy_id):
            raise ValueError(
                f"Strategy '{strategy_id}' is unavailable on the configured plan"
            )
        if asset_class not in strategy.supported_asset_classes:
            raise ValueError(
                f"Strategy '{strategy_id}' does not support {asset_class.value}"
            )
        if timeframe not in strategy.supported_timeframes:
            raise ValueError(
                f"Strategy '{strategy_id}' does not support {timeframe.value}"
            )
        strategy.validate_parameters(parameter_map.get(strategy_id))


def filters_payload() -> dict[str, dict[str, dict[str, Any]]]:
    categories: dict[str, dict[str, dict[str, Any]]] = {}
    for strategy in registry.all():
        categories.setdefault(strategy.category, {})[strategy.identifier] = {
            "id": strategy.identifier,
            "name": strategy.display_name,
            "description": strategy.description,
            "category": strategy.category,
            "version": strategy.version,
            "parameters": dict(strategy.parameter_schema),
            "required_history": strategy.required_history,
            "required_indicators": list(strategy.required_indicators),
            "supported_asset_classes": sorted(
                asset.value for asset in strategy.supported_asset_classes
            ),
            "supported_timeframes": [
                value
                for value in CANONICAL_TIMEFRAMES
                if Timeframe(value) in strategy.supported_timeframes
            ],
            "available": strategy_enabled(strategy.identifier),
        }
    return categories


__all__ = [
    "FILTER_PRESETS",
    "available_timeframes",
    "filters_payload",
    "get_flat_filters",
    "get_strategies",
    "required_features",
    "StrategyContext",
    "StrategyStatus",
    "validate_strategy_selection",
]
