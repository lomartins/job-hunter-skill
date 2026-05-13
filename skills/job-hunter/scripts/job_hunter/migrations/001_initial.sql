-- Migration 001: initial schema.
-- The SQLModel definitions in job_hunter.models mirror this verbatim.
-- A test in tests/test_db_migrations.py asserts agreement.

CREATE TABLE IF NOT EXISTS jobs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source          TEXT NOT NULL,
    external_id     TEXT NOT NULL,
    url             TEXT NOT NULL UNIQUE,
    title           TEXT NOT NULL,
    company         TEXT NOT NULL,
    location        TEXT,
    remote          BOOLEAN,
    salary_min      INTEGER,
    salary_max      INTEGER,
    currency        TEXT,
    posted_at       TIMESTAMP,
    description     TEXT,
    raw_payload     TEXT,           -- JSON
    scraped_at      TIMESTAMP NOT NULL,
    fingerprint     TEXT NOT NULL,
    UNIQUE(source, external_id)
);
CREATE INDEX IF NOT EXISTS jobs_source_idx ON jobs(source);
CREATE INDEX IF NOT EXISTS jobs_company_idx ON jobs(company);
CREATE INDEX IF NOT EXISTS jobs_fingerprint_idx ON jobs(fingerprint);

CREATE TABLE IF NOT EXISTS applications (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id          INTEGER NOT NULL REFERENCES jobs(id),
    current_stage   TEXT NOT NULL DEFAULT 'discovered',
    applied_at      TIMESTAMP,
    next_action     TEXT,
    next_action_due TIMESTAMP,
    notes           TEXT,
    adapter_used    TEXT,
    updated_at      TIMESTAMP NOT NULL
);
CREATE INDEX IF NOT EXISTS applications_job_id_idx ON applications(job_id);
CREATE INDEX IF NOT EXISTS applications_stage_idx ON applications(current_stage);

CREATE TABLE IF NOT EXISTS stage_history (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id   INTEGER NOT NULL REFERENCES applications(id),
    from_stage       TEXT,
    to_stage         TEXT NOT NULL,
    transitioned_at  TIMESTAMP NOT NULL,
    note             TEXT
);
CREATE INDEX IF NOT EXISTS stage_history_app_idx ON stage_history(application_id);

CREATE TABLE IF NOT EXISTS site_adapters (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    platform_signature    TEXT NOT NULL UNIQUE,
    adapter_path          TEXT NOT NULL,
    version               INTEGER NOT NULL DEFAULT 1,
    success_count         INTEGER NOT NULL DEFAULT 0,
    failure_count         INTEGER NOT NULL DEFAULT 0,
    consecutive_failures  INTEGER NOT NULL DEFAULT 0,
    last_used_at          TIMESTAMP,
    auto_eligible         BOOLEAN NOT NULL DEFAULT 0,
    paused_for_review     BOOLEAN NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS fill_attempts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id  INTEGER NOT NULL REFERENCES applications(id),
    adapter_id      INTEGER REFERENCES site_adapters(id),
    started_at      TIMESTAMP NOT NULL,
    finished_at     TIMESTAMP,
    outcome         TEXT,
    artifacts_path  TEXT,
    fields_filled   INTEGER,
    fields_total    INTEGER,
    mode            TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS fill_attempts_app_idx ON fill_attempts(application_id);

CREATE TABLE IF NOT EXISTS cover_letter_approvals (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id                INTEGER NOT NULL UNIQUE REFERENCES jobs(id),
    generated_text_hash   TEXT NOT NULL,
    approved_at           TIMESTAMP NOT NULL
);
