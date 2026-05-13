-- Migration 002: webapp manual-review fields.
-- Adds flag/flag_reason for "broken url / suspicious / spam / not-a-fit" reports
-- and match_score (0..100) cached from validate_fit() for sort-by-match.
-- All three are nullable; existing rows stay valid.

ALTER TABLE applications ADD COLUMN flag TEXT;
ALTER TABLE applications ADD COLUMN flag_reason TEXT;
ALTER TABLE applications ADD COLUMN flag_at TIMESTAMP;
ALTER TABLE applications ADD COLUMN match_score INTEGER;

CREATE INDEX IF NOT EXISTS applications_flag_idx ON applications(flag);
CREATE INDEX IF NOT EXISTS applications_match_idx ON applications(match_score);
