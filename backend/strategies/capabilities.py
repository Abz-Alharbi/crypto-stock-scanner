"""Config-driven provider-plan capability declarations."""

from __future__ import annotations

import os
from typing import Any

from backend.domain import AssetClass
from backend.domain.timeframes import CANONICAL_TIMEFRAMES

DEFAULT_PLAN_TIER = "unlimited"

PROVIDER_PLAN_CAPABILITIES: dict[str, dict[str, Any]] = {
    "unlimited": {
        "strategy_ids": "*",
        "asset_classes": [asset.value for asset in AssetClass],
        "timeframes": list(CANONICAL_TIMEFRAMES),
    }
}


def current_plan_tier() -> str:
    return os.getenv("MARKET_DATA_PLAN_TIER", DEFAULT_PLAN_TIER)


def get_plan_capabilities(plan_tier: str | None = None) -> dict[str, Any]:
    tier = plan_tier or current_plan_tier()
    try:
        return PROVIDER_PLAN_CAPABILITIES[tier]
    except KeyError as exc:
        raise ValueError(f"Unknown market-data plan tier '{tier}'") from exc


def strategy_enabled(strategy_id: str, plan_tier: str | None = None) -> bool:
    configured = get_plan_capabilities(plan_tier)["strategy_ids"]
    return configured == "*" or strategy_id in configured
