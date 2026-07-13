"""Duplicate-safe in-process strategy registry."""

from __future__ import annotations

from backend.strategies.base import Strategy


class DuplicateStrategyError(ValueError):
    pass


class UnknownStrategyError(ValueError):
    pass


class StrategyRegistry:
    def __init__(self) -> None:
        self._strategies: dict[str, Strategy] = {}

    def register(self, strategy: Strategy) -> Strategy:
        if strategy.identifier in self._strategies:
            raise DuplicateStrategyError(
                f"Strategy '{strategy.identifier}' is already registered"
            )
        self._strategies[strategy.identifier] = strategy
        return strategy

    def get(self, strategy_id: str) -> Strategy:
        try:
            return self._strategies[strategy_id]
        except KeyError as exc:
            raise UnknownStrategyError(f"Unknown strategy '{strategy_id}'") from exc

    def all(self) -> tuple[Strategy, ...]:
        return tuple(self._strategies.values())

    def ids(self) -> tuple[str, ...]:
        return tuple(self._strategies)


registry = StrategyRegistry()
