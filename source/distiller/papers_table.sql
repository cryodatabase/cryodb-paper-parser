CREATE TYPE paper_status AS ENUM (
  'PENDING',
  'DOWNLOADED',
  'SKIPPED_DUPLICATE',
  'NO_FULLTEXT',
  'FAILED',
  'COMPLETED'
);

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE TABLE papers (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  paper_id         TEXT UNIQUE,
  doi              TEXT,
  source           TEXT NOT NULL,

  title            TEXT,
  journal          TEXT,
  published_year   INT,
  published_month  INT,
  published_day    INT,

  abstract         TEXT,
  authors_json     JSONB,
  authors_flat     TEXT,

  paper_url        TEXT,
  download_url     TEXT,
  is_free_fulltext BOOLEAN,
  license          TEXT,

  md5_hash         CHAR(64),
  file_size_bytes  INTEGER,
  file_s3_uri       TEXT,
  cpa_facts_json   JSONB,
  status           paper_status NOT NULL DEFAULT 'PENDING',
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Uniqueness only on md5_hash (ignores NULL)
CREATE UNIQUE INDEX ux_papers_md5_hash ON papers(md5_hash) WHERE md5_hash IS NOT NULL;