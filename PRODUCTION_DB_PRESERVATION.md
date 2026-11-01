# Production SQLite preservation gate (NO DEPLOY)

**Current live deploy:** `1dc81d4b4d2f741fe50844780d88d60cfcc4ec92`.
**GitHub main is newer than the live deployment.** The `/api/backup` endpoint exists in main but is NOT present on the live deployment.
**Storage:** Render Free ephemeral filesystem. Deploy, restart, spin-down/replacement or redeployment can lose local SQLite data. Do not rely on local DB durability.

## Mandatory prerequisites before merge or deploy
1. Obtain the **full live** `data/signals.db` SQLite file (not a 100/200-row API JSON export).
2. Validate the downloaded file on a separate computer using `PRAGMA integrity_check`; inventory all tables and row counts.
3. Preserve at least two independent copies of the backup off Render. Avoid publishing DB, API tokens or private trading records in GitHub.
4. Perform an isolated restore drill; confirm BUY events, snapshots, tracking and paper trade records.
5. Configure durable storage or external database before any production migration, and verify persistence through a restart on a **test** service.
6. Only then review and merge the code; explicitly verify new deploy commit and runtime API endpoints.

## Access limitations
- Render connector offers service/deploy/log/metrics/env management, but no remote shell or file download action.
- Render dashboard `Connect` in the supplied screenshot shows outbound IPs, not a shell.
- Existing partial JSON exports are valuable forensic evidence, but not a restorable full SQLite database.
- DO NOT deploy a backup endpoint just to recover the current ephemeral DB: the deployment itself may discard the data being rescued.
- Do not put an ACCESS_TOKEN in screenshots, URLs shared publicly, GitHub issues, or logs.

## Next safe step
Find a **non-restarting** path to read the currently running instance's file, e.g. an already-enabled remote shell or provider-supported live filesystem export. If unavailable, obtain provider support advice or accept that the historical live SQLite DB cannot be guaranteed preserved. Continue read-only API exports only as a partial fallback, clearly labeled incomplete.

## Automated validation
`python -m unittest -v test_paper_exit_audit_readonly test_backup_offline_verify test_backup_producer_integration test_backup_concurrent_writes test_backup_restore_drill`

Tests exercise synthetic local databases; passing them does not mean the live database was backed up, restored or that trade performance was validated.
