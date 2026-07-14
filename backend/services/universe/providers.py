"""Universe-provider contract and concrete compatibility providers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from sqlalchemy.exc import SQLAlchemyError

from backend.domain import AssetClass
from backend.extensions import db
from backend.models.universe import UniverseSymbol


@dataclass(frozen=True)
class UniverseResolution:
    universe_key: str
    asset_class: AssetClass
    symbols: tuple[str, ...]
    source: str
    computed_at: datetime | None = None
    degraded: bool = False
    degraded_reason: str | None = None
    symbol_venues: tuple[tuple[str, str], ...] = ()


@runtime_checkable
class UniverseProvider(Protocol):
    universe_key: str
    asset_class: AssetClass
    display_name: str

    def resolve(self, fallback_symbols=()) -> UniverseResolution: ...


@dataclass(frozen=True)
class EquityVolumeUniverseProvider:
    universe_key: str
    display_name: str
    stored_keys: tuple[str, ...]
    asset_class: AssetClass = AssetClass.EQUITY

    def build_candidate(self, market_data_provider, lookback_days, computed_at):
        """Build with the characterized equity eligibility and volume ranking."""
        # Imported lazily to keep the provider/registry dependency one-way while
        # the compatibility builder functions remain directly testable.
        from backend.services.universe import universe_builder

        eligible_symbols, reference_counts = universe_builder.fetch_eligible_symbols(
            market_data_provider
        )
        volume_sum, volume_count, processed_days, skipped_days = (
            universe_builder.build_volume_history(
                eligible_symbols,
                lookback_days,
                market_data_provider,
            )
        )
        records, final_counts = universe_builder.rank_symbols(
            eligible_symbols,
            volume_sum,
            volume_count,
            computed_at,
        )
        return {
            "records": records,
            "reference_counts": reference_counts,
            "processed_days": processed_days,
            "skipped_days": skipped_days,
            "final_counts": final_counts,
        }

    def resolve(self, fallback_symbols=()) -> UniverseResolution:
        try:
            rows = (
                UniverseSymbol.query.filter(
                    UniverseSymbol.asset_class == "equity",
                    UniverseSymbol.universe_key.in_(self.stored_keys),
                )
                .order_by(UniverseSymbol.rank.asc(), UniverseSymbol.universe_key.asc())
                .all()
            )
        except (RuntimeError, SQLAlchemyError) as exc:
            db.session.rollback()
            return UniverseResolution(
                self.universe_key,
                self.asset_class,
                tuple(fallback_symbols),
                "fallback",
                None,
                True,
                f"database lookup failed: {type(exc).__name__}",
            )
        if rows:
            return UniverseResolution(
                self.universe_key,
                self.asset_class,
                tuple(row.symbol for row in rows),
                "database",
                max(row.computed_at for row in rows),
                symbol_venues=tuple(
                    (row.symbol, row.venue or "XNYS") for row in rows
                ),
            )
        return UniverseResolution(
            self.universe_key,
            self.asset_class,
            tuple(fallback_symbols),
            "fallback",
            None,
            True,
            "stored universe is empty",
        )


@dataclass(frozen=True)
class CryptoVolumeUniverseProvider:
    universe_key: str
    display_name: str
    asset_class: AssetClass = AssetClass.CRYPTO

    def build_candidate(self, market_data_provider, lookback_days, computed_at):
        """Build a USD-pair universe ranked by average daily USD notional."""
        from backend.services.universe import universe_builder

        eligible_symbols = universe_builder.fetch_eligible_crypto_symbols(
            market_data_provider
        )
        notional_sum, volume_count, processed_days, skipped_days = (
            universe_builder.build_crypto_volume_history(
                eligible_symbols,
                lookback_days,
                market_data_provider,
            )
        )
        records, final_counts = universe_builder.rank_crypto_symbols(
            eligible_symbols,
            notional_sum,
            volume_count,
            computed_at,
            window_days=lookback_days,
        )
        return {
            "records": records,
            "reference_counts": {"crypto_usd": len(eligible_symbols)},
            "processed_days": processed_days,
            "skipped_days": skipped_days,
            "final_counts": final_counts,
        }

    def resolve(self, fallback_symbols=()) -> UniverseResolution:
        try:
            rows = (
                UniverseSymbol.query.filter_by(
                    asset_class="crypto",
                    universe_key=self.universe_key,
                )
                .order_by(UniverseSymbol.rank.asc())
                .all()
            )
        except (RuntimeError, SQLAlchemyError) as exc:
            db.session.rollback()
            return UniverseResolution(
                self.universe_key,
                self.asset_class,
                tuple(fallback_symbols),
                "fallback",
                None,
                True,
                f"database lookup failed: {type(exc).__name__}",
                tuple((symbol, "GLOBAL_CRYPTO") for symbol in fallback_symbols),
            )
        if rows:
            return UniverseResolution(
                self.universe_key,
                self.asset_class,
                tuple(row.symbol for row in rows),
                "database",
                max(row.computed_at for row in rows),
                symbol_venues=tuple(
                    (row.symbol, row.venue or "GLOBAL_CRYPTO") for row in rows
                ),
            )
        return UniverseResolution(
            self.universe_key,
            self.asset_class,
            tuple(fallback_symbols),
            "fallback",
            None,
            True,
            "stored universe is empty",
            tuple((symbol, "GLOBAL_CRYPTO") for symbol in fallback_symbols),
        )


@dataclass(frozen=True)
class StaticUniverseProvider:
    universe_key: str
    asset_class: AssetClass
    display_name: str
    symbols: tuple[str, ...]

    def resolve(self, fallback_symbols=()) -> UniverseResolution:
        return UniverseResolution(
            self.universe_key,
            self.asset_class,
            self.symbols,
            "static",
            symbol_venues=tuple(
                (symbol, "GLOBAL_CRYPTO") for symbol in self.symbols
            ),
        )
