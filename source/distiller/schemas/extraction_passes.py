"""
CryoDB – Extraction‑pass schemas  (Markdown‑aware pipeline)
────────────────────────────────────────────────────────────
These pydantic models are used *only at pipeline runtime* to validate
and normalise the JSON returned by the LLM.

• MoleculeCoreData      – Pass 1  (chemicals / “agents”, formulation‑independent)
• ExperimentPass   – Pass 2  (experiments + biological context)
• FormulationPass  – Pass 3  (formulations + dependent properties)
• AgentProperty    – Intrinsic physicochemical properties (new)
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Literal
from uuid import UUID, uuid4

from pydantic import (
    BaseModel,
    Field,
    ConfigDict,
    field_validator,
)
from distiller.schemas.structured_output import (
    ChemicalRole,           # enum (CPA / ADJUVANT / CARRIER)
    Formulation,             # validated formulation (incl. experiment_id, quote…)
    AgentProperty
)


# ────────────────────────────────────────────────────────────────
# 0.  Shared helpers / vocab
# ────────────────────────────────────────────────────────────────
_INCHIKEY_RE = re.compile(r"^[A-Z0-9]{14}-[A-Z0-9]{10}-[A-Z]$")

class ChemicalRole(str, Enum):
    CPA      = "CPA"
    ADJUVANT = "ADJUVANT"
    CARRIER  = "CARRIER"
# ── value helpers (point / range / raw / struct) ─────────────────
class NumericValue(BaseModel):
    value_type: Literal["point"]
    value: float | int
    model_config = ConfigDict(extra="forbid")

class NumericRange(BaseModel):
    value_type: Literal["range"]
    min: float | int
    max: float | int
    model_config = ConfigDict(extra="forbid")

RawScalar = Union[str, float, int]        # e.g. "hydrophilic", 7.4
StructuredValue = Dict[str, Any]          # arbitrary JSON for complex structs

FactValue = Union[NumericValue, NumericRange, RawScalar, StructuredValue]

# schemas/extraction_passes.py  (add at the bottom)

class AgentsPass(BaseModel):
    agents: List[MoleculeCoreData]
    model_config = ConfigDict(extra="forbid")

# ────────────────────────────────────────────────────────────────
# 1.  Pass 1 – MoleculeCoreData (chemicals, formulation‑independent)
# ────────────────────────────────────────────────────────────────
class MoleculeCoreData(BaseModel):
    """One *chemical agent* extracted from the paper."""
    inchikey: Optional[str] = Field(None, description="Use standard InChIKey when possible.")
    preferred_name: str
    synonyms: List[str] = Field(default_factory=list)
    role: ChemicalRole

    model_config = ConfigDict(extra="forbid")

    # ── validation ──────────────────────────────────────────────
    @field_validator("inchikey")
    @classmethod
    def _validate_inchikey(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not _INCHIKEY_RE.match(v):
            raise ValueError("Invalid InChIKey format.")
        return v


# ────────────────────────────────────────────────────────────────
# 2.  Pass 2 – ExperimentPass
# ────────────────────────────────────────────────────────────────
class SampleContext(BaseModel):
    organ: Optional[str] = None
    tissue: Optional[str] = None
    species: Optional[str] = None
    cell_line: Optional[str] = None
    dimensions: Optional[str] = None
    health_status: Optional[str] = None
    developmental_stage: Optional[str] = None

    model_config = ConfigDict(extra="forbid")

class ExperimentItem(BaseModel):
    """A single experiment identified in a heading‑based chunk."""
    id: str = Field(..., description="Deterministic ID (e.g. 'EXPT‑003').")
    performed_in_this_paper: bool = True
    label: Optional[str] = None
    method: Optional[str] = None
    biological_context: Optional[SampleContext] = None
    quote: str
    source_chunk        : List[str] = Field(default_factory=list, description="The source chunk of the experiment. It must be exact extracted from the paper, and fragmented if needed to include all numeric values. Minimum length is 1000 words")
    model_config = ConfigDict(extra="forbid")

class ExperimentPass(BaseModel):
    """Top‑level container returned by the experiment extractor."""

    experiments: List[ExperimentItem]

    model_config = ConfigDict(extra="forbid")


# ────────────────────────────────────────────────────────────────
# 3.  Pass 3 – FormulationPass
# ────────────────────────────────────────────────────────────────
# Top‑level container returned by the LLM
class FormulationPass(BaseModel):
    """
    Wrapper returned by the formulation‑extraction prompt.
    Re‑uses the `Formulation` model defined in distiller.schemas.structured_output.
    """
    formulations: List[Formulation]

    # forbid arbitrary extra keys, just like your other passes
    model_config = ConfigDict(extra="forbid")
# ────────────────────────────────────────────────────────────────
# 4.  Intrinsic physicochemical properties – AgentProperty
# ────────────────────────────────────────────────────────────────
class PropertyType(str, Enum):
    MOLECULAR_MASS                 = "MOLECULAR_MASS"
    SOLUBILITY                     = "SOLUBILITY"
    VISCOSITY                      = "VISCOSITY"
    TG_PRIME                       = "TG_PRIME"
    PARTITION_COEFFICIENT          = "PARTITION_COEFFICIENT"
    DIELECTRIC_CONSTANT            = "DIELECTRIC_CONSTANT"
    THERMAL_CONDUCTIVITY           = "THERMAL_CONDUCTIVITY"
    HEAT_CAPACITY                  = "HEAT_CAPACITY"
    THERMAL_EXPANSION_COEFFICIENT  = "THERMAL_EXPANSION_COEFFICIENT"
    CRYSTALLIZATION_TEMPERATURE    = "CRYSTALLIZATION_TEMPERATURE"
    DIFFUSION_COEFFICIENT          = "DIFFUSION_COEFFICIENT"
    HYDROGEN_BOND_DONORS_ACCEPTORS = "HYDROGEN_BOND_DONORS_ACCEPTORS"
    SOURCE_OF_COMPOUND             = "SOURCE_OF_COMPOUND"
    GRAS_CERTIFICATION             = "GRAS_CERTIFICATION"
    MELTING_POINT                  = "MELTING_POINT"
    HYDROPHOBICITY                 = "HYDROPHOBICITY"
    DENSITY                        = "DENSITY"
    REFRACTIVE_INDEX               = "REFRACTIVE_INDEX"
    SURFACE_TENSION                = "SURFACE_TENSION"
    PH                             = "PH"
    OSMOLALITY_OSMOLARITY          = "OSMOLALITY_OSMOLARITY"
    POLAR_SURFACE_AREA             = "POLAR_SURFACE_AREA"
# ────────────────────────────────────────────────────────────────
# 4‑bis · Pass 1‑B – intrinsic agent properties
# ────────────────────────────────────────────────────────────────
class AgentPropertyPass(BaseModel):
    """
    One JSON envelope per paper – list of intrinsic properties
    for the chemicals that appeared in `MoleculeCoreData`.
    """

    properties: List[AgentProperty]

    model_config = ConfigDict(extra="forbid")


        