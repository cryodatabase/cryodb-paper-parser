/* ════════════════════════════════════════════════════════════════
   CryoDB – Minimal schema for Python‑side merge strategy
   Version: 2025‑07‑29
   Run with:  psql -f 00_base_schema.sql
   ════════════════════════════════════════════════════════════════ */
BEGIN;

--------------------------------------------------------------------
-- 1. Extensions  (idempotent)
--------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";     -- uuid_generate_v4()
CREATE EXTENSION IF NOT EXISTS citext;          -- case‑insensitive text
CREATE EXTENSION IF NOT EXISTS vector;          -- pgvector (≥ 0.5.2)

--------------------------------------------------------------------
-- 2. Enumerated types
--------------------------------------------------------------------
-- 2.a Role of each cryoprotectant agent
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'cryoprotectant_roles') THEN
    CREATE TYPE cryoprotectant_roles AS ENUM ('CPA', 'Adjuvant', 'Carrier');
  END IF;
END$$;

-- 2.b Property type vocabulary  (used by agent‑properties)
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'property_type') THEN
    CREATE TYPE property_type AS ENUM (
      'MOLECULAR_MASS', 'SOLUBILITY', 'VISCOSITY', 'TG_PRIME',
      'PARTITION_COEFFICIENT', 'DIELECTRIC_CONSTANT', 'THERMAL_CONDUCTIVITY',
      'HEAT_CAPACITY', 'THERMAL_EXPANSION_COEFFICIENT',
      'CRYSTALLIZATION_TEMPERATURE', 'DIFFUSION_COEFFICIENT',
      'HYDROGEN_BOND_DONORS_ACCEPTORS', 'SOURCE_OF_COMPOUND',
      'GRAS_CERTIFICATION', 'MELTING_POINT', 'HYDROPHOBICITY', 'DENSITY',
      'REFRACTIVE_INDEX', 'SURFACE_TENSION', 'PH', 'OSMOLALITY_OSMOLARITY',
      'POLAR_SURFACE_AREA'
    );
  END IF;
END$$;

-- 2.c Kind of hybrid value stored in chemical_property_values
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'fact_value_kind') THEN
    CREATE TYPE fact_value_kind AS ENUM ('POINT', 'RANGE', 'RAW', 'STRUCT');
  END IF;
END$$;

--------------------------------------------------------------------
-- 3. Core tables (agents + aliases)
--------------------------------------------------------------------
/* 3.a cpa_chemicals */
CREATE TABLE IF NOT EXISTS cpa_chemicals (
  id             UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
  inchikey       TEXT UNIQUE,
  preferred_name TEXT        NOT NULL,
  role           cryoprotectant_roles,
  embedding      vector(3072),                 -- adjust dim if you use a smaller model
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (inchikey IS NULL OR inchikey ~* '^[A-Z]{14}-[A-Z]{10}-[A-Z]$')
);

/* auto‑update updated_at */
CREATE OR REPLACE FUNCTION _touch_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql AS
$$BEGIN NEW.updated_at = now(); RETURN NEW; END;$$;

DROP TRIGGER IF EXISTS trg_touch_cpa_chemicals ON cpa_chemicals;
CREATE TRIGGER trg_touch_cpa_chemicals
BEFORE UPDATE ON cpa_chemicals
FOR EACH ROW EXECUTE FUNCTION _touch_updated_at();

/* 3.b cpa_chemical_aliases */
CREATE TABLE IF NOT EXISTS cpa_chemical_aliases (
  chemical_id  UUID   NOT NULL REFERENCES cpa_chemicals(id) ON DELETE CASCADE,
  alias        CITEXT NOT NULL,
  embedding    vector(3072) NOT NULL,
  is_preferred BOOLEAN      DEFAULT FALSE,
  PRIMARY KEY (chemical_id, alias)
);

/* unique globally to prevent “glucose” pointing to 2 chemicals */
CREATE UNIQUE INDEX IF NOT EXISTS uq_alias_global
    ON cpa_chemical_aliases (alias);

/* ANN index for similarity search (vector cosine distance) */
CREATE INDEX IF NOT EXISTS idx_alias_embedding_ann
    ON cpa_chemical_aliases
 USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);

--------------------------------------------------------------------
-- 4. Agent‑property tables  (your insert_agent_properties helper)
--------------------------------------------------------------------
/* 4.a Property header */
CREATE TABLE IF NOT EXISTS chemical_properties (
  id           UUID          PRIMARY KEY DEFAULT uuid_generate_v4(),
  chemical_id  UUID          NOT NULL REFERENCES cpa_chemicals(id) ON DELETE CASCADE,
  prop_type    property_type NOT NULL,
  UNIQUE (chemical_id, prop_type)
);

/* 4.b Hybrid value storage */
CREATE TABLE IF NOT EXISTS chemical_property_values (
  id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  property_id   UUID NOT NULL REFERENCES chemical_properties(id) ON DELETE CASCADE,

  value_kind    fact_value_kind NOT NULL,

  numeric_value NUMERIC,      -- for POINT
  range_min     NUMERIC,      -- for RANGE
  range_max     NUMERIC,      -- for RANGE
  raw_value     TEXT,         -- for RAW
  extra         JSONB,        -- for STRUCT

  unit          TEXT,
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

/* optional performance indexes */
CREATE INDEX IF NOT EXISTS idx_propval_point
    ON chemical_property_values (property_id, numeric_value)
 WHERE value_kind = 'POINT';

CREATE INDEX IF NOT EXISTS idx_propval_range
    ON chemical_property_values
 USING gist (property_id, numrange(range_min, range_max))
 WHERE value_kind = 'RANGE';

CREATE INDEX IF NOT EXISTS idx_propval_struct
    ON chemical_property_values
 USING gin (extra)
 WHERE value_kind = 'STRUCT';

/* 4.c Provenance (paper ↔ value) */
CREATE TABLE IF NOT EXISTS cpa_references (
  id                 UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  property_value_id  UUID NOT NULL REFERENCES chemical_property_values(id) ON DELETE CASCADE,
  paper_id           TEXT NOT NULL,          -- DOI, arXiv, internal UUID …
  quote              TEXT,
  link               TEXT
);

CREATE INDEX IF NOT EXISTS idx_ref_propval
    ON cpa_references (property_value_id);

--------------------------------------------------------------------
-- 5. Staging tables  (raw JSON from COPY)
--------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS staging_cpa_chemicals (
  data_json  JSONB            NOT NULL,
  arrived_at TIMESTAMPTZ      DEFAULT now()
);

/* create more as you add pipeline steps */
-- CREATE TABLE IF NOT EXISTS staging_cpa_properties (data_json jsonb, arrived_at timestamptz default now());

--------------------------------------------------------------------
-- 6. Misc helpers (optional)
--------------------------------------------------------------------
/* Table to log unvalidated or duplicate InChIKeys if you wish */
CREATE TABLE IF NOT EXISTS cpa_unverified_inchikeys (
  supplied_key TEXT PRIMARY KEY,
  source_paper TEXT,
  note         TEXT,
  logged_at    TIMESTAMPTZ DEFAULT now()
);

COMMIT;

-- add a per‑paper deterministic ID to experiments
ALTER TABLE experiments
    ADD COLUMN IF NOT EXISTS local_id TEXT;

-- make (paper_id, local_id) unique so each ID is unambiguous inside one paper
ALTER TABLE experiments
    ADD CONSTRAINT IF NOT EXISTS uq_experiments_paper_local
    UNIQUE (paper_id, local_id);

/* ════════════════════════════════════════════════════════════════
   Post‑installation notes
   ----------------------------------------------------------------
   • The ANN index (ivfflat) needs `SET enable_seqscan = off;`
     or `SET ivfflat.probes` session parameter for best performance
     during similarity search.
   • If you use an embedding dimension other than 3 072, adjust the
     `vector(3072)` declarations in *both* tables and rebuild the
     ivfflat index.
   • Nothing else (functions, triggers) is required because all
     upsert / dedup logic lives in Python.
   ════════════════════════════════════════════════════════════════ */
