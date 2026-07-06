# Market Scanner Pro Runbook

## Database Backup

The default Docker Compose setup uses SQLite at `backend/instance/market_scanner.db`.

Stop writes before taking a filesystem copy:

```bash
docker compose stop backend worker scheduler
mkdir -p backups
cp backend/instance/market_scanner.db backups/market_scanner_$(date +%Y%m%d_%H%M%S).db
docker compose start backend worker scheduler
```

For a live SQLite backup, use the SQLite backup command:

```bash
sqlite3 backend/instance/market_scanner.db ".backup 'backups/market_scanner_$(date +%Y%m%d_%H%M%S).db'"
```

Keep backups encrypted at rest and store at least one copy outside the application host.

## Database Restore

Restore during a maintenance window:

```bash
docker compose stop backend worker scheduler
cp backups/market_scanner_YYYYMMDD_HHMMSS.db backend/instance/market_scanner.db
docker compose run --rm backend flask --app backend.app db upgrade
docker compose start backend worker scheduler
```

Verify the restored database:

```bash
curl http://localhost:5000/health
curl http://localhost:5000/ready
```

## Secret Rotation

Rotate secrets whenever a credential is exposed, a team member leaves, or on the regular security schedule.

1. Generate replacement values for `SECRET_KEY`, `POLYGON_API_KEY`, SMTP credentials, Redis credentials if used, and any deployment platform secrets.
2. Update the secret store or deployment environment. Do not commit `.env`.
3. Restart all services that read the rotated secret:

```bash
docker compose up -d --force-recreate backend worker scheduler
```

4. Re-authenticate users if `SECRET_KEY` or token-signing behavior changes.
5. Revoke the old upstream keys in the provider dashboard after the new deployment is healthy.
6. Confirm:

```bash
curl http://localhost:5000/health
docker compose logs --tail=100 backend
```

## YOLOv8 Model Download And Update

The model is intentionally excluded from Git. Download it from:

```text
https://huggingface.co/foduucom/stockmarket-pattern-detection-yolov8
```

Place the file at:

```text
models/yolov8/model.pt
```

To update the model:

```bash
mkdir -p models/yolov8
cp /path/to/new/model.pt models/yolov8/model.pt
docker compose up -d --force-recreate backend worker scheduler
```

Confirm readiness after the backend reloads the model:

```bash
curl http://localhost:5000/ready
```

Expected ready response when the database is reachable and `model.pt` is loaded:

```json
{"status":"ready","db":"ok","model":"ok"}
```

## Logs

Backend logs are emitted as JSON to stdout. In Docker Compose:

```bash
docker compose logs -f backend worker scheduler
```

Pattern detection audit artifacts are written under:

```text
logs/pattern_detections/<user_id>/
```

The XLSX log contains timestamp, symbol, timeframe, pattern, confidence, source badge, TA-Lib conflict flag, and annotated screenshot path.
