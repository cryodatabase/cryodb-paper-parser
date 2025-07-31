/* ════════════════════════════════════════════════════════════════
   CryoDB – Experiment & Formulation stack (clean install)
   public.{experiments, formulations, formulation_components,
           formulation_properties, formulation_property_values,
           formulation_references}
   © CryoDB – rev. 2025‑07‑29
   ════════════════════════════════════════════════════════════════
   This script ONLY creates the objects that do **not** exist in the
   “CPA core” schema you already defined (papers, cpa_chemicals, …).
   Run inside an empty or partially‑populated cluster; everything is
   idempotent and safe to re‑execute.
   ────────────────────────────────────────────────────────────────*/

/* ── 0. Extensions (create once per database) ─────────────────── */
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";       -- uuid_generate_v4()
CREATE EXTENSION IF NOT EXISTS citext;            -- case‑insensitive text
CREATE EXTENSION IF NOT EXISTS btree_gist;        -- GiST on NUMRANGE

/* ── 1. Utility trigger to auto‑touch updated_at ──────────────── */
DO $$
BEGIN
  IF NOT EXISTS (
       SELECT 1 FROM pg_proc WHERE proname = '_touch_updated_at'
     ) THEN
CREATE OR REPLACE FUNCTION _touch_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $func$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END;
$func$;
  END IF;
END$$;

/* ── 2. ENUM types ────────────────────────────────────────────── */
-- 2.a  Already‑existing enums (cryoprotectant_roles, fact_value_kind)
--      are assumed present; create only if missing for clean install.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'cryoprotectant_roles') THEN
    CREATE TYPE cryoprotectant_roles AS ENUM ('CPA', 'Adjuvant', 'Carrier');
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'fact_value_kind') THEN
    CREATE TYPE fact_value_kind AS ENUM ('POINT', 'RANGE', 'RAW', 'STRUCT');
  END IF;
END$$;

-- 2.b  Dependent property types (context‑aware measurements)
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'dependent_property_type') THEN
    CREATE TYPE dependent_property_type AS ENUM (
      'MEMBRANE_PERMEABILITY',
      'TOXICITY',
      'LOADING_TEMPERATURE',
      'UNLOADING_TEMPERATURE',
      'CRITICAL_COOLING_RATE',
      'CRITICAL_WARMING_RATE'
    );
  END IF;
END$$;

/* ── 3. Table: experiments ───────────────────────────────────── */
CREATE TABLE IF NOT EXISTS experiments (
  id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  paper_id                UUID NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
  local_id                TEXT,
  performed_in_this_paper BOOLEAN      NOT NULL DEFAULT TRUE,
  label                   TEXT,
  method                  TEXT,
  biological_context      JSONB,
  quote                   TEXT          NOT NULL,
  created_at              TIMESTAMPTZ   NOT NULL DEFAULT now(),
  updated_at              TIMESTAMPTZ   NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_experiments_paper
    ON experiments (paper_id);
CREATE CONSTRAINT IF NOT EXISTS uq_experiments_paper_local
    UNIQUE (paper_id, local_id);

DROP TRIGGER IF EXISTS trg_touch_experiments ON experiments;
CREATE TRIGGER trg_touch_experiments
BEFORE UPDATE ON experiments
FOR EACH ROW EXECUTE FUNCTION _touch_updated_at();

/* ── 4. Table: formulations ──────────────────────────────────── */
CREATE TABLE IF NOT EXISTS formulations (
  id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  experiment_id  UUID    NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
  label          CITEXT  NOT NULL,
  quote          TEXT    NOT NULL,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (experiment_id, label)          -- avoid duplicate labels
);
CREATE INDEX IF NOT EXISTS idx_formulations_experiment
    ON formulations (experiment_id);

DROP TRIGGER IF EXISTS trg_touch_formulations ON formulations;
CREATE TRIGGER trg_touch_formulations
BEFORE UPDATE ON formulations
FOR EACH ROW EXECUTE FUNCTION _touch_updated_at();

/* ── 5. Table: formulation_components ────────────────────────── */
CREATE TABLE IF NOT EXISTS formulation_components (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  formulation_id  UUID    NOT NULL REFERENCES formulations(id) ON DELETE CASCADE,
  role            cryoprotectant_roles NOT NULL,
  chemical_id     UUID REFERENCES cpa_chemicals(id) ON DELETE RESTRICT,
  alias_id        UUID NOT NULL REFERENCES cpa_chemical_aliases(id) ON DELETE RESTRICT,
  amount          NUMERIC,
  unit            TEXT,
  quote           TEXT   NOT NULL,
  note            TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (
        (role IN ('CPA','Adjuvant') AND chemical_id IS NOT NULL) OR
        (role = 'Carrier'          AND chemical_id IS NULL)
  )
);
CREATE INDEX IF NOT EXISTS idx_formcomp_formulation
    ON formulation_components (formulation_id);
CREATE INDEX IF NOT EXISTS idx_formcomp_role
    ON formulation_components (role);
CREATE INDEX IF NOT EXISTS idx_formcomp_chemical
    ON formulation_components (chemical_id) WHERE chemical_id IS NOT NULL;

DROP TRIGGER IF EXISTS trg_touch_formcomp ON formulation_components;
CREATE TRIGGER trg_touch_formcomp
BEFORE UPDATE ON formulation_components
FOR EACH ROW EXECUTE FUNCTION _touch_updated_at();

/* ── 6. Table: formulation_properties (header rows) ──────────── */
CREATE TABLE IF NOT EXISTS formulation_properties (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  experiment_id   UUID NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,

  formulation_id  UUID REFERENCES formulations(id) ON DELETE CASCADE,
  component_id    UUID REFERENCES formulation_components(id) ON DELETE CASCADE,

  prop_type       dependent_property_type NOT NULL,

  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

  CHECK ( (formulation_id IS NOT NULL AND component_id IS NULL) OR
          (formulation_id IS NULL     AND component_id IS NOT NULL) ),

  UNIQUE (experiment_id, prop_type, formulation_id, component_id)
);
CREATE INDEX IF NOT EXISTS idx_formprop_experiment
    ON formulation_properties (experiment_id);
CREATE INDEX IF NOT EXISTS idx_formprop_target
    ON formulation_properties (formulation_id, component_id);

DROP TRIGGER IF EXISTS trg_touch_formprops ON formulation_properties;
CREATE TRIGGER trg_touch_formprops
BEFORE UPDATE ON formulation_properties
FOR EACH ROW EXECUTE FUNCTION _touch_updated_at();

/* ── 7. Table: formulation_property_values ───────────────────── */
CREATE TABLE IF NOT EXISTS formulation_property_values (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  property_id     UUID NOT NULL REFERENCES formulation_properties(id) ON DELETE CASCADE,

  value_kind      fact_value_kind NOT NULL,

  numeric_value   NUMERIC,
  range_min       NUMERIC,
  range_max       NUMERIC,
  raw_value       TEXT,
  extra           JSONB,

  unit            TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

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

-- Helpful indexes
CREATE INDEX IF NOT EXISTS idx_fpropval_point
  ON formulation_property_values (property_id, numeric_value)
  WHERE value_kind = 'POINT';

CREATE INDEX IF NOT EXISTS idx_fpropval_range
  ON formulation_property_values
  USING gist (property_id, numrange(range_min, range_max))
  WHERE value_kind = 'RANGE';

CREATE INDEX IF NOT EXISTS idx_fpropval_struct
  ON formulation_property_values USING gin (extra)
  WHERE value_kind = 'STRUCT';

/* ── 8. Table: formulation_references (provenance) ───────────── */
CREATE TABLE IF NOT EXISTS formulation_references (
  id                 UUID PRIMARY KEY DEFAULT uuid_generate_v4\(),
  property_value_id  UUID NOT NULL
                     REFERENCES formulation_property_values(id) ON DELETE CASCADE,
  paper_id           TEXT NOT NULL,
  quote              TEXT,
  link               TEXT
);
CREATE INDEX IF NOT EXISTS idx_fref_propval
    ON formulation_references (property_value_id);

/* ═══════════════════════  END  ════════════════════════════════ */
