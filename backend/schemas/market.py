from typing import Optional

from pydantic import Field, field_validator

from backend.errors import ApiError
from backend.market_config import TIMEFRAME_CONFIG, normalize_timeframe
from backend.schemas.common import ApiModel
from backend.symbols import canonicalize_symbol

VALID_MARKETS = {"stocks", "crypto"}
VALID_TIMEFRAMES = set(TIMEFRAME_CONFIG)


class ScanRequest(ApiModel):
    market: str = Field(default="stocks", max_length=20)
    timeframe: str = Field(default="1D", max_length=10)
    filters: list[str] = Field(min_length=1, max_length=25)
    limit: int = Field(default=20, ge=1, le=50)

    @field_validator("market")
    @classmethod
    def validate_market(cls, value):
        value = value.lower().strip()
        if value not in VALID_MARKETS:
            raise ValueError("Invalid market")
        return value

    @field_validator("timeframe")
    @classmethod
    def validate_timeframe(cls, value):
        value = normalize_timeframe(value)
        if value not in VALID_TIMEFRAMES:
            raise ValueError("Invalid timeframe")
        return value


class SearchQuery(ApiModel):
    q: str = Field(default="", max_length=50)
    market: str = Field(default="stocks", max_length=20)

    @field_validator("market")
    @classmethod
    def validate_market(cls, value):
        value = value.lower().strip()
        if value not in VALID_MARKETS:
            raise ValueError("Invalid market")
        return value


class ChartQuery(ApiModel):
    timeframe: str = Field(default="1D", max_length=10)

    @field_validator("timeframe")
    @classmethod
    def validate_timeframe(cls, value):
        value = normalize_timeframe(value)
        if value not in VALID_TIMEFRAMES:
            raise ValueError("Invalid timeframe")
        return value


class StockQuery(ApiModel):
    market: str = Field(default="stocks", max_length=20)

    @field_validator("market")
    @classmethod
    def validate_market(cls, value):
        value = value.lower().strip()
        if value not in VALID_MARKETS:
            raise ValueError("Invalid market")
        return value


class WatchlistAddRequest(ApiModel):
    symbol: str = Field(min_length=1, max_length=20)
    market: str = Field(default="stocks", max_length=20)
    notes: str = Field(default="", max_length=1000)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol_value(cls, value):
        return canonicalize_symbol(value).provider_symbol

    @field_validator("market")
    @classmethod
    def validate_market(cls, value):
        value = value.lower().strip()
        if value not in VALID_MARKETS:
            raise ValueError("Invalid market")
        return value


class WatchlistUpdateRequest(ApiModel):
    notes: str = Field(default="", max_length=1000)


class UpdateUserRequest(ApiModel):
    role: Optional[str] = Field(default=None, max_length=20)
    plan: Optional[str] = Field(default=None, max_length=20)
    is_active: Optional[bool] = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, value):
        if value is None:
            return value
        value = value.strip().lower()
        if value not in {"user", "admin"}:
            raise ValueError("Invalid role")
        return value

    @field_validator("plan")
    @classmethod
    def validate_plan(cls, value):
        if value is None:
            return value
        value = value.strip().lower()
        if value not in {"free", "premium"}:
            raise ValueError("Invalid plan")
        return value


def normalize_symbol(symbol):
    if not symbol:
        raise ApiError("Symbol is required", 400, "validation_error")
    normalized = canonicalize_symbol(symbol).provider_symbol
    if len(normalized) > 20:
        raise ApiError("Symbol is too long", 400, "validation_error")
    return normalized


class NewsQuery(ApiModel):
    limit: int = Field(default=30, ge=1, le=80)
    days: int = Field(default=30, ge=1, le=365)
    sentiment: Optional[str] = Field(default=None, max_length=20)
    source: Optional[str] = Field(default=None, max_length=80)

    @field_validator("sentiment")
    @classmethod
    def validate_sentiment(cls, value):
        if value is None or value == "":
            return None
        value = value.lower().strip()
        if value not in {"positive", "negative", "neutral"}:
            raise ValueError("Invalid sentiment")
        return value

    @field_validator("source")
    @classmethod
    def normalize_source(cls, value):
        if value is None or value == "":
            return None
        return value.strip()
