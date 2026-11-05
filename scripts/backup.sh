#!/usr/bin/env bash
set -Eeuo pipefail
: "${DATABASE_URL:?DATABASE_URL is required}"
: "${POLICY_EVIDENCE_DIR:?POLICY_EVIDENCE_DIR is required}"
: "${BACKUP_DIR:?BACKUP_DIR is required}"
for cmd in pg_dump tar sha256sum; do command -v "$cmd" >/dev/null || { echo "Missing command: $cmd" >&2; exit 1; }; done
[[ -d "$POLICY_EVIDENCE_DIR" ]] || { echo "Evidence directory does not exist: $POLICY_EVIDENCE_DIR" >&2; exit 1; }
mkdir -p "$BACKUP_DIR"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
work="$(mktemp -d "$BACKUP_DIR/.quote-backup.XXXXXX")"
trap 'rm -rf "$work"' EXIT
pg_dump "$DATABASE_URL" --format=custom --no-owner --no-acl --file="$work/database.dump"
tar -C "$POLICY_EVIDENCE_DIR" -czf "$work/policy-evidence.tar.gz" .
cat > "$work/manifest.txt" <<EOF
format=phone-quote-backup-v1
created_at_utc=$stamp
database_dump=database.dump
evidence_archive=policy-evidence.tar.gz
EOF
(cd "$work" && sha256sum database.dump policy-evidence.tar.gz manifest.txt > SHA256SUMS)
package="$BACKUP_DIR/phone-quote-$stamp.tar.gz"
tar -C "$work" -czf "$package" database.dump policy-evidence.tar.gz manifest.txt SHA256SUMS
chmod 600 "$package"
sha256sum "$package" > "$package.sha256"
chmod 600 "$package.sha256"
printf '%s\n' "Backup package: $package" "Package checksum: $package.sha256" "Copy both files to independent storage."
