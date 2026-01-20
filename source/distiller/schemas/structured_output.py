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

class DependentPropertyType(str, Enum):
    MEMBRANE_PERMEABILITY   = "MEMBRANE_PERMEABILITY"
    TOXICITY                = "TOXICITY"
    LOADING_TEMPERATURE     = "LOADING_TEMPERATURE"
    UNLOADING_TEMPERATURE   = "UNLOADING_TEMPERATURE"
    CRITICAL_COOLING_RATE   = "CRITICAL_COOLING_RATE"
    CRITICAL_WARMING_RATE   = "CRITICAL_WARMING_RATE"
class DependentProperty(BaseModel):
    property_id     : UUID = Field(default_factory=uuid4)
    property_type   : DependentPropertyType
    value           : FactValue          # POINT / RANGE / STRUCT / RAW
    unit            : Optional[str] = None
    quote           : str
    model_config    = ConfigDict(extra="forbid")
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
    amount       : NumericValue
    unit         : Optional[str] = None
    
    quote        : str
    note         : Optional[str] = None
    model_config = ConfigDict(extra="forbid")

    _chk_id = field_validator("agent_id", mode="before")(_validate_inchikey)

class Formulation(BaseModel):
    formulation_id : UUID = Field(default_factory=uuid4)
    label          : str
    components     : List[FormulationComponent]
    experiment_id: str   # links back to ExperimentItem.id
    dependent_properties : List[DependentProperty] = Field(default_factory=list)
    quote          : str = Field(description="The source chunk of the formulation. It must be exact extracted from the paper, and fragmented if needed to include all numeric values. Minimum length is 200 words. If needed, use ... to separate different chunks of text. ALWAYS EXACT QUOTE EXTRACTED FROM TEXT") # must be exact extracted from the paper, and fragmented if needed to include all numeric values
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
    source_chunk        : List[str] = Field(default_factory=list, description="The source chunk of the experiment. It must be exact extracted from the paper, and fragmented if needed to include all numeric values. Minimum length is 1000 words")
    model_config = ConfigDict(extra="forbid")

# ────────────────────────────────────────────────────────────────
# Intrinsic properties of agents
class AgentProperty(BaseModel):  # renamed from CPAProperty
    agent_id     : Optional[str]
    agent_label  : str #agent name
    prop_type    : PropertyType
    value        : FactValue
    unit         : Optional[str] = None
    quote        : str
    model_config = ConfigDict(extra="forbid")

    _chk_id = field_validator("agent_id", mode="before")(_validate_inchikey)

    # This is for making sure we have numerical values for fact values
# --- NEW: hard-type-check the value field ------------------------
    @field_validator("value")
    def _numeric_required(cls, v, info):
        """
        For properties that are *defined* in FACT_UNIT_DEFAULTS
        (i.e. they have a numeric default unit), the value must be a
        PointValue, RangeValue, int or float.  Otherwise raise.
        """
        ptype = info.data.get("prop_type")
        if not ptype:
            return v                      # nothing to compare against

        # UnitSpec present  → this is a numeric property
        unit_spec = getattr(FACT_UNIT_DEFAULTS, ptype.name, None)
        if isinstance(unit_spec, UnitSpec):
            ok_types = (int, float, PointValue, RangeValue)
            if isinstance(v, ok_types):
                return v
            raise ValueError(
                f"{ptype.value} expects a numeric value (point or range); "
                f"got {type(v).__name__}"
            )
        return v   

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

# ────────────────────────────────────────────────────────────────────────
# NEW CODE
# ---------------------------------------------------------------------
# Dependent properties enum (extended)
# ---------------------------------------------------------------------
class DependentPropertyType(str, Enum):
    # existing ones you already had
    MEMBRANE_PERMEABILITY = "MEMBRANE_PERMEABILITY"
    TOXICITY = "TOXICITY"
    LOADING_TEMPERATURE = "LOADING_TEMPERATURE"
    UNLOADING_TEMPERATURE = "UNLOADING_TEMPERATURE"
    CRITICAL_COOLING_RATE = "CRITICAL_COOLING_RATE"
    CRITICAL_WARMING_RATE = "CRITICAL_WARMING_RATE"

    # new ones (from your list)
    POST_THAW_VIABILITY = "POST_THAW_VIABILITY"
    FUNCTIONAL_RECOVERY = "FUNCTIONAL_RECOVERY"
    PLATING_EFFICIENCY = "PLATING_EFFICIENCY"
    POST_THAW_MOTILITY = "POST_THAW_MOTILITY"
    DEVELOPMENTAL_SUCCESS = "DEVELOPMENTAL_SUCCESS"
    MEMBRANE_INTEGRITY = "MEMBRANE_INTEGRITY"
    DNA_INTEGRITY = "DNA_INTEGRITY"
    APOPTOSIS = "APOPTOSIS"
    ATP_CONTENT = "ATP_CONTENT"
    MITOCHONDRIAL_MEMBRANE_POTENTIAL = "MITOCHONDRIAL_MEMBRANE_POTENTIAL"
    ROS_OXIDATIVE_STRESS_LEVEL = "ROS_OXIDATIVE_STRESS_LEVEL"
    TIME_TO_FIRST_ACTIVITY = "TIME_TO_FIRST_ACTIVITY"
    CPA_PERMEABILITY_COEFFICIENT = "CPA_PERMEABILITY_COEFFICIENT"
    WATER_PERMEABILITY_COEFFICIENT = "WATER_PERMEABILITY_COEFFICIENT"
    RESIDUAL_INTRACELLULAR_CPA_CONCENTRATION = "RESIDUAL_INTRACELLULAR_CPA_CONCENTRATION"
    CPA_WASHOUT_HALF_TIME = "CPA_WASHOUT_HALF_TIME"
    ICE_CRYSTAL_MEAN_SIZE = "ICE_CRYSTAL_MEAN_SIZE"
    ICE_VOLUME_FRACTION = "ICE_VOLUME_FRACTION"
    RATE_OF_RECRYSTALLISATION = "RATE_OF_RECRYSTALLISATION"
    MEAN_NUCLEATION_TEMPERATURE = "MEAN_NUCLEATION_TEMPERATURE"
    DEGREE_OF_SUPERCOOLING = "DEGREE_OF_SUPERCOOLING"
    ENTHALPY_OF_CRYSTALLISATION_PER_SAMPLE_MASS = "ENTHALPY_OF_CRYSTALLISATION_PER_SAMPLE_MASS"
    EFFECTIVE_DIFFUSION_COEFFICIENT_TISSUE = "EFFECTIVE_DIFFUSION_COEFFICIENT_TISSUE"
    OSMOTIC_TOLERANCE_LIMITS = "OSMOTIC_TOLERANCE_LIMITS"
    VASCULAR_PERFUSION_FLOW_RESISTANCE = "VASCULAR_PERFUSION_FLOW_RESISTANCE"
    MICROVASCULAR_LEAK = "MICROVASCULAR_LEAK"
    YOUNGS_MODULUS_POST_THAW = "YOUNGS_MODULUS_POST_THAW"
    TENSILE_STRENGTH_POST_THAW = "TENSILE_STRENGTH_POST_THAW"
    ELASTIC_RECOVERY_STRAIN_AT_FAILURE_POST_THAW = "ELASTIC_RECOVERY_STRAIN_AT_FAILURE_POST_THAW"
    FRACTURE_TOUGHNESS_BRITTLENESS_POST_THAW = "FRACTURE_TOUGHNESS_BRITTLENESS_POST_THAW"
    CHANGE_IN_TISSUE_VOLUME = "CHANGE_IN_TISSUE_VOLUME"
    LONG_TERM_SURVIVAL = "LONG_TERM_SURVIVAL"
    DIFFERENTIATION_POTENTIAL_MARKER_EXPRESSION = "DIFFERENTIATION_POTENTIAL_MARKER_EXPRESSION"
    ABERRANT_GROWTH_INCIDENCE = "ABERRANT_GROWTH_INCIDENCE"
    POST_THAW_OXYGEN_CONSUMPTION_RATE = "POST_THAW_OXYGEN_CONSUMPTION_RATE"
    POST_THAW_EXTRACELLULAR_O2_PARTIAL_PRESSURE = "POST_THAW_EXTRACELLULAR_O2_PARTIAL_PRESSURE"
    FUNCTIONAL_LATENCY_DISTRIBUTION = "FUNCTIONAL_LATENCY_DISTRIBUTION"
    ECM_DAMAGE = "ECM_DAMAGE"
    CYTOKINE_CHANGE = "CYTOKINE_CHANGE"
    EXTRACELLULAR_POTASSIUM_CHANGE_POST_THAW = "EXTRACELLULAR_POTASSIUM_CHANGE_POST_THAW"

# ---------------------------------------------------------------------
# Unit defaults (Fact-like style)
# ---------------------------------------------------------------------
class DependentPropertyUnitDefaults(BaseModel):
    POST_THAW_VIABILITY: UnitSpec
    FUNCTIONAL_RECOVERY: UnitSpec
    PLATING_EFFICIENCY: UnitSpec
    POST_THAW_MOTILITY: UnitSpec
    DEVELOPMENTAL_SUCCESS: UnitSpec
    MEMBRANE_INTEGRITY: UnitSpec
    DNA_INTEGRITY: UnitSpec
    APOPTOSIS: UnitSpec
    ATP_CONTENT: UnitSpec
    MITOCHONDRIAL_MEMBRANE_POTENTIAL: UnitSpec
    ROS_OXIDATIVE_STRESS_LEVEL: UnitSpec
    TIME_TO_FIRST_ACTIVITY: UnitSpec
    CRITICAL_COOLING_RATE: UnitSpec
    CRITICAL_WARMING_RATE: UnitSpec
    CPA_PERMEABILITY_COEFFICIENT: UnitSpec
    WATER_PERMEABILITY_COEFFICIENT: UnitSpec
    RESIDUAL_INTRACELLULAR_CPA_CONCENTRATION: UnitSpec
    CPA_WASHOUT_HALF_TIME: UnitSpec
    ICE_CRYSTAL_MEAN_SIZE: UnitSpec
    ICE_VOLUME_FRACTION: UnitSpec
    RATE_OF_RECRYSTALLISATION: UnitSpec
    MEAN_NUCLEATION_TEMPERATURE: UnitSpec
    DEGREE_OF_SUPERCOOLING: UnitSpec
    ENTHALPY_OF_CRYSTALLISATION_PER_SAMPLE_MASS: UnitSpec
    EFFECTIVE_DIFFUSION_COEFFICIENT_TISSUE: UnitSpec
    OSMOTIC_TOLERANCE_LIMITS: UnitSpec
    VASCULAR_PERFUSION_FLOW_RESISTANCE: UnitSpec
    MICROVASCULAR_LEAK: UnitSpec
    YOUNGS_MODULUS_POST_THAW: UnitSpec
    TENSILE_STRENGTH_POST_THAW: UnitSpec
    ELASTIC_RECOVERY_STRAIN_AT_FAILURE_POST_THAW: UnitSpec
    FRACTURE_TOUGHNESS_BRITTLENESS_POST_THAW: UnitSpec
    CHANGE_IN_TISSUE_VOLUME: UnitSpec
    LONG_TERM_SURVIVAL: UnitSpec
    DIFFERENTIATION_POTENTIAL_MARKER_EXPRESSION: UnitSpec
    ABERRANT_GROWTH_INCIDENCE: UnitSpec
    POST_THAW_OXYGEN_CONSUMPTION_RATE: UnitSpec
    POST_THAW_EXTRACELLULAR_O2_PARTIAL_PRESSURE: UnitSpec
    FUNCTIONAL_LATENCY_DISTRIBUTION: UnitSpec
    ECM_DAMAGE: UnitSpec
    CYTOKINE_CHANGE: UnitSpec
    EXTRACELLULAR_POTASSIUM_CHANGE_POST_THAW: UnitSpec

    # Optional: include your legacy generic ones if you want validation on them too
    MEMBRANE_PERMEABILITY: Optional[UnitSpec] = None
    TOXICITY: Optional[UnitSpec] = None
    LOADING_TEMPERATURE: Optional[UnitSpec] = None
    UNLOADING_TEMPERATURE: Optional[UnitSpec] = None

    model_config = ConfigDict(extra="forbid")

DEPENDENT_PROPERTY_UNIT_DEFAULTS = DependentPropertyUnitDefaults(
    POST_THAW_VIABILITY=UnitSpec(defaultUnit="%", units=["%"]),
    FUNCTIONAL_RECOVERY=UnitSpec(defaultUnit="% of baseline", units=["% of baseline"]),
    PLATING_EFFICIENCY=UnitSpec(defaultUnit="%", units=["%", "CFU"]),
    POST_THAW_MOTILITY=UnitSpec(defaultUnit="%", units=["%"]),
    DEVELOPMENTAL_SUCCESS=UnitSpec(defaultUnit="%", units=["%", "stage"]),
    MEMBRANE_INTEGRITY=UnitSpec(defaultUnit="%", units=["%", "U/L", "U·L^-1", "U·L⁻¹"]),
    DNA_INTEGRITY=UnitSpec(defaultUnit="%", units=["%"]),
    APOPTOSIS=UnitSpec(defaultUnit="%", units=["%", "RFU"]),
    ATP_CONTENT=UnitSpec(defaultUnit="nmol/mg protein", units=["nmol/mg protein", "% of baseline"]),
    MITOCHONDRIAL_MEMBRANE_POTENTIAL=UnitSpec(defaultUnit="% of control", units=["% of control", "RFU"]),
    ROS_OXIDATIVE_STRESS_LEVEL=UnitSpec(defaultUnit="% change", units=["% change", "RFU"]),
    TIME_TO_FIRST_ACTIVITY=UnitSpec(defaultUnit="min", units=["min", "h", "hours"]),
    CRITICAL_COOLING_RATE=UnitSpec(defaultUnit="degC/min", units=["degC/min", "°C/min", "°C·min^-1", "°C·min⁻¹"]),
    CRITICAL_WARMING_RATE=UnitSpec(defaultUnit="degC/min", units=["degC/min", "°C/min", "°C·min^-1", "°C·min⁻¹"]),
    CPA_PERMEABILITY_COEFFICIENT=UnitSpec(defaultUnit="cm/s", units=["cm/s", "um/s", "µm/s"]),
    WATER_PERMEABILITY_COEFFICIENT=UnitSpec(defaultUnit="cm/s", units=["cm/s", "um/s", "µm/s"]),
    RESIDUAL_INTRACELLULAR_CPA_CONCENTRATION=UnitSpec(defaultUnit="mol/L", units=["mol/L", "% of initial"]),
    CPA_WASHOUT_HALF_TIME=UnitSpec(defaultUnit="min", units=["min"]),
    ICE_CRYSTAL_MEAN_SIZE=UnitSpec(defaultUnit="um", units=["um", "µm"]),
    ICE_VOLUME_FRACTION=UnitSpec(defaultUnit="%", units=["%"]),
    RATE_OF_RECRYSTALLISATION=UnitSpec(defaultUnit="um/h", units=["um/h", "µm/h", "um2/s", "µm²/s", "µm²·s^-1", "µm²·s⁻¹"]),
    MEAN_NUCLEATION_TEMPERATURE=UnitSpec(defaultUnit="degC", units=["degC", "°C"]),
    DEGREE_OF_SUPERCOOLING=UnitSpec(defaultUnit="degC", units=["degC", "°C"]),
    ENTHALPY_OF_CRYSTALLISATION_PER_SAMPLE_MASS=UnitSpec(defaultUnit="J/g", units=["J/g"]),
    EFFECTIVE_DIFFUSION_COEFFICIENT_TISSUE=UnitSpec(defaultUnit="cm2/s", units=["cm2/s", "m2/s"]),
    OSMOTIC_TOLERANCE_LIMITS=UnitSpec(defaultUnit="mOsm/kg", units=["mOsm/kg"]),
    VASCULAR_PERFUSION_FLOW_RESISTANCE=UnitSpec(defaultUnit="mL/min/g", units=["mL/min/g", "mmHg*min/mL", "mmHg·min·mL^-1", "mmHg·min·ml⁻¹"]),
    MICROVASCULAR_LEAK=UnitSpec(defaultUnit="ug/g", units=["ug/g", "µg/g", "% leakage"]),
    YOUNGS_MODULUS_POST_THAW=UnitSpec(defaultUnit="kPa", units=["kPa", "% of baseline"]),
    TENSILE_STRENGTH_POST_THAW=UnitSpec(defaultUnit="kPa", units=["kPa", "% of baseline"]),
    ELASTIC_RECOVERY_STRAIN_AT_FAILURE_POST_THAW=UnitSpec(defaultUnit="%", units=["%"]),
    FRACTURE_TOUGHNESS_BRITTLENESS_POST_THAW=UnitSpec(defaultUnit="J/m2", units=["J/m2", "J·m^-2", "J·m⁻²", "% of baseline"]),
    CHANGE_IN_TISSUE_VOLUME=UnitSpec(defaultUnit="%", units=["%"]),
    LONG_TERM_SURVIVAL=UnitSpec(defaultUnit="%", units=["%"]),
    DIFFERENTIATION_POTENTIAL_MARKER_EXPRESSION=UnitSpec(defaultUnit="fold-change", units=["fold-change", "% positive"]),
    ABERRANT_GROWTH_INCIDENCE=UnitSpec(defaultUnit="%", units=["%", "count"]),
    POST_THAW_OXYGEN_CONSUMPTION_RATE=UnitSpec(defaultUnit="pmol/min/1e6 cells", units=["pmol/min/1e6 cells", "pmol/min/10^6 cells", "% of baseline"]),
    POST_THAW_EXTRACELLULAR_O2_PARTIAL_PRESSURE=UnitSpec(defaultUnit="mmHg", units=["mmHg", "kPa"]),
    FUNCTIONAL_LATENCY_DISTRIBUTION=UnitSpec(defaultUnit="min", units=["min", "h", "hours"]),
    ECM_DAMAGE=UnitSpec(defaultUnit="% area", units=["% area", "%"]),
    CYTOKINE_CHANGE=UnitSpec(defaultUnit="fold-change", units=["fold-change", "pg/mL", "pg·mL^-1"]),
    EXTRACELLULAR_POTASSIUM_CHANGE_POST_THAW=UnitSpec(defaultUnit="mmol/L", units=["mmol/L", "% of baseline"]),

    # Optional defaults for legacy enums (if you want validation on them too)
    MEMBRANE_PERMEABILITY=UnitSpec(defaultUnit="cm2/s", units=["cm2/s", "m2/s"]) ,
    TOXICITY=UnitSpec(defaultUnit="qualitative", units=["qualitative", "IC50 uM", "IC50 µM"]),
    LOADING_TEMPERATURE=UnitSpec(defaultUnit="degC", units=["degC", "°C", "K", "degK"]),
    UNLOADING_TEMPERATURE=UnitSpec(defaultUnit="degC", units=["degC", "°C", "K", "degK"]),
)

# Convenience lookup: Enum -> UnitSpec
DEPENDENT_PROPERTY_UNITS = {
    DependentPropertyType[k]: getattr(DEPENDENT_PROPERTY_UNIT_DEFAULTS, k, None)
    for k in DEPENDENT_PROPERTY_UNIT_DEFAULTS.model_dump().keys()
    if k in DependentPropertyType.__members__
}

# Minimal aliases normalizer to accept common unicode/ASCII forms
UNIT_ALIASES = {
    "°c": "degC",
    "°c/min": "degC/min",
    "°c·min^-1": "degC/min",
    "°c·min⁻¹": "degC/min",
    "µm": "um",
    "μm": "um",
    "µm/h": "um/h",
    "µm2/s": "um2/s",
    "µm²/s": "um2/s",
    "µm²·s^-1": "um2/s",
    "µm²·s⁻¹": "um2/s",
    "u·l^-1": "U/L",
    "u·l⁻¹": "U/L",
    "ml": "mL",
    "mmhg·min·ml^-1": "mmHg*min/mL",
    "mmhg·min·ml⁻¹": "mmHg*min/mL",
    "pg·ml^-1": "pg/mL",
    "pg·ml⁻¹": "pg/mL",
    "j·m^-2": "J/m2",
    "j·m⁻²": "J/m2",
}

def _normalize_unit(u: Optional[str]) -> Optional[str]:
    if u is None:
        return None
    norm = u.strip()
    # unify spacing
    norm = norm.replace(" ", "")
    # lowercased key for aliases that are case-insensitive
    lower_key = norm.lower()
    if lower_key in UNIT_ALIASES:
        return UNIT_ALIASES[lower_key]
    return norm  # e.g., "%", "RFU", "CFU", "kPa", "mmHg", "mol/L", etc.

# ---------------------------------------------------------------------
# DependentProperty model + validation
# ---------------------------------------------------------------------
# Assumes FactValue is defined in your codebase.
class DependentProperty(BaseModel):
    property_id: UUID = Field(default_factory=uuid4)
    property_type: DependentPropertyType
    value: "FactValue"  # POINT / RANGE / STRUCT / RAW
    unit: Optional[str] = None
    quote: str

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _validate_and_fill_unit(self):
        spec = DEPENDENT_PROPERTY_UNITS.get(self.property_type)
        # If we have a spec, enforce/auto-fill units
        if spec is not None:
            allowed = { _normalize_unit(u) for u in spec.units }
            if self.unit is None:
                self.unit = spec.defaultUnit
            norm = _normalize_unit(self.unit)
            if norm not in allowed:
                raise ValueError(
                    f"Unit '{self.unit}' not allowed for {self.property_type}. "
                    f"Allowed: {sorted(allowed)}"
                )
            # store normalized canonical unit for consistency
            # (keep original human-readable forms in quotes if needed)
            self.unit = norm
        return self

class Experiment_Properties(BaseModel):
    """
    Composition wrapper: preserves Experiment unchanged and adds dependent_properties.
    """
    experiment: Experiment
    dependent_properties: List[DependentProperty] = Field(
        default_factory=list,
        description="Measured/derived outcomes (validated units per DependentPropertyType).",
    )

    model_config = ConfigDict(extra="forbid")

    @classmethod
    def wrap(
        cls,
        e: Experiment,
        dependent_properties: Optional[List[DependentProperty]] = None,
    ) -> "Experiment_Properties":
        return cls(experiment=e, dependent_properties=list(dependent_properties or []))

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