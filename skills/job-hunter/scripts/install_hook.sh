#!/usr/bin/env bash
# Idempotent bootstrap for the `job-hunter` skill's XDG runtime layout.
# Safe to run repeatedly. Never deletes user data. Never reads secrets.
#
# Called by `job init`. Also runnable directly:
#   bash skills/job-hunter/scripts/install_hook.sh
#
# Honours JOB_HUNTER_HOME_OVERRIDE (used by tests) — same layout, different root.

set -euo pipefail

XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
XDG_DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
XDG_STATE_HOME="${XDG_STATE_HOME:-$HOME/.local/state}"

if [[ -n "${JOB_HUNTER_HOME_OVERRIDE:-}" ]]; then
    CONFIG_DIR="${JOB_HUNTER_HOME_OVERRIDE}/config/job-hunter"
    DATA_DIR="${JOB_HUNTER_HOME_OVERRIDE}/data/job-hunter"
    STATE_DIR="${JOB_HUNTER_HOME_OVERRIDE}/state/job-hunter"
else
    CONFIG_DIR="${XDG_CONFIG_HOME}/job-hunter"
    DATA_DIR="${XDG_DATA_HOME}/job-hunter"
    STATE_DIR="${XDG_STATE_HOME}/job-hunter"
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ASSETS_DIR="$(cd -- "${SCRIPT_DIR}/../assets" && pwd)"

mkdir -p \
    "${CONFIG_DIR}/secrets" \
    "${DATA_DIR}/tracking" \
    "${DATA_DIR}/adapters_inbox" \
    "${DATA_DIR}/adapters_user" \
    "${DATA_DIR}/files" \
    "${DATA_DIR}/runs" \
    "${STATE_DIR}/logs"

# Copy templates only if absent (never clobber user edits).
declare -A TEMPLATES=(
    ["${ASSETS_DIR}/personal.env.example"]="${CONFIG_DIR}/secrets/personal.env"
    ["${ASSETS_DIR}/profile.yaml.example"]="${CONFIG_DIR}/profile.yaml"
)

for src in "${!TEMPLATES[@]}"; do
    dst="${TEMPLATES[$src]}"
    if [[ -e "${dst}" ]]; then
        echo "  skip (exists): ${dst}"
        continue
    fi
    cp -- "${src}" "${dst}"
    echo "  copied: ${src} -> ${dst}"
done

# Lock down the secrets file. We never read its contents.
if [[ -f "${CONFIG_DIR}/secrets/personal.env" ]]; then
    chmod 600 "${CONFIG_DIR}/secrets/personal.env"
fi

cat <<EOF
job-hunter install hook complete.

Config dir : ${CONFIG_DIR}
Data dir   : ${DATA_DIR}
State dir  : ${STATE_DIR}

Next steps:
  1. \$EDITOR ${CONFIG_DIR}/profile.yaml         # roles, locations, public links (no PII)
  2. \$EDITOR ${CONFIG_DIR}/secrets/personal.env # PII; chmod 600 already applied
  3. playwright install chromium                 # if not already installed
  4. job doctor                                   # validate setup
EOF
