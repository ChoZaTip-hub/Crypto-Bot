"""AI layer: interprets multi-timeframe market data (not TV screenshots)."""

from __future__ import annotations

import json
from typing import Any

from app.core.config import Settings
from app.core.logging import get_logger
from app.core.timeframes import label_for_timeframe
from app.services.ai.providers import OpenAICompatibleProvider, parse_json_response

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are a crypto spot trading analyst assistant.
You receive structured OHLCV indicators from Bybit (same data as the chart, not an image).
Respond ONLY with valid JSON in this schema:
{
  "action": "BUY" | "SELL" | "HOLD",
  "confidence": 0.0-1.0,
  "best_timeframe": "5" | "15" | "30" | "60" | "240" | "D",
  "best_timeframe_label": "human label",
  "summary_ru": "2-4 sentences in Russian for the trader",
  "patterns": ["list of pattern names you infer, e.g. engulfing, support bounce"],
  "entry_note_ru": "where to enter and why on that timeframe",
  "risk_note_ru": "stop loss / take profit logic in plain Russian"
}
Use live_price as entry reference. Prefer HOLD if timeframes conflict.
"""


class AiTradeAnalyst:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def available(self) -> bool:
        return bool(
            self._settings.ai_enabled
            and self._settings.ai_api_key
            and self._settings.ai_api_key.strip()
        )

    def _provider(self) -> OpenAICompatibleProvider:
        return OpenAICompatibleProvider(
            api_key=self._settings.ai_api_key,
            model=self._settings.ai_model,
            base_url=self._settings.ai_base_url,
            timeout=self._settings.ai_timeout_seconds,
        )

    def build_payload(
        self,
        *,
        symbol: str,
        live_price: float,
        chart_timeframe: str,
        regime: str | None,
        setups: list[dict[str, Any]],
        rule_action: str,
        rule_reason: str,
        indicators_by_tf: dict[str, dict],
    ) -> dict[str, Any]:
        tf_rows = []
        for tf, ind in sorted(indicators_by_tf.items(), key=lambda x: (len(x[0]), x[0])):
            tf_rows.append(
                {
                    "timeframe": tf,
                    "label": label_for_timeframe(tf),
                    "close": ind.get("close"),
                    "rsi": ind.get("rsi"),
                    "adx": ind.get("adx"),
                    "ema": ind.get("ema"),
                    "atr": ind.get("atr"),
                    "bb_upper": ind.get("bb_upper"),
                    "bb_lower": ind.get("bb_lower"),
                }
            )
        return {
            "symbol": symbol,
            "live_price": live_price,
            "chart_timeframe": chart_timeframe,
            "chart_timeframe_label": label_for_timeframe(chart_timeframe),
            "regime": regime,
            "rule_engine": {"action": rule_action, "reason": rule_reason},
            "per_timeframe_setups": setups,
            "indicators": tf_rows,
        }

    async def analyze(
        self,
        *,
        symbol: str,
        live_price: float,
        chart_timeframe: str,
        regime: str | None,
        setups: list[dict[str, Any]],
        rule_action: str,
        rule_reason: str,
        indicators_by_tf: dict[str, dict],
        chart_png: bytes | None = None,
    ) -> dict[str, Any]:
        if not self.available:
            return {
                "enabled": False,
                "error": "ИИ выключен или не задан AI_API_KEY в .env",
                "hint": "Добавьте OPENAI_API_KEY / AI_API_KEY и AI_ENABLED=true",
            }

        payload = self.build_payload(
            symbol=symbol,
            live_price=live_price,
            chart_timeframe=chart_timeframe,
            regime=regime,
            setups=setups,
            rule_action=rule_action,
            rule_reason=rule_reason,
            indicators_by_tf=indicators_by_tf,
        )
        user_msg = json.dumps(payload, ensure_ascii=False, indent=2)
        mode = "structured_data"

        try:
            provider = self._provider()
            if self._settings.ai_use_chart_image and chart_png:
                from app.services.ai.chart_image import png_to_data_url

                mode = "chart_image"
                vision_model = self._settings.ai_vision_model or self._settings.ai_model
                vision_provider = OpenAICompatibleProvider(
                    api_key=self._settings.ai_api_key,
                    model=vision_model,
                    base_url=self._settings.ai_base_url,
                    timeout=self._settings.ai_timeout_seconds,
                )
                raw = await vision_provider.complete_vision(
                    SYSTEM_PROMPT + "\nYou also receive a candlestick chart image.",
                    user_msg,
                    png_to_data_url(chart_png),
                )
            else:
                raw = await provider.complete(SYSTEM_PROMPT, user_msg)
            parsed = parse_json_response(raw)
            return {
                "enabled": True,
                "provider": self._settings.ai_provider,
                "model": self._settings.ai_model,
                "mode": mode,
                "symbol": symbol.upper(),
                "action": str(parsed.get("action", "HOLD")).upper(),
                "confidence": float(parsed.get("confidence") or 0),
                "best_timeframe": parsed.get("best_timeframe"),
                "best_timeframe_label": parsed.get("best_timeframe_label")
                or label_for_timeframe(str(parsed.get("best_timeframe", chart_timeframe))),
                "summary_ru": parsed.get("summary_ru", ""),
                "patterns": parsed.get("patterns") or [],
                "entry_note_ru": parsed.get("entry_note_ru", ""),
                "risk_note_ru": parsed.get("risk_note_ru", ""),
                "rule_action": rule_action,
                "disagrees_with_rules": str(parsed.get("action", "")).upper() != rule_action,
            }
        except Exception as exc:
            logger.warning("ai_analyze_failed", symbol=symbol, error=str(exc))
            return {
                "enabled": True,
                "error": str(exc),
                "symbol": symbol.upper(),
                "hint": "Проверьте AI_API_KEY, модель и доступ в интернет",
            }
