"""Registry-only RSI overbought/oversold demonstration strategy."""

from collections.abc import Mapping
from typing import Any

from backend.strategies.base import (
    SignalDirection,
    Strategy,
    StrategyContext,
    StrategyResult,
    StrategyStatus,
)
from backend.strategies.legacy import ALL_ASSET_CLASSES, ALL_TIMEFRAMES
from backend.strategies.registry import registry


class RsiOverboughtOversoldStrategy(Strategy):
    def _evaluate(
        self, context: StrategyContext, parameters: Mapping[str, Any]
    ) -> StrategyResult:
        period = parameters["period"]
        rsi = context.analysis["indicators"]["rsi"]
        if rsi is None:
            return self._result(
                StrategyStatus.INSUFFICIENT_DATA,
                SignalDirection.NO_SIGNAL,
                explanation=f"RSI({period}) is unavailable",
                evidence={"rsi": None},
            )
        if rsi < 30:
            direction = SignalDirection.BULLISH
            status = StrategyStatus.MATCHED
            explanation = f"RSI({period}) is below 30"
        elif rsi > 70:
            direction = SignalDirection.BEARISH
            status = StrategyStatus.MATCHED
            explanation = f"RSI({period}) is above 70"
        else:
            direction = SignalDirection.NEUTRAL
            status = StrategyStatus.NOT_MATCHED
            explanation = f"RSI({period}) is between 30 and 70 inclusive"
        return self._result(
            status,
            direction,
            score=abs(float(rsi) - 50.0) / 50.0,
            explanation=explanation,
            evidence={"rsi": rsi},
        )


registry.register(
    RsiOverboughtOversoldStrategy(
        identifier="rsi_overbought_oversold",
        version="1.0.0",
        display_name="RSI Overbought/Oversold",
        description="Bullish below RSI 30, bearish above RSI 70",
        category="oscillators",
        parameter_schema={
            "period": {"type": "integer", "default": 14, "const": 14}
        },
        required_history=30,
        required_indicators=("rsi",),
        required_features=frozenset({"rsi"}),
        supported_asset_classes=ALL_ASSET_CLASSES,
        supported_timeframes=ALL_TIMEFRAMES,
    )
)
