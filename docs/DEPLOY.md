# Deploy on Render

## 1. Create services

Use **Blueprint** (`render.yaml`) or manually:

| Service | Type |
|---------|------|
| `crypto-bot` | Web Service (Python) |
| `crypto-bot-db` | PostgreSQL 16 |

Region: **Singapore** (same for both).

## 2. Build & start

```bash
pip install -e . && alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

## 3. Required environment variables

```env
APP_ENV=production
DEBUG=false
DATABASE_URL=postgresql+asyncpg://...   # replace postgresql:// with postgresql+asyncpg://
API_ADMIN_TOKEN=<long random secret>
CREDENTIALS_ENCRYPTION_KEY=<Fernet key>
TRADING_MODE=paper
BOT_AUTO_START=true
BACKGROUND_SERVICES_ENABLED=true
BYBIT_API_KEY=...
BYBIT_API_SECRET=...
```

Generate Fernet key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## 4. Dashboard admin token

After deploy, open the dashboard → **Дополнительно** → paste `API_ADMIN_TOKEN` → **Сохранить токен**.

Without it, Start/Stop/Run-once return 401 in production.

## 5. Plans

- **Free Web** sleeps → bot does not run 24/7.
- **Starter (Always On)** recommended for trading.
- **Free Postgres** expires after 90 days.

## 6. Health checks

- Liveness: `GET /api/v1/health`
- Ready: `GET /api/v1/health/ready` (checks DB)

## 7. Local vs production

| | Local | Production |
|---|-------|------------|
| DB | SQLite OK | Postgres only |
| Auth | Optional | `API_ADMIN_TOKEN` required |
| Encryption | Optional | `CREDENTIALS_ENCRYPTION_KEY` required |
