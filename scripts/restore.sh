#!/usr/bin/env bash
set -Eeuo pipefail
: "${1:?Usage: restore.sh /path/to/backup.tar.gz}"
: "${DATABASE_URL:?DATABASE_URL must point to a NEW, EMPTY PostgreSQL database}"
: "${POLICY_EVIDENCE_DIR:?POLICY_EVIDENCE_DIR is required}"
[[ "${RESTORE_CONFIRM:-}" == "RESTORE_TO_EMPTY_DATABASE" ]] || { echo "Refusing restore. Set RESTORE_CONFIRM=RESTORE_TO_EMPTY_DATABASE after verifying the target database is new and empty." >&2; exit 1; }
package="$1"
[[ -f "$package" ]] || { echo "Backup package not found: $package" >&2; exit 1; }
for cmd in pg_restore psql tar sha256sum find; do command -v "$cmd" >/dev/null || { echo "Missing command: $cmd" >&2; exit 1; }; done
[[ -f "$package.sha256" ]] || { echo "Package checksum file is missing: $package.sha256" >&2; exit 1; }
(cd "$(dirname "$package")" && sha256sum -c "$(basename "$package").sha256")
if tar -tzf "$package" | grep -Eq '(^/|(^|/)\.\.(/|$))'; then echo "Unsafe path detected in backup package." >&2; exit 1; fi
work="$(mktemp -d)"; staging="$(mktemp -d)"
trap 'rm -rf "$work" "$staging"' EXIT
tar -C "$work" -xzf "$package"
for f in database.dump policy-evidence.tar.gz manifest.txt SHA256SUMS; do [[ -f "$work/$f" ]] || { echo "Backup package missing: $f" >&2; exit 1; }; done
grep -qx 'format=phone-quote-backup-v1' "$work/manifest.txt" || { echo "Unsupported backup format." >&2; exit 1; }
(cd "$work" && sha256sum -c SHA256SUMS)
mkdir -p "$POLICY_EVIDENCE_DIR"
if find "$POLICY_EVIDENCE_DIR" -mindepth 1 -print -quit | grep -q .; then echo "Evidence target is not empty: $POLICY_EVIDENCE_DIR" >&2; exit 1; fi
tar -C "$staging" -xzf "$work/policy-evidence.tar.gz"
existing="$(psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -Atqc "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','S')")"
[[ "$existing" == "0" ]] || { echo "Target database is not empty (public objects: $existing)." >&2; exit 1; }
pg_restore --exit-on-error --no-owner --no-acl --dbname="$DATABASE_URL" "$work/database.dump"
cp -a "$staging/." "$POLICY_EVIDENCE_DIR/"
echo "Restore completed. Verify Alembic version, login, products, prices, policy evidence downloads and CSV exports before opening traffic."
