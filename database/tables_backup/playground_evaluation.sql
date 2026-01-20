/*══════════════════════════════════════════════════════════════════
  CryoDB – playground evaluation table
  Stores one LLM extraction package together with the model metadata.
══════════════════════════════════════════════════════════════════*/

CREATE TABLE IF NOT EXISTS playground_evaluation (
    id              bigserial PRIMARY KEY,
    
    /* --- provenance --------------------------------------------------- */
    ts_created      timestamptz NOT NULL DEFAULT now(),
    /* LLM that produced the extraction (e.g. gpt‑4o‑mini‑2024‑05‑13)    */
    extractor_model text        NOT NULL,
    /* Model used to judge / rank the extraction (optional)              */
    judge_model     text,
    
    /* --- user / run metadata (OPTIONAL) ------------------------------- */
    run_id          uuid,                 -- correlation id of a batch run
    user_email      text,                 -- who triggered the run
    
    /* --- extracted JSON payload -------------------------------------- */
    extracted_data  jsonb       NOT NULL, -- aliases, properties, expts, formulations
    
    /* --- convenience slices  ----------------------------------------- */
    -- Keep redundant scalar fields for fast filtering
    n_aliases       int     GENERATED ALWAYS AS (
                       jsonb_array_length(extracted_data -> 'agents_aliases')
                     ) STORED,
    n_properties    int     GENERATED ALWAYS AS (
                       jsonb_array_length(extracted_data -> 'agents_properties')
                     ) STORED,
    n_experiments   int     GENERATED ALWAYS AS (
                       jsonb_array_length(extracted_data -> 'experiments')
                     ) STORED,
    n_formulations  int     GENERATED ALWAYS AS (
                       jsonb_array_length(extracted_data -> 'formulations')
                     ) STORED
);

COMMENT ON TABLE  playground_evaluation IS
'LLM extraction playground – one row per paper × extractor run.';
COMMENT ON COLUMN playground_evaluation.extracted_data IS
'Composite JSON with keys: agents_aliases, agents_properties, experiments, formulations';

------------------------------------------------------------------
-- JSONB GIN index so we can search inside the payload quickly
------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_playground_eval_extracted_gin
    ON playground_evaluation
    USING gin (extracted_data jsonb_path_ops);
