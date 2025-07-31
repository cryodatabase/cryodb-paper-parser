/*══════════════════════════════════════════════════════════════════
  CryoDB  –  presentation views  (rev. 2025‑07‑29)
  + NEW  v_cpa_alias_embeddings  (for pgvector semantic search)
══════════════════════════════════════════════════════════════════*/

------------------------------------------------------------------
-- (Re)create views – safest to DROP CASCADE first
------------------------------------------------------------------
DROP VIEW IF EXISTS v_cpa_alias_embeddings   CASCADE;
DROP VIEW IF EXISTS v_cpa_names_synonyms     CASCADE;
DROP VIEW IF EXISTS v_cpa_property_values    CASCADE;
DROP VIEW IF EXISTS v_cpa_properties         CASCADE;

------------------------------------------------------------------
-- 0.  Alias + embedding  (frontend semantic search entry‑point)
------------------------------------------------------------------
CREATE OR REPLACE VIEW v_cpa_alias_embeddings AS
SELECT
    chem.id          AS chemical_id,
    chem.inchikey,
    chem.role,
    chem.preferred_name,
    al.alias,                       -- the exact casing stored
    al.is_preferred,
    al.embedding                    -- pgvector(1536)
FROM   cpa_chemical_aliases AS al
JOIN   cpa_chemicals        AS chem
       ON chem.id = al.chemical_id;

-- Example search (parameterised):
--   SELECT * FROM v_cpa_alias_embeddings
--   ORDER BY embedding <-> $1::vector
--   LIMIT 20;

------------------------------------------------------------------
-- 1. Flat list of names and synonyms  (backwards‑compatible shape)
------------------------------------------------------------------
CREATE OR REPLACE VIEW v_cpa_names_synonyms AS
SELECT
    chem.id          AS chemical_id,
    chem.inchikey,
    chem.preferred_name,
    chem.role,
    al.alias         AS synonym,
    CASE
        WHEN al.is_preferred THEN 'preferred'
        ELSE 'synonym'
    END              AS label_type
FROM   cpa_chemical_aliases AS al
JOIN   cpa_chemicals        AS chem
       ON chem.id = al.chemical_id;

------------------------------------------------------------------
-- 2. Helper: one row per distinct (value, unit)
------------------------------------------------------------------
CREATE OR REPLACE VIEW v_cpa_property_values AS
SELECT
    cpv.id                  AS property_value_id,
    chem.id                 AS chemical_id,
    chem.preferred_name,
    chem.role,
    prop.prop_type,
    cpv.unit,

    /* ---------- Pretty‑printed value ---------------------------------- */
    CASE cpv.value_kind
      WHEN 'POINT'  THEN to_char(cpv.numeric_value, 'FM999999990.######')
      WHEN 'RANGE'  THEN concat_ws(' – ',
                          to_char(cpv.range_min, 'FM999999990.######'),
                          to_char(cpv.range_max, 'FM999999990.######')
                       )
      WHEN 'RAW'    THEN cpv.raw_value
      ELSE                cpv.extra::text
    END                             AS value_display,

    /* ---------- All sources for this (value,unit) --------------------- */
    jsonb_agg(
      jsonb_build_object(
        'paper_id', ref.paper_id,
        'quote',    ref.quote,
        'link',     ref.link
      )
      ORDER BY ref.paper_id
    ) AS sources

FROM       chemical_property_values   AS cpv
JOIN       chemical_properties        AS prop  ON prop.id  = cpv.property_id
JOIN       cpa_chemicals              AS chem  ON chem.id  = prop.chemical_id
LEFT JOIN  cpa_references             AS ref   ON ref.property_value_id = cpv.id
GROUP BY   cpv.id,
           chem.id, chem.preferred_name, chem.role,
           prop.prop_type, cpv.unit,
           cpv.value_kind, cpv.numeric_value,
           cpv.range_min, cpv.range_max,
           cpv.raw_value, cpv.extra;

------------------------------------------------------------------
-- 3. Aggregated view: one row per property type (à la ChemSpider)
------------------------------------------------------------------
CREATE OR REPLACE VIEW v_cpa_properties AS
SELECT
    chemical_id,
    preferred_name,
    role,
    prop_type,
    jsonb_agg(
      jsonb_build_object(
        'value',    value_display,
        'unit',     unit,
        'sources',  sources
      )
      ORDER BY value_display
    ) AS property_values
FROM v_cpa_property_values
GROUP BY chemical_id, preferred_name, role, prop_type;

------------------------------------------------------------------
-- Optional: grant read access to a front‑end role
------------------------------------------------------------------
-- GRANT SELECT ON v_cpa_alias_embeddings,
--                v_cpa_names_synonyms,
--                v_cpa_property_values,
--                v_cpa_properties
--    TO cryo_reader;
