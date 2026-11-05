# Docker deployment

1. Copy .env.example to .env and set strong unique database password and SECRET_KEY values.
2. Put valid TLS certificate files at deploy/certs/fullchain.pem and deploy/certs/privkey.pem.
3. Run docker compose up -d --build.
4. Check docker compose logs -f api and https://YOUR_DOMAIN/api/health.
5. Bootstrap the first administrator using the existing bootstrap flow, then disable bootstrap access according to the bootstrap endpoint instructions.

The API container runs Alembic migrations before starting a single Uvicorn worker. PostgreSQL and policy evidence use named persistent volumes. Nginx is the only published service and redirects HTTP to HTTPS. Do not expose PostgreSQL or the API port publicly.

For migration to a new host, copy the repository/deployment configuration and TLS material securely, create a fresh database and empty evidence volume, restore a portable backup using scripts/restore.sh, then start the stack. Review docs/DEPLOYMENT_BACKUP_RESTORE.md first.

This is a deployment scaffold, not a production certification. Validate TLS issuance/renewal, firewall rules, backups, restore rehearsal, bootstrap security and domain configuration before public use. No separate Worker is configured because no independent scheduled worker task is currently implemented.
