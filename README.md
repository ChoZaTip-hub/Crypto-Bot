# Crypto Trading Bot MVP

Production-oriented MVP for an AI-assisted crypto trading bot.

**Important:** This software does not guarantee profits. Trading involves substantial risk. Default mode is **paper trading**. Live trading requires explicit environment flags.

## Stack

- Python 3.12, FastAPI, asyncio, SQLAlchemy 2.0 async, Alembic, Pydantic v2
- PostgreSQL, Redis
- Bybit V5 (spot) via `pybit` — testnet/live switch
- Chart-based strategy: multi-timeframe indicators, memory snapshots, adaptive learning from trade outcomes

## Architecture

```
Market Data → Indicators → Strategy → Risk → Execution → Audit
     ↑           ↑            ↑         ↑        ↑
  Bybit/Mock   Postgres    Multi-TF   Rules   Paper/Live
                    ↑
              Memory & Learning (SL/TP outcomes)
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
- График свечей Bybit + TradingView + уровни Entry/SL/TP
- Сигналы, индикаторы, обучение, риск, audit

### 6. Health check

```bash
curl http://localhost:8000/api/v1/health
```

## Trading Modes

| Mode | Env |
|------|-----|
| Paper (default) | `TRADING_MODE=paper` |
| Live | `TRADING_MODE=live` **and** `LIVE_TRADING_ENABLED=true` |

### Live trading (real orders on Bybit)

1. Create API keys on [Bybit](https://www.bybit.com) (or [testnet](https://testnet.bybit.com)) with **Spot Trade** only (no withdraw).
2. In `.env`:

```env
TRADING_MODE=live
LIVE_TRADING_ENABLED=true
BYBIT_TESTNET=true          # false for mainnet
BYBIT_API_KEY=...
BYBIT_API_SECRET=...
BOT_AUTO_START=true         # or POST /api/v1/bot/start
```

3. **SL/TP on exchange** (at entry): `LIVE_PLACE_EXCHANGE_SL_TP=true` sends `stopLoss` / `takeProfit` with the buy order.
4. **24/7 monitor** (`POSITION_MONITOR_INTERVAL_SECONDS=10`): if price hits SL/TP, bot places a **market close** on Bybit (`LIVE_CLOSE_SL_TP_ON_EXCHANGE=true`). Works even when the trading loop is stopped.
5. Verify: `curl http://localhost:8000/api/v1/health` → `"live_enabled": true`.

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
| `GET /api/v1/memory/*` | Market memory snapshots |
| `GET /api/v1/learning/*` | Adaptive learning stats |
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

## Disclaimer

For educational and development purposes. Not financial advice. Always test on paper/testnet before any live capital.
