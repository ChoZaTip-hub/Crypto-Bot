# ИИ-анализ сделок — как включить

## Где настраивать

1. **Файл `.env`** в корне проекта (`/Users/yarik/Downloads/Crypto Bot/.env`).
2. **Дашборд** — боковая панель справа, блок **«ИИ-анализ»** (`http://localhost:8000/`).
3. **API** — `GET /api/v1/ai/status`, `POST /api/v1/ai/analyze?symbol=BTCUSDT&timeframe=5`.

После правок `.env` перезапустите сервер (`uvicorn` / `python -m app.main`).

## Минимальная настройка

```env
AI_ENABLED=true
AI_API_KEY=sk-ваш-ключ
# или
OPENAI_API_KEY=sk-ваш-ключ

AI_MODEL=gpt-4o-mini
AI_BASE_URL=https://api.openai.com/v1
```

OpenRouter / LM Studio — тот же формат, другой `AI_BASE_URL` и модель.

## Режимы

| Переменная | Что делает |
|------------|------------|
| `AI_AUTO_ANALYZE=true` | При загрузке overview план сделки дополняется блоком `ai` (без отдельной кнопки). |
| `AI_INFLUENCE_TRADES=false` | ИИ только **советует** в панели; бот торгует по правилам MTF. |
| `AI_INFLUENCE_TRADES=true` | Если уверенность ИИ ≥ `AI_MIN_CONFIDENCE_INFLUENCE` (0.62), план и **цикл бота** могут сменить BUY/SELL и пересчитать SL/TP. |
| `AI_USE_CHART_IMAGE=true` | Дополнительно отправляется PNG свечей (нужен `matplotlib`). Модель — `AI_VISION_MODEL`. |

## Что видит ИИ

- Текущая цена Bybit.
- Индикаторы по таймфреймам (RSI, EMA, ATR, ADX и т.д.).
- Сетапы по каждому ТФ (как блок «Где видит сделку»).
- Решение правил бота (BUY/SELL/HOLD) для сравнения.

**TradingView** на экране — только для вас; бот и ИИ работают с данными Bybit из БД/API.

## Кнопка в интерфейсе

**«Запросить ИИ»** — принудительный запрос (`POST /api/v1/ai/analyze`), даже если авто-анализ выключен.

## Безопасность

- Ключ храните только в `.env`, не коммитьте в git.
- С `AI_INFLUENCE_TRADES=true` на live-режиме бот может открывать сделки по мнению модели — сначала проверьте на paper.
