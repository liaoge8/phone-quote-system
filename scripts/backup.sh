#!/usr/bin/env bash
set -Eeuo pipefail
: "${DATABASE_URL:?DATABASE_URL is required}"
: "${POLICY_EVIDENCE_DIR:?POLICY_EVIDENCE_DIR is required}"
: "${BACKUP_DIR:?BACKUP_DIR is required}"

command -v pg_dump >/dev/null
command -v tar >/dev/null
command -v sha256sum >/dev/null
[[ -d "$POLICY_EVIDENCE_DIR" ]] || { echo "Evidence directory does not exist: $POLICY_EVIDENCE_DIR" >&2; exit 1; }

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
dest="$BACKUP_DIR/$stamp"
mkdir -p "$dest"
chmod 700 "$dest"

# Run during a maintenance window with writes paused so the DB and evidence
# directory represent the same point in time.
pg_dump "$DATABASE_URL" --format=custom --no-owner --no-acl --file="$dest/database.dump"
tar -C "$(dirname "$POLICY_EVIDENCE_DIR")" -czf "$dest/policy-evidence.tar.gz" "$(basename "$POLICY_EVIDENCE_DIR")"
(
  cd "$dest"
  sha256sum database.dump policy-evidence.tar.gz > SHA256SUMS
)
printf '%s\n' "Backup created: $dest" "Keep this directory as one indivisible backup set."
