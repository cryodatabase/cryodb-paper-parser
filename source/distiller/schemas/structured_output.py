# cryo_schema.py
from __future__ import annotations

import re
from enum import Enum
from typing import Any, Dict, List, Tuple, Union, Optional, Annotated, Literal
from uuid import UUID, uuid4

from pydantic import (
    BaseModel, Field, HttpUrl, ConfigDict,
    field_validator, model_validator
)

# ────────────────────────────────────────────────────────────────
# Regex patterns for external IDs
_DOI_PAT   = re.compile(r"^10\.\d{4,9}/[-._;()/:A-Z0-9]+$", re.I)
_ARXIV_PAT = re.compile(r"^(arXiv:)?\d{4}\.\d{4,5}(v\d+)?$", re.I)
_INCHI_PAT = re.compile(r"^[A-Z]{14}-[A-Z]{10}-[A-Z]$", re.I)  # 14‑10‑1 blocks

def _validate_inchikey(v: Optional[str]) -> Optional[str]:
    """Return None or a normalised (upper‑case) InChIKey."""
    if v is None:
        return v
    if not _INCHI_PAT.match(v):
        raise ValueError(
            "agent_id must be a valid InChIKey "
            "(e.g. 'BSYNRYMUTXBXSQ-UHFFFAOYSA-N') or null"
        )
    return v.upper()

# ────────────────────────────────────────────────────────────────
# Property types — intrinsic facts
class PropertyType(str, Enum):  # renamed from FactType
    MOLECULAR_MASS                = "MOLECULAR_MASS"
    SOLUBILITY                    = "SOLUBILITY"
    VISCOSITY                     = "VISCOSITY"
    TG_PRIME                      = "TG_PRIME"
    PARTITION_COEFFICIENT         = "PARTITION_COEFFICIENT"
    DIELECTRIC_CONSTANT           = "DIELECTRIC_CONSTANT"
    THERMAL_CONDUCTIVITY          = "THERMAL_CONDUCTIVITY"
    HEAT_CAPACITY                 = "HEAT_CAPACITY"
    THERMAL_EXPANSION_COEFFICIENT = "THERMAL_EXPANSION_COEFFICIENT"
    CRYSTALLIZATION_TEMPERATURE   = "CRYSTALLIZATION_TEMPERATURE"
    DIFFUSION_COEFFICIENT         = "DIFFUSION_COEFFICIENT"
    HYDROGEN_BOND_DONORS_ACCEPTORS= "HYDROGEN_BOND_DONORS_ACCEPTORS"
    SOURCE_OF_COMPOUND            = "SOURCE_OF_COMPOUND"
    GRAS_CERTIFICATION            = "GRAS_CERTIFICATION"
    MELTING_POINT                 = "MELTING_POINT"
    HYDROPHOBICITY                = "HYDROPHOBICITY"
    DENSITY                       = "DENSITY"
    REFRACTIVE_INDEX              = "REFRACTIVE_INDEX"
    SURFACE_TENSION               = "SURFACE_TENSION"
    PH                            = "PH"
    OSMOLALITY_OSMOLARITY         = "OSMOLALITY_OSMOLARITY"
    POLAR_SURFACE_AREA            = "POLAR_SURFACE_AREA"

# ────────────────────────────────────────────────────────────────
# Numeric values (point / range)
class PointValue(BaseModel):
    value_type : Literal["point"]
    value      : float
    model_config = ConfigDict(extra="forbid")

class RangeValue(BaseModel):
    value_type : Literal["range"]
    min        : float
    max        : float
    model_config = ConfigDict(extra="forbid")

NumericValue = Annotated[Union[PointValue, RangeValue], Field(discriminator="value_type")]
RawScalar    = Union[float, int, str]
FactValue    = Union[NumericValue, RawScalar, Dict[str, Any]]

# ────────────────────────────────────────────────────────────────
# Units (unchanged)
class UnitSpec(BaseModel):
    defaultUnit : str
    units       : List[str]
    model_config = ConfigDict(extra="forbid")

class FactUnitDefaults(BaseModel):
    MOLECULAR_MASS                : UnitSpec
    SOLUBILITY                    : UnitSpec
    VISCOSITY                     : UnitSpec
    TG_PRIME                      : UnitSpec
    PARTITION_COEFFICIENT         : UnitSpec
    DIELECTRIC_CONSTANT           : Optional[UnitSpec]
    THERMAL_CONDUCTIVITY          : UnitSpec
    HEAT_CAPACITY                 : UnitSpec
    THERMAL_EXPANSION_COEFFICIENT : UnitSpec
    CRYSTALLIZATION_TEMPERATURE   : UnitSpec
    DIFFUSION_COEFFICIENT         : UnitSpec
    HYDROGEN_BOND_DONORS_ACCEPTORS: UnitSpec
    SOURCE_OF_COMPOUND            : UnitSpec
    GRAS_CERTIFICATION            : UnitSpec
    MELTING_POINT                 : UnitSpec
    HYDROPHOBICITY                : UnitSpec
    DENSITY                       : UnitSpec
    REFRACTIVE_INDEX              : Optional[UnitSpec]
    SURFACE_TENSION               : UnitSpec
    PH                            : Optional[UnitSpec]
    OSMOLALITY_OSMOLARITY         : UnitSpec
    POLAR_SURFACE_AREA            : UnitSpec
    model_config = ConfigDict(extra="forbid")

FACT_UNIT_DEFAULTS = FactUnitDefaults(
    MOLECULAR_MASS                = UnitSpec(defaultUnit="g/mol",       units=["g/mol", "Da", "kDa"]),
    SOLUBILITY                    = UnitSpec(defaultUnit="mg/mL",       units=["mg/mL", "g/100 mL", "% w/v"]),
    VISCOSITY                     = UnitSpec(defaultUnit="mPa.s",       units=["mPa.s", "cP"]),
    TG_PRIME                      = UnitSpec(defaultUnit="degC",        units=["degC", "degK"]),
    PARTITION_COEFFICIENT         = UnitSpec(defaultUnit="logP",        units=["logP"]),
    DIELECTRIC_CONSTANT           = None,
    THERMAL_CONDUCTIVITY          = UnitSpec(defaultUnit="W/(m.K)",     units=["W/(m.K)"]),
    HEAT_CAPACITY                 = UnitSpec(defaultUnit="J/(g.K)",     units=["J/(g.K)", "J/(mol.K)"]),
    THERMAL_EXPANSION_COEFFICIENT = UnitSpec(defaultUnit="1/K",         units=["1/K"]),
    CRYSTALLIZATION_TEMPERATURE   = UnitSpec(defaultUnit="degC",        units=["degC", "degK"]),
    DIFFUSION_COEFFICIENT         = UnitSpec(defaultUnit="m2/s",        units=["m2/s", "cm2/s"]),
    HYDROGEN_BOND_DONORS_ACCEPTORS= UnitSpec(defaultUnit="count",       units=["count"]),
    SOURCE_OF_COMPOUND            = UnitSpec(defaultUnit="text",        units=["text"]),
    GRAS_CERTIFICATION            = UnitSpec(defaultUnit="boolean",     units=["boolean"]),
    MELTING_POINT                 = UnitSpec(defaultUnit="degC",        units=["degC", "degK"]),
    HYDROPHOBICITY                = UnitSpec(defaultUnit="qualitative", units=["qualitative"]),
    DENSITY                       = UnitSpec(defaultUnit="g/cm3",       units=["g/cm3", "kg/m3"]),
    REFRACTIVE_INDEX              = None,
    SURFACE_TENSION               = UnitSpec(defaultUnit="mN/m",        units=["mN/m", "dyn/cm"]),
    PH                            = None,
    OSMOLALITY_OSMOLARITY         = UnitSpec(defaultUnit="Osmol/kg",    units=["Osmol/kg", "Osmol/L"]),
    POLAR_SURFACE_AREA            = UnitSpec(defaultUnit="A2",          units=["A2"]),
)

# ────────────────────────────────────────────────────────────────
# Base class for dimension types
class DimensionBase(BaseModel):
    quote: Optional[str] = None
    note: Optional[str] = None

    model_config = {
        "extra": "forbid"
    }

# 1. Organ-scale: mass
class MassDimension(DimensionBase):
    kind: Literal["MASS"] = "MASS"
    mass: float
    unit: Literal["g", "mg"]

# 2. Cell-scale: volume / diameter
class VolumeDimension(DimensionBase):
    kind: Literal["VOLUME"] = "VOLUME"
    volume: float
    unit: Literal["nL", "pL", "µm3"]

class DiameterDimension(DimensionBase):
    kind: Literal["DIAMETER"] = "DIAMETER"
    diameter: float
    unit: Literal["µm"]

# 3. Tissue-scale: geometric size
class SizeDimension(DimensionBase):
    kind: Literal["SIZE"] = "SIZE"
    width: float
    height: float
    thickness: Optional[float] = None
    unit: Literal["mm", "µm"]

# Discriminated union for Dimension
Dimension = Annotated[
    Union[MassDimension, VolumeDimension, DiameterDimension, SizeDimension],
    Field(discriminator="kind")
]


class SampleContext(BaseModel):
    species             : Optional[str] = None
    organ               : Optional[str] = None
    tissue              : Optional[str] = None
    cell_line           : Optional[str] = None
    developmental_stage : Optional[str] = None
    health_status       : Optional[str] = None
    dimensions          : Optional[Dimension] = None   # new
    model_config = ConfigDict(extra="forbid")

# ────────────────────────────────────────────────────────────────
# Central registry of chemicals (single place for label)
class ChemicalAgent(BaseModel):
    agent_id : Optional[str] = Field(
        None, description="InChIKey of the chemical (or null if unknown)."
    )
    label    : Optional[str] = None
    model_config = ConfigDict(extra="forbid")

    _chk_id = field_validator("agent_id", mode="before")(_validate_inchikey)

# ────────────────────────────────────────────────────────────────
# Formulation layer
class ChemicalRole(str, Enum):  # formerly ComponentRole
    CPA      = "CPA"
    ADJUVANT = "ADJUVANT"
    CARRIER  = "CARRIER"

class FormulationComponent(BaseModel):
    component_id : UUID = Field(default_factory=uuid4)
    role         : ChemicalRole
    label        : str
    agent_id     : Optional[str] = Field(
        None, description="InChIKey of the chemical component."
    )
    amount       : Optional[NumericValue] = None
    unit         : Optional[str] = None
    quote        : str
    note         : Optional[str] = None
    model_config = ConfigDict(extra="forbid")

    _chk_id = field_validator("agent_id", mode="before")(_validate_inchikey)

class Formulation(BaseModel):
    formulation_id : UUID = Field(default_factory=uuid4)
    label          : str
    components     : List[FormulationComponent]
    experiment_id  : UUID
    quote          : str
    model_config   = ConfigDict(extra="forbid")

# ────────────────────────────────────────────────────────────────
# Experiment layer
class Experiment(BaseModel):
    experiment_id       : UUID = Field(default_factory=uuid4)
    performed_in_this_paper: bool
    label               : Optional[str] = None
    method              : Optional[str] = None
    biological_context  : Optional[SampleContext] = None
    quote               : str
    model_config = ConfigDict(extra="forbid")

# ────────────────────────────────────────────────────────────────
# Intrinsic properties of agents
class AgentProperty(BaseModel):  # renamed from CPAProperty
    property_id  : UUID = Field(default_factory=uuid4)
    agent_id     : Optional[str]
    agent_label  : str #agent name
    prop_type    : PropertyType
    value        : FactValue
    unit         : Optional[str] = None
    quote        : str
    model_config = ConfigDict(extra="forbid")

    _chk_id = field_validator("agent_id", mode="before")(_validate_inchikey)

    # Ensure supplied unit is legal for the prop_type
    @field_validator("unit")
    def _unit_allowed(cls, v: Optional[str], info):
        if v is None:
            return v
        ptype = info.data.get("prop_type")
        if ptype is None:
            return v
        unit_spec = getattr(FACT_UNIT_DEFAULTS, ptype.name)
        # If no UnitSpec defined, skip validation
        if unit_spec is None:
            return v
        if v not in unit_spec.units:
            raise ValueError(
                f"Unit '{v}' invalid for prop_type '{ptype}'. "
                f"Allowed: {unit_spec.units}"
            )
        return v

# ────────────────────────────────────────────────────────────────
# Paper‑level root object
class CPAPaperData(BaseModel):
    paper_id    : str
    title       : str
    link        : Optional[HttpUrl] = None

    chemical_agents  : List[ChemicalAgent]
    experiments      : List[Experiment]
    formulations     : List[Formulation]
    agent_properties : List[AgentProperty]

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    # Validate paper_id shape
    @field_validator("paper_id")
    @classmethod
    def _valid_paper_id(cls, v: str) -> str:
        # Accept UUID
        try:
            UUID(v)
            return v
        except ValueError:
            pass
        # Accept DOI or arXiv
        if _DOI_PAT.match(v) or _ARXIV_PAT.match(v):
            return v
        raise ValueError("paper_id must be a DOI, arXiv ID, or UUID")

    # Cross‑reference checks
    @model_validator(mode="after")
    def _check_refs(self):
        exp_ids   = {e.experiment_id for e in self.experiments}
        agent_ids = {a.agent_id for a in self.chemical_agents if a.agent_id}

        # Every formulation must reference an existing experiment
        for f in self.formulations:
            if f.experiment_id not in exp_ids:
                raise ValueError(
                    f"Formulation {f.formulation_id} "
                    f"references missing experiment_id {f.experiment_id}"
                )
            # Each component's agent_id (if any) must exist in registry
            for c in f.components:
                if c.agent_id and c.agent_id not in agent_ids:
                    raise ValueError(
                        f"Component {c.component_id} uses unknown agent_id '{c.agent_id}'"
                    )

        # Each agent_property must refer to a registered agent (if specified)
        for ap in self.agent_properties:
            if ap.agent_id and ap.agent_id not in agent_ids:
                raise ValueError(
                    f"AgentProperty {ap.property_id} refers to unknown agent_id "
                    f"'{ap.agent_id}'"
                )
        return self