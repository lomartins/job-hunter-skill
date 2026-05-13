-- Migration 003: structured tags on jobs.
-- TEXT column holding a JSON-encoded list of strings (or NULL).
-- We don't normalize to a join table because tags are noisy upstream
-- (every source uses different vocab) and we want filter-by-tag to stay a
-- single-table scan against a small dataset (<10k rows).

ALTER TABLE jobs ADD COLUMN tags TEXT;

-- No index: we filter by substring inside the JSON. With a 10k-row ceiling
-- on a local SQLite, a full scan is fine and avoids needing per-tag rows.
