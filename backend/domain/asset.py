from enum import Enum


class AssetClass(str, Enum):
    """Canonical asset classification with frozen legacy wire values."""

    EQUITY = "stocks"
    CRYPTO = "crypto"

    @classmethod
    def from_wire(cls, value: "AssetClass | str") -> "AssetClass":
        if isinstance(value, cls):
            return value
        normalized = str(value or "").lower().strip()
        try:
            return cls(normalized)
        except ValueError as exc:
            raise ValueError(f"Unsupported asset class: {value!r}") from exc

    @property
    def wire_value(self) -> str:
        return self.value
