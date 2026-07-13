"""Canonical strategy contract and result types."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Mapping, Sequence

from backend.domain import AssetClass, Instrument, Timeframe

logger = logging.getLogger(__name__)


class StrategyStatus(str, Enum):
    MATCHED = "matched"
    NOT_MATCHED = "not_matched"
    INSUFFICIENT_DATA = "insufficient_data"
    UNSUPPORTED = "unsupported"
    ERROR = "error"


class SignalDirection(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    NO_SIGNAL = "no_signal"


class StrategyParameterError(ValueError):
    """Raised when strategy parameters do not match the declared schema."""


@dataclass(frozen=True)
class StrategyContext:
    """Evaluation input with oldest-to-newest, closed candles in ``bars``."""

    bars: Sequence[Mapping[str, Any]]
    analysis: Mapping[str, Any]
    asset_class: AssetClass
    timeframe: Timeframe
    instrument: Instrument | None = None


@dataclass(frozen=True)
class StrategyResult:
    strategy_id: str
    strategy_version: str
    status: StrategyStatus
    direction: SignalDirection
    score: float | None = None
    confidence: float | None = None
    explanation: str | None = None
    evidence: Mapping[str, Any] | None = None

    @property
    def matched(self) -> bool:
        return self.status is StrategyStatus.MATCHED

    @property
    def evaluated(self) -> bool:
        return self.status in {StrategyStatus.MATCHED, StrategyStatus.NOT_MATCHED}

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "strategy_version": self.strategy_version,
            "status": self.status.value,
            "evaluated": self.evaluated,
            "direction": self.direction.value,
            "score": self.score,
            "confidence": self.confidence,
            "explanation": self.explanation,
            "evidence": dict(self.evidence or {}),
        }


@dataclass(frozen=True)
class Strategy(ABC):
    identifier: str
    version: str
    display_name: str
    description: str
    category: str
    parameter_schema: Mapping[str, Mapping[str, Any]]
    required_history: int
    required_indicators: tuple[str, ...]
    required_features: frozenset[str]
    supported_asset_classes: frozenset[AssetClass]
    supported_timeframes: frozenset[Timeframe]

    @property
    def is_legacy_filter(self) -> bool:
        return False

    def validate_parameters(
        self, parameters: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        supplied = dict(parameters or {})
        unknown = sorted(set(supplied) - set(self.parameter_schema))
        if unknown:
            raise StrategyParameterError(
                f"Unknown parameters for {self.identifier}: {', '.join(unknown)}"
            )

        validated: dict[str, Any] = {}
        for name, rules in self.parameter_schema.items():
            has_value = name in supplied
            if not has_value and "default" in rules:
                value = rules["default"]
            elif not has_value and rules.get("required", False):
                raise StrategyParameterError(
                    f"Missing required parameter '{name}' for {self.identifier}"
                )
            elif not has_value:
                continue
            else:
                value = supplied[name]

            expected = rules.get("type")
            type_map = {
                "integer": int,
                "number": (int, float),
                "string": str,
                "boolean": bool,
            }
            if expected in type_map and (
                not isinstance(value, type_map[expected])
                or expected in {"integer", "number"} and isinstance(value, bool)
            ):
                raise StrategyParameterError(
                    f"Parameter '{name}' for {self.identifier} must be {expected}"
                )
            if "const" in rules and value != rules["const"]:
                raise StrategyParameterError(
                    f"Parameter '{name}' for {self.identifier} must equal {rules['const']}"
                )
            if "enum" in rules and value not in rules["enum"]:
                raise StrategyParameterError(
                    f"Parameter '{name}' for {self.identifier} must be one of {rules['enum']}"
                )
            if "minimum" in rules and value < rules["minimum"]:
                raise StrategyParameterError(
                    f"Parameter '{name}' for {self.identifier} must be >= {rules['minimum']}"
                )
            if "maximum" in rules and value > rules["maximum"]:
                raise StrategyParameterError(
                    f"Parameter '{name}' for {self.identifier} must be <= {rules['maximum']}"
                )
            validated[name] = value
        return validated

    def evaluate(
        self,
        context: StrategyContext,
        parameters: Mapping[str, Any] | None = None,
    ) -> StrategyResult:
        validated = self.validate_parameters(parameters)
        if context.asset_class not in self.supported_asset_classes:
            return self._result(
                StrategyStatus.UNSUPPORTED,
                SignalDirection.NO_SIGNAL,
                explanation=f"{context.asset_class.value} is not supported",
            )
        if context.timeframe not in self.supported_timeframes:
            return self._result(
                StrategyStatus.UNSUPPORTED,
                SignalDirection.NO_SIGNAL,
                explanation=f"{context.timeframe.value} is not supported",
            )
        if len(context.bars) < self.required_history:
            return self._result(
                StrategyStatus.INSUFFICIENT_DATA,
                SignalDirection.NO_SIGNAL,
                explanation=(
                    f"Requires {self.required_history} closed bars; "
                    f"received {len(context.bars)}"
                ),
                evidence={
                    "required_history": self.required_history,
                    "available_history": len(context.bars),
                },
            )
        try:
            return self._evaluate(context, validated)
        except (KeyError, TypeError, ValueError, ZeroDivisionError) as exc:
            logger.exception(
                "Strategy evaluation failed strategy=%s instrument=%s asset_class=%s timeframe=%s",
                self.identifier,
                context.instrument.provider_symbol if context.instrument else None,
                context.asset_class.value,
                context.timeframe.value,
            )
            return self._result(
                StrategyStatus.ERROR,
                SignalDirection.NO_SIGNAL,
                explanation=f"Strategy evaluation failed: {type(exc).__name__}: {exc}",
                evidence={
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "instrument": (
                        context.instrument.provider_symbol
                        if context.instrument
                        else None
                    ),
                    "asset_class": context.asset_class.value,
                    "timeframe": context.timeframe.value,
                },
            )

    def _result(
        self,
        status: StrategyStatus,
        direction: SignalDirection,
        *,
        score: float | None = None,
        confidence: float | None = None,
        explanation: str | None = None,
        evidence: Mapping[str, Any] | None = None,
    ) -> StrategyResult:
        return StrategyResult(
            strategy_id=self.identifier,
            strategy_version=self.version,
            status=status,
            direction=direction,
            score=score,
            confidence=confidence,
            explanation=explanation,
            evidence=evidence,
        )

    @abstractmethod
    def _evaluate(
        self, context: StrategyContext, parameters: Mapping[str, Any]
    ) -> StrategyResult:
        raise NotImplementedError


@dataclass(frozen=True)
class LegacyFilterStrategy(Strategy):
    predicate: Callable[[Mapping[str, Any]], bool]
    matched_direction: SignalDirection

    @property
    def is_legacy_filter(self) -> bool:
        return True

    def legacy_match(self, analysis: Mapping[str, Any]) -> bool:
        return bool(self.predicate(analysis))

    def _evaluate(
        self, context: StrategyContext, parameters: Mapping[str, Any]
    ) -> StrategyResult:
        matched = self.legacy_match(context.analysis)
        return self._result(
            StrategyStatus.MATCHED if matched else StrategyStatus.NOT_MATCHED,
            self.matched_direction if matched else SignalDirection.NO_SIGNAL,
            score=1.0 if matched else 0.0,
        )
