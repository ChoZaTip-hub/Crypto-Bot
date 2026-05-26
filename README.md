# Crypto Trading Bot MVP

Production-oriented MVP for an AI-assisted crypto trading bot.

**Important:** This software does not guarantee profits. Trading involves substantial risk. Default mode is **paper trading**. Live trading requires explicit environment flags.

## Stack

- Python 3.12, FastAPI, asyncio, SQLAlchemy 2.0 async, Alembic, Pydantic v2
- PostgreSQL, Redis
- Bybit V5 (spot) via `pybit` — testnet/live switch
- Multi-source news: RSS (CoinDesk, Cointelegraph, CryptoSlate, Decrypt, …), Bybit Announcements, optional Crypto News API

## Architecture

```
Market Data → Indicators → Strategy → Risk → Execution → Audit
     ↑           ↑            ↑         ↑        ↑
  Bybit/Mock   Postgres    Multi-TF   Rules   Paper/Live
```

## Quick Start

### 1. Environment

```bash
cp .env.example .env
```

### 2. Infrastructure

```bash
docker compose -f docker/docker-compose.yml up -d postgres redis
```

### 3. Install & migrate

```bash
pip install -e ".[dev]"
alembic upgrade head
```

### 4. Run API

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Web dashboard (панель управления)

Открой в браузере: **http://localhost:8000/**

- Старт / стоп бота, один цикл
- График свечей Bybit + линии индикаторов и entry/SL/TP
- Новости, сигналы, риск, audit

### 6. Health check

```bash
curl http://localhost:8000/api/v1/health
```

## Trading Modes

| Mode | Env |
|------|-----|
| Paper (default) | `TRADING_MODE=paper` |
| Live | `TRADING_MODE=live` **and** `LIVE_TRADING_ENABLED=true` |

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/v1/health` | Health + DB status |
| `GET /api/v1/bot/status` | Bot state |
| `POST /api/v1/bot/start` | Start bot loop |
| `POST /api/v1/bot/stop` | Stop bot |
| `GET /api/v1/market/candles` | Historical candles |
| `GET /api/v1/signals` | Strategy signals |
| `GET /api/v1/orders` | Orders & fills |
| `GET /api/v1/positions` | Open positions |
| `GET /api/v1/risk/status` | Risk state |
| `GET /api/v1/news` | News feed |
| `GET /api/v1/news/sources` | Configured news providers |
| `POST /api/v1/news/ingest` | Pull RSS + Bybit + Crypto News API |
| `POST /api/v1/backtests/run` | Run backtest |
| `GET /api/v1/admin/audit` | Audit log |
| `WS /ws` | Realtime events |

Admin endpoints require `X-Admin-Token` when `API_ADMIN_TOKEN` is set.

## Default Universe

- Symbols: `BTCUSDT`, `ETHUSDT`, `SOLUSDT`, `BNBUSDT`, `XRPUSDT`
- Timeframes: `1`, `5`, `60` (minutes)

## Tests

```bash
pytest -v
```

## Project Structure

See `app/` for modular packages: `exchanges/`, `indicators/`, `strategies/`, `risk/`, `services/`, `backtesting/`, `workers/`, `realtime/`.

## News sources

| Provider | Config | Notes |
|----------|--------|-------|
| RSS | `NEWS_RSS_URLS` (defaults in `app/core/news_sources.py`) | CoinDesk, Cointelegraph, CryptoSlate, Decrypt, The Defiant, macro (Yahoo, CNBC), … |
| Bybit Announcements | `BYBIT_ANNOUNCEMENTS_ENABLED=true` | Official `pybit` `HTTP.get_announcement()` — [V5 API](https://bybit-exchange.github.io/docs/v5/announcement) |
| Crypto News API | `CRYPTO_NEWS_API_KEY` | Optional aggregator at [cryptonews-api.com](https://cryptonews-api.com) |

High-impact Bybit events (listings, delistings, maintenance) feed into sentiment risk blocks.

## Disclaimer

For educational and development purposes. Not financial advice. Always test on paper/testnet before any live capital.
