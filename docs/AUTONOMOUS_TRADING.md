# Автономная торговля и мультиаккаунт (без Telegram)

## Что добавлено

### 1. Сканер монет (`CoinScannerService`)

- Берёт USDT spot пары с Bybit (до `SCANNER_UNIVERSE_SIZE`).
- Каждый цикл проверяет порцию (`SCANNER_BATCH_SIZE`) — за ночь обходится весь список.
- Фильтр ликвидности: `SCANNER_MIN_TURNOVER_USDT` (оборот 24h).
- Скоринг: MTF edge, уверенность стратегии, сетапы по ТФ, волатильность (ATR).
- Лучшие попадают в `trading_universe` (до `SCANNER_TOP_N` + whitelist + открытые позиции).

### 2. Мультиаккаунт (copy trading)

- Таблицы `users`, `exchange_accounts`.
- У каждого счёта: свои API keys (шифрование `CREDENTIALS_ENCRYPTION_KEY`), `order_usdt`, paper/live.
- Один сигнал leader → `ExecutionRouter` исполняет на всех `copy_enabled` счетах.
- Счёт **default** создаётся из `.env` при старте.

### 3. API

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/v1/scanner/status` | Последний скан |
| POST | `/api/v1/scanner/run` | Принудительный скан |
| GET | `/api/v1/scanner/universe` | Список монет на цикл |
| GET | `/api/v1/accounts` | Список счетов |
| POST | `/api/v1/accounts` | Добавить счёт |
| PATCH | `/api/v1/accounts/{id}/toggle` | Вкл/выкл copy |

### 4. Позиции и SL/TP

- `positions.account_id`, `orders.account_id`.
- Монитор позиций закрывает SL/TP **по ключам того счёта**, где открыта позиция.

## Настройка `.env`

```env
SCANNER_ENABLED=true
BOT_AUTO_START=true
MARKET_POLL_INTERVAL_SECONDS=30
MULTI_ACCOUNT_COPY_ENABLED=true
CREDENTIALS_ENCRYPTION_KEY=<Fernet key>
```

Сгенерировать ключ:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Добавить второй счёт (пример)

```bash
curl -X POST http://localhost:8000/api/v1/accounts \
  -H "Content-Type: application/json" \
  -d '{
    "label": "client-2",
    "api_key": "BYBIT_KEY",
    "api_secret": "BYBIT_SECRET",
    "trading_mode": "paper",
    "order_usdt": 50,
    "copy_enabled": true
  }'
```

## Деплой на сервер 24/7

1. Postgres: `DATABASE_URL=postgresql+asyncpg://...`
2. `alembic upgrade head`
3. Docker: `docker compose -f docker/docker-compose.yml up -d`
4. `BOT_AUTO_START=true`, `BACKGROUND_SERVICES_ENABLED=true`

## Ограничения (следующие шаги)

- Telegram — не реализован.
- Redis-очередь для 1000 счётов — пока fan-out в том же процессе.
- Bybit WebSocket для свечей — код есть, в ingest не подключён.
- Синхронизация позиций с биржей — позиции в БД, не full sync с Bybit.

## Безопасность

- API keys только **Trade**, без **Withdraw**.
- На проде обязателен `CREDENTIALS_ENCRYPTION_KEY`.
- Сначала `TRADING_MODE=paper` на всех счетах.
