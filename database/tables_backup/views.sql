DROP VIEW IF EXISTS v_cpa_names_synonyms CASCADE;
DROP VIEW IF EXISTS v_cpa_property_values CASCADE;
DROP VIEW IF EXISTS v_cpa_properties CASCADE;
/* ════════════════════════════════════════════════════════════════
   ChemSpider‑style presentation views for CryoDB
   --------------------------------------------------------------
     • v_cpa_names_synonyms
     • v_cpa_property_values      (helper, may be queried directly)
     • v_cpa_properties
   rev. 2025‑07‑27
   ═══════════════════════════════════════════════════════════════ */

------------------------------------------------------------------
-- 1. Flat list of names and synonyms
------------------------------------------------------------------
CREATE OR REPLACE VIEW v_cpa_names_synonyms AS
SELECT
    chem.id                  AS chemical_id,
    chem.inchikey,
    chem.preferred_name,
    chem.role,                               -- NEW  ‹CPA | Adjuvant | Carrier›
    COALESCE(synonym.value, chem.preferred_name) AS synonym,  -- include canonical
    CASE
        WHEN synonym.value IS NULL THEN 'preferred'
        ELSE 'synonym'
    END                    AS label_type
FROM   cpa_chemicals AS chem
LEFT   JOIN LATERAL            -- explode JSONB array into rows
       jsonb_array_elements_text(chem.synonyms) AS synonym(value)
       ON TRUE;

------------------------------------------------------------------
-- 2. Helper: one row per distinct (value, unit)
------------------------------------------------------------------
CREATE OR REPLACE VIEW v_cpa_property_values AS
SELECT
    cpv.id                  AS property_value_id,
    chem.id                 AS chemical_id,
    chem.preferred_name,
    chem.role,                              -- NEW
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
      ELSE                cpv.extra::text          -- fallback display
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
    role,                                   -- NEW
    prop_type,
    jsonb_agg(
      jsonb_build_object(
        'value',    value_display,
        'unit',     unit,
        'sources',  sources
      )
      ORDER BY value_display         -- deterministic order
    ) AS property_values
FROM v_cpa_property_values
GROUP BY chemical_id, preferred_name, role, prop_type;

------------------------------------------------------------------
-- Optional: grant read access to a front‑end role
------------------------------------------------------------------
-- GRANT SELECT ON v_cpa_names_synonyms,
--                v_cpa_property_values,
--                v_cpa_properties
--    TO cryo_reader;
