"""
Mirror of the four core CPA tables created in Postgres.
You can `model_dump()` these objects to insert JSONB columns
or just keep them around for type safety.
"""
from __future__ import annotations

import json, hashlib
from enum import Enum
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict
from psycopg.errors import UniqueViolation
# ---------------------------------------------------------------
# Re‑use definitions that already live in cryo_schema.py
from distiller.schemas.structured_output import PropertyType, FactValue


# ---------------------------------------------------------------
# Re‑encode the SQL ENUM so that the app can reason about it
class FactValueKind(str, Enum):
    POINT  = "POINT"
    RANGE  = "RANGE"
    RAW    = "RAW"
    STRUCT = "STRUCT"




def _detect_value_kind(value: FactValue) -> FactValueKind:
    # Only support allowed types in your schema.
    if hasattr(value, "value_type"):  # Pydantic model (Point/Range)
        if value.value_type == "point":
            return FactValueKind.POINT
        elif value.value_type == "range":
            return FactValueKind.RANGE
    elif isinstance(value, (float, int, str)):
        return FactValueKind.RAW
    elif isinstance(value, dict):
        return FactValueKind.STRUCT
    else:
        raise TypeError(
            f"Unsupported FactValue type: {type(value)} ({value!r})"
        )


# ---------------------------------------------------------------
class CPAChemical(BaseModel):
    """Row in table `cpa_chemicals`."""
    id             : UUID | None = None
    inchikey       : Optional[str] = None
    preferred_name : str
    synonyms       : List[str] = Field(default_factory=list)
    created_at     : datetime | None = None
    updated_at     : datetime | None = None

    model_config = ConfigDict(extra="forbid")


class ChemicalProperty(BaseModel):
    """Row in table `chemical_properties`."""
    id          : UUID | None = None
    chemical_id : UUID
    prop_type   : PropertyType

    model_config = ConfigDict(extra="forbid")


class ChemicalPropertyValue(BaseModel):
    """Row in table `chemical_property_values`."""
    id            : UUID | None = None
    property_id   : UUID
    value_kind    : FactValueKind
    numeric_value : Optional[float] = None
    range_min     : Optional[float] = None
    range_max     : Optional[float] = None
    raw_value     : Optional[str | int | float]  = None
    extra         : Optional[Dict[str, Any]] = None
    unit          : Optional[str]  = None
    created_at    : datetime | None = None

    model_config = ConfigDict(extra="forbid")

    # Convenience factory that takes the original FactValue
    @classmethod
    def from_fact_value(
        cls,
        *,
        property_id: UUID,
        value: FactValue,
        unit: Optional[str],
        created_at: datetime | None = None
    ) -> "ChemicalPropertyValue":
        kind = _detect_value_kind(value)
        print(f'[TRACE] from_fact_value: {kind}, {value}')
        kw: Dict[str, Any] = dict(
            property_id=property_id,
            value_kind=kind,
            unit=unit,
            created_at=created_at,
        )
        if kind == FactValueKind.POINT:
            kw["numeric_value"] = float(value.value)
        elif kind == FactValueKind.RANGE:
            kw["range_min"] = float(value.min)
            kw["range_max"] = float(value.max)
        elif kind == FactValueKind.RAW:
            kw["raw_value"] = value
        elif kind == FactValueKind.STRUCT:
            # for dicts (complex/structured value types; future-proof)
            kw["extra"] = value
        else:
            raise TypeError(f"Unknown FactValueKind: {kind}")
        return cls(**kw)


class CPAReference(BaseModel):
    """Row in table `cpa_references`."""
    id                : UUID | None = None
    property_value_id : UUID
    paper_id          : str
    quote             : Optional[str] = None
    link              : Optional[str] = None

    model_config = ConfigDict(extra="forbid")
