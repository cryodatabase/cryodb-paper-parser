/* ════════════════════════════════════════════════════════════════
   CryoDB – CPA core schema
   public.{cpa_chemicals, chemical_properties,
           chemical_property_values, cpa_references}
   © CryoDB – rev. 2025‑07‑27
   ════════════════════════════════════════════════════════════════ */

--------------------------------------------------------------------
-- 1. Extensions (idempotent)
--------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";   -- uuid_generate_v4()
CREATE EXTENSION IF NOT EXISTS btree_gist;    -- GiST on NUMRANGE
CREATE EXTENSION IF NOT EXISTS vector;         -- pgvector (embeddings)
--------------------------------------------------------------------
-- 2. Work inside the public schema
--------------------------------------------------------------------
SET search_path TO public;

--------------------------------------------------------------------
-- 3. Enum types
--------------------------------------------------------------------
-- 3.a  Property types (matches cryo_schema.PropertyType)
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'property_type') THEN
    CREATE TYPE property_type AS ENUM (
      'MOLECULAR_MASS',
      'SOLUBILITY',
      'VISCOSITY',
      'TG_PRIME',
      'PARTITION_COEFFICIENT',
      'DIELECTRIC_CONSTANT',
      'THERMAL_CONDUCTIVITY',
      'HEAT_CAPACITY',
      'THERMAL_EXPANSION_COEFFICIENT',
      'CRYSTALLIZATION_TEMPERATURE',
      'DIFFUSION_COEFFICIENT',
      'HYDROGEN_BOND_DONORS_ACCEPTORS',
      'SOURCE_OF_COMPOUND',
      'GRAS_CERTIFICATION',
      'MELTING_POINT',
      'HYDROPHOBICITY',
      'DENSITY',
      'REFRACTIVE_INDEX',
      'SURFACE_TENSION',
      'PH',
      'OSMOLALITY_OSMOLARITY',
      'POLAR_SURFACE_AREA'
    );
  END IF;
END$$;

-- 3.b  Kind of FactValue stored in each row
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'fact_value_kind') THEN
    CREATE TYPE fact_value_kind AS ENUM ('POINT', 'RANGE', 'RAW', 'STRUCT');
  END IF;
END$$;

-- 3.c  Role of each chemical (new)
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'cryoprotectant_roles') THEN
    CREATE TYPE cryoprotectant_roles AS ENUM ('CPA', 'Adjuvant', 'Carrier');
  END IF;
END$$;

--------------------------------------------------------------------
-- 4. Table: cpa_chemicals
--------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS citext;

CREATE TABLE IF NOT EXISTS cpa_chemical_aliases (
  id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  chemical_id  UUID   NOT NULL REFERENCES cpa_chemicals(id) ON DELETE CASCADE,
  alias        CITEXT UNIQUE NOT NULL,
  embedding    vector(3072) NOT NULL,
  is_preferred BOOLEAN DEFAULT FALSE,
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_alias_global
    ON cpa_chemical_aliases (alias);


CREATE TABLE IF NOT EXISTS cpa_chemicals (
  id             UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
  inchikey       TEXT UNIQUE,
  preferred_name TEXT        NOT NULL,
  synonyms       JSONB       NOT NULL DEFAULT '[]',  -- array of strings
  role           cryoprotectant_roles,
  embedding      vector(3072),
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (inchikey IS NULL OR inchikey ~* '^[A-Z]{14}-[A-Z]{10}-[A-Z]$')
);

-- Trigger function to auto‑update the timestamp
CREATE OR REPLACE FUNCTION _touch_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS
$$BEGIN NEW.updated_at = now(); RETURN NEW; END;$$;

DROP TRIGGER IF EXISTS trg_touch_cpa_chemicals ON cpa_chemicals;
CREATE TRIGGER trg_touch_cpa_chemicals
BEFORE UPDATE ON cpa_chemicals
FOR EACH ROW EXECUTE FUNCTION _touch_updated_at();


--------------------------------------------------------------------
-- 5. Table: chemical_properties
--------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS chemical_properties (
  id           UUID          PRIMARY KEY DEFAULT uuid_generate_v4(),
  chemical_id  UUID          NOT NULL REFERENCES cpa_chemicals(id) ON DELETE CASCADE,
  prop_type    property_type NOT NULL,
  UNIQUE (chemical_id, prop_type)
);

CREATE INDEX IF NOT EXISTS idx_chemprop_chemical
  ON chemical_properties (chemical_id);

--------------------------------------------------------------------
-- 6. Table: chemical_property_values  (hybrid value layout)
--------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS chemical_property_values (
  id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  property_id   UUID NOT NULL REFERENCES chemical_properties(id) ON DELETE CASCADE,

  /* ---- one of these representations is mandatory --------------- */
  value_kind    fact_value_kind NOT NULL,

  numeric_value NUMERIC,         -- for POINT
  range_min     NUMERIC,         -- for RANGE
  range_max     NUMERIC,         -- for RANGE
  raw_value     TEXT,            -- for RAW
  extra         JSONB,           -- for STRUCT

  unit          TEXT,            -- optional unit
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),

  CHECK (
        (value_kind = 'POINT'  AND numeric_value IS NOT NULL
                               AND range_min IS NULL AND range_max IS NULL
                               AND raw_value IS NULL AND extra IS NULL)
     OR (value_kind = 'RANGE'  AND range_min IS NOT NULL AND range_max IS NOT NULL
                               AND numeric_value IS NULL
                               AND raw_value IS NULL AND extra IS NULL)
     OR (value_kind = 'RAW'    AND raw_value IS NOT NULL
                               AND numeric_value IS NULL
                               AND range_min IS NULL AND range_max IS NULL
                               AND extra IS NULL)
     OR (value_kind = 'STRUCT' AND extra IS NOT NULL
                               AND numeric_value IS NULL
                               AND range_min IS NULL AND range_max IS NULL
                               AND raw_value IS NULL)
  )
);

-- POINT value index (BTREE)
CREATE INDEX IF NOT EXISTS idx_propval_point
  ON chemical_property_values (property_id, numeric_value)
  WHERE value_kind = 'POINT';

-- RANGE value index (GiST on numrange)
CREATE INDEX IF NOT EXISTS idx_propval_range
  ON chemical_property_values
  USING gist (property_id, numrange(range_min, range_max))
  WHERE value_kind = 'RANGE';

-- STRUCT value index (GIN on JSONB)
CREATE INDEX IF NOT EXISTS idx_propval_struct
  ON chemical_property_values USING gin (extra)
  WHERE value_kind = 'STRUCT';

--------------------------------------------------------------------
-- 7. Table: cpa_references  (provenance)
--------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cpa_references (
  id                 UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  property_value_id  UUID NOT NULL REFERENCES chemical_property_values(id) ON DELETE CASCADE,
  paper_id           TEXT NOT NULL,     -- DOI / arXiv / UUID
  quote              TEXT,
  link               TEXT
);

CREATE INDEX IF NOT EXISTS idx_ref_propval
  ON cpa_references (property_value_id);
/* Extension (only once per DB) */
CREATE EXTENSION IF NOT EXISTS citext;

-- Option A: change the column type
ALTER TABLE cpa_chemicals
  ALTER COLUMN preferred_name TYPE citext;

