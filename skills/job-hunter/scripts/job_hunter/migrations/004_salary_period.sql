-- Migration 004: salary period.
-- Adds jobs.salary_period (hour | day | month | year | NULL).
-- NULL means "unknown" — the webapp falls back to a default assumption
-- (currently 'year', the most common period in tech postings).
-- Stored as plain TEXT to avoid a CHECK constraint that would block
-- future periods (e.g. 'week') without another migration.

ALTER TABLE jobs ADD COLUMN salary_period TEXT;
