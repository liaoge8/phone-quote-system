# Portable backup package and new-server restore

This procedure targets PostgreSQL 16 and a Docker-based deployment. One portable archive contains the database dump, policy evidence files, a format manifest and SHA-256 checksums. A sidecar .sha256 file verifies the complete archive after transfer.

## Create a backup

During a maintenance window, pause all API/Worker writes and confirm no screenshot upload is in progress:

```bash
export DATABASE_URL='postgresql://...'
export POLICY_EVIDENCE_DIR='/persistent-volume/policy-evidence'
export BACKUP_DIR='/secure-backup-volume/phone-quote'
bash scripts/backup.sh
```

The script creates phone-quote-TIMESTAMP.tar.gz and its .sha256 sidecar. Copy both files together to independent storage. Restrict access: the package contains business data and policy screenshots. Do not put database URLs, JWT secrets or other credentials in the repository or package.

## Restore on a new server

1. Install Docker / Docker Compose and prepare PostgreSQL 16 plus persistent application storage.
2. Create a brand-new, empty PostgreSQL database. Never point the restore at a live production database.
3. Copy the archive and its .sha256 sidecar to the new server.
4. Check out an application version compatible with the backup and prepare its environment. POLICY_EVIDENCE_DIR must point to an empty persistent directory.
5. Install PostgreSQL client utilities (psql and pg_restore), tar and sha256sum.
6. Run:

```bash
export DATABASE_URL='postgresql://...'
export POLICY_EVIDENCE_DIR='/persistent-volume/policy-evidence'
export RESTORE_CONFIRM='RESTORE_TO_EMPTY_DATABASE'
bash scripts/restore.sh /backup/phone-quote-TIMESTAMP.tar.gz
```

The restore script checks the external checksum, internal checksums, format version, archive paths, empty evidence directory and empty target database before restoring. It does not use pg_restore --clean and will not drop existing tables.

7. Check the Alembic revision and start the application. Verify admin/member login, products, base-price history, policy prices, ST rebates, authenticated policy-evidence downloads (including SHA-256 verification) and CSV exports. Open business traffic only after these checks pass.

## Safety and limitations

- Restore is destructive in effect. Use a newly created empty database; never merge a backup into an existing database.
- The evidence directory must also be empty. Existing evidence files are never overwritten.
- Pause writes before backup so database and evidence files represent the same point in time.
- Encrypt backup storage and transport and restrict access. The scripts do not provide encryption or remote upload.
- PostgreSQL major-version compatibility is required; PostgreSQL 16 is the target.
- Scripts and documentation are committed, but an end-to-end restore rehearsal in an isolated PostgreSQL 16 + Docker environment is still required before calling production recovery verified.
- These scripts do not create Docker, configure TLS, or switch DNS. Container orchestration and a full migration rehearsal require separate validation.
