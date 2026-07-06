from typing import Optional

from pydantic import Field, field_validator

from backend.market_config import TIMEFRAME_CONFIG, normalize_timeframe
from backend.schemas.common import ApiModel


class PatternDetectRequest(ApiModel):
    image: str = Field(min_length=1, max_length=15_000_000)
    symbol: Optional[str] = Field(default=None, max_length=50)
    timeframe: Optional[str] = Field(default=None, max_length=10)

    @field_validator("image")
    @classmethod
    def normalize_image(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Image is required")
        return value

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value):
        if value is None or value == "":
            return None
        return value.strip()

    @field_validator("timeframe")
    @classmethod
    def validate_timeframe(cls, value):
        if value is None or value == "":
            return None
        value = normalize_timeframe(value)
        if value not in TIMEFRAME_CONFIG:
            raise ValueError("Invalid timeframe")
        return value
