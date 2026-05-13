#!/usr/bin/env bash
# Idempotent bootstrap for the `job-hunter` skill's XDG runtime layout.
#
# Phase 1: prints what would be done and exits 0. The real implementation
# (Phase 2) will:
#   - mkdir -p the three XDG roots
#   - copy assets/personal.env.example -> $XDG_CONFIG_HOME/job-hunter/secrets/personal.env
#     ONLY if missing (never clobber)
#   - copy profile.yaml.example -> profile.yaml ONLY if missing
#   - chmod 600 secrets/personal.env
#   - print next-steps for the user (edit the files, install Playwright)
#
# Safe to run repeatedly. Never deletes user data. Never reads secrets.

set -euo pipefail

XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
XDG_DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
XDG_STATE_HOME="${XDG_STATE_HOME:-$HOME/.local/state}"

CONFIG_DIR="${XDG_CONFIG_HOME}/job-hunter"
DATA_DIR="${XDG_DATA_HOME}/job-hunter"
STATE_DIR="${XDG_STATE_HOME}/job-hunter"

cat <<EOF
job-hunter install hook (phase 1 stub).

Would create:
  - ${CONFIG_DIR}/{secrets,}
  - ${DATA_DIR}/{tracking,adapters_inbox,adapters_user,files,runs}
  - ${STATE_DIR}/logs

Would copy templates (if absent):
  - assets/personal.env.example -> ${CONFIG_DIR}/secrets/personal.env  (then chmod 600)
  - assets/profile.yaml.example -> ${CONFIG_DIR}/profile.yaml

Real implementation lands in phase 2. Run `job init` once the CLI ships.
EOF
