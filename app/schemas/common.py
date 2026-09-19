"""Shared Pydantic base configuration."""

from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, PlainSerializer


class ORMModel(BaseModel):
    """Base class for response schemas built from ORM objects."""

    model_config = ConfigDict(from_attributes=True)


def _to_decimal(value: Decimal | int | float | str) -> Decimal:
    """Coerce input to an exact Decimal (via str so floats never accumulate
    binary-representation error)."""
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


Money = Annotated[
    Decimal,
    BeforeValidator(_to_decimal),
    # Serialize back to a JSON number (not a Decimal-as-string) so the API
    # contract stays the same as when prices were plain floats.
    PlainSerializer(lambda value: float(value), return_type=float),
]