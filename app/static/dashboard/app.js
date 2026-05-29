const API = "";
const ADMIN_TOKEN_KEY = "crypto_bot_admin_token";

function getAdminToken() {
  return localStorage.getItem(ADMIN_TOKEN_KEY) || "";
}

function setAdminToken(value) {
  const v = String(value || "").trim();
  if (v) localStorage.setItem(ADMIN_TOKEN_KEY, v);
  else localStorage.removeItem(ADMIN_TOKEN_KEY);
}

const TF_LABELS = {
  "1": "1m", "3": "3m", "5": "5m", "15": "15m", "30": "30m",
  "60": "1h", "240": "4h", "D": "1D", "W": "1W", "M": "1MN",
};

let refreshTimer = null;
let ratioTimer = null;
let livePriceTimer = null;
let tfChangeTimer = null;
let refreshAbort = null;
let lastOverview = null;
let tvChartKey = "";
let lastLivePrice = null;
let lastPriceSource = "";
let lastLivePlan = null;
let allSymbols = [];
let userPinnedSymbol = false;
let programmaticSymbolChange = false;
let lastOpportunityMeta = null;
let symbolPickMap = {};

function formatPrice(v) {
  if (v == null || Number.isNaN(Number(v))) return "—";
  return Number(v).toLocaleString("en-US", { maximumFractionDigits: 2 });
}

function currentDisplayPrice(chartData, overview) {
  return lastLivePrice ?? chartData?.last_price ?? overview?.last_price ?? null;
}

function priceSourceLabel(src) {
  if (src === "bybit_live") return "Текущая цена (Bybit, как на TV)";
  if (src === "candle_close") return "Цена (закрытие свечи в БД)";
  return "Текущая цена";
}

function updatePriceContextBanner(overview, priceInfo) {
  const el = $("priceContextBanner");
  if (!el) return;
  const note = overview?.price_note || priceInfo?.note_ru;
  if (!note) {
    el.hidden = true;
    return;
  }
  el.hidden = false;
  el.className = "price-context-banner";
  el.textContent = note;
}

function selectedSymbol() {
  return ($("symbolSelect")?.value || "BTCUSDT").toUpperCase();
}

function selectedChartTimeframe() {
  return $("timeframeSelect")?.value || "5";
}

function tfLabel(tf) {
  return TF_LABELS[tf] || tf;
}

/** Levels/labels for the chart TF (not MTF primary setup on another TF). */
function resolvePlanForChart(plan) {
  if (!plan || !planMatchesSymbol(plan)) return null;
  const chartTf = selectedChartTimeframe();
  const chartLbl = plan.chart_timeframe_label || tfLabel(chartTf);
  const setup = (plan.setups || []).find((s) => s.timeframe === chartTf);
  const base = { ...plan, chart_timeframe: chartTf, chart_timeframe_label: chartLbl };
  if (setup) {
    return {
      ...base,
      horizon_tf: chartTf,
      horizon_label: setup.label || chartLbl,
      entry: setup.entry,
      stop_loss: setup.stop_loss,
      take_profit: setup.take_profit,
      suggested_chart_action: setup.action,
    };
  }
  if (plan.chart_timeframe === chartTf || plan.horizon_tf === chartTf) {
    return base;
  }
  return base;
}

function applyLevelLabels(plan) {
  const lbl = plan?.horizon_label || plan?.chart_timeframe_label || tfLabel(selectedChartTimeframe());
  const setLbl = (id, prefix) => {
    const el = $(id);
    if (el) el.textContent = `${prefix} (${lbl})`;
  };
  if (plan?.source === "open_position") {
    const e = $("lblEntry");
    if (e) e.textContent = "Вход (позиция открыта)";
    setLbl("lblStop", "Stop Loss");
    setLbl("lblTp", "Take Profit");
    return;
  }
  setLbl("lblEntry", "Вход");
  setLbl("lblStop", "Stop Loss");
  setLbl("lblTp", "Take Profit");
}

function planMatchesSymbol(plan) {
  if (!plan) return false;
  const sym = selectedSymbol();
  return !plan.symbol || String(plan.symbol).toUpperCase() === sym;
}

function applyLivePlanToLevelCards(plan) {
  const resolved = resolvePlanForChart(plan);
  if (!resolved) return;
  const set = (id, v) => {
    const el = $(id);
    if (el) el.textContent = formatPrice(v);
  };
  const showLevels =
    resolved.action === "BUY" ||
    resolved.action === "SELL" ||
    resolved.suggested_chart_action ||
    resolved.chart_setup;
  if (showLevels) {
    set("lvlEntry", resolved.entry);
    set("lvlStop", resolved.stop_loss);
    set("lvlTp", resolved.take_profit);
  }
  applyLevelLabels(resolved);
}

function renderAiAnalysis(ai) {
  const el = $("aiAnalysisPanel");
  const btn = $("btnAiAnalyze");
  if (!el) return;
  if (!ai) {
    el.textContent = "Нажмите «Запросить ИИ» (нужен AI_API_KEY в .env)";
    return;
  }
  if (ai.enabled === false || ai.error) {
    el.className = "ai-analysis-panel hint";
    el.textContent = ai.error || ai.hint || "ИИ не настроен";
    if (btn) btn.disabled = false;
    return;
  }
  const act = (ai.action || "HOLD").toLowerCase();
  el.className = "ai-analysis-panel " + (act === "buy" || act === "sell" ? act : "");
  const disagree = ai.disagrees_with_rules
    ? "<p class='hint'>⚠ ИИ не согласен с правилами бота</p>"
    : "";
  el.innerHTML = `
    <p class="ai-action">${escapeHtml(ai.action)} · ${(ai.confidence * 100).toFixed(0)}% · ТФ: ${escapeHtml(ai.best_timeframe_label || ai.best_timeframe || "—")}</p>
    <p>${escapeHtml(ai.summary_ru || "")}</p>
    ${ai.entry_note_ru ? `<p class="hint"><strong>Вход:</strong> ${escapeHtml(ai.entry_note_ru)}</p>` : ""}
    ${ai.risk_note_ru ? `<p class="hint"><strong>Риск:</strong> ${escapeHtml(ai.risk_note_ru)}</p>` : ""}
    ${(ai.patterns || []).length ? `<p class="hint">Паттерны: ${escapeHtml(ai.patterns.join(", "))}</p>` : ""}
    ${disagree}`;
}

let aiStatusCache = null;

async function loadAiStatus() {
  try {
    const st = await api("/api/v1/ai/status");
    aiStatusCache = st;
    const btn = $("btnAiAnalyze");
    const panel = $("aiAnalysisPanel");
    if (btn) btn.disabled = !st.configured;
    if (!st.configured && panel) {
      renderAiAnalysis({
        error: "ИИ не настроен",
        hint: "В .env: AI_ENABLED=true и AI_API_KEY=sk-… (или OPENAI_API_KEY)",
      });
      return;
    }
    if (panel && st.auto_analyze && !panel.textContent?.includes("%")) {
      panel.className = "ai-analysis-panel hint";
      panel.textContent =
        "Авто-анализ при обновлении страницы (AI_AUTO_ANALYZE). Кнопка — принудительно.";
    }
  } catch {
    /* ignore */
  }
}

async function requestAiAnalysis() {
  const symbol = selectedSymbol();
  const tf = $("timeframeSelect")?.value || "5";
  const data = await api(
    `/api/v1/ai/analyze?symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(tf)}`,
    { method: "POST" }
  );
  renderAiAnalysis(data?.ai);
}

function renderTfSetups(plan) {
  const el = $("tfSetupsPanel");
  if (!el) return;
  if (!plan || !planMatchesSymbol(plan)) {
    el.innerHTML = "<p class='hint'>Выберите монету…</p>";
    return;
  }
  const chartTf = selectedChartTimeframe();
  const setups = plan.setups || [];
  if (!setups.length) {
    el.innerHTML =
      "<p class='hint'>Нет явного BUY/SELL на ТФ — нейтрально или загрузите свечи.</p>";
    return;
  }
  el.innerHTML = setups
    .map((s) => {
      const cls = s.action === "BUY" ? "buy" : "sell";
      const active = s.timeframe === chartTf ? " tf-setup-row--active" : "";
      const tag = s.timeframe === chartTf ? " · <em>график</em>" : "";
      return `<div class="tf-setup-row ${cls}${active}">
        <strong>${escapeHtml(s.label)} · ${escapeHtml(s.action)}${tag}</strong>
        <span>Вход сейчас: ${formatPrice(s.entry)} · SL ${formatPrice(s.stop_loss)} · TP ${formatPrice(s.take_profit)}</span>
        <span class="hint">${escapeHtml(s.reason || "")}</span>
      </div>`;
    })
    .join("");
}

function updateTradeLevelsPanel(chartData, overview) {
  const sym = selectedSymbol();
  const chartTf = selectedChartTimeframe();
  let plan = chartData?.trade_plan || overview?.trade_plan;
  if (plan && plan.symbol && plan.symbol !== sym) plan = null;
  if (
    lastLivePlan &&
    planMatchesSymbol(lastLivePlan) &&
    (!lastLivePlan.chart_timeframe || lastLivePlan.chart_timeframe === chartTf)
  ) {
    if (!chartData?.trade_plan || chartData.trade_plan?.chart_timeframe === chartTf) {
      plan = lastLivePlan;
    }
  } else if (plan && !planMatchesSymbol(plan)) {
    plan = null;
  }
  plan = resolvePlanForChart(plan);
  const signal = overview?.signal;
  const last = currentDisplayPrice(chartData, overview);
  const set = (id, v) => {
    const el = $(id);
    if (el) el.textContent = formatPrice(v);
  };
  set("lvlEntry", plan?.entry);
  set("lvlStop", plan?.stop_loss);
  set("lvlTp", plan?.take_profit);
  set("lvlPrice", last);
  const priceCard = document.querySelector(".level-card.price .lbl");
  if (priceCard) {
    const src = lastPriceSource || chartData?.price_source || overview?.price_source || "";
    priceCard.textContent = priceSourceLabel(src);
  }
  if (plan?.horizon_note && plan.source === "live_market") {
    const foot = $("levelsChartStatus");
    if (foot && !foot.dataset.horizonSet) {
      foot.dataset.horizonSet = "1";
    }
  }
  applyLivePlanToLevelCards(plan);
  renderTfSetups(plan);
}

async function pollLivePrice() {
  const symbol = $("symbolSelect")?.value || "BTCUSDT";
  try {
    const tf = $("timeframeSelect")?.value || "5";
    const [data, planRes] = await Promise.all([
      api(
        `/api/v1/dashboard/live-price?symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(tf)}`
      ),
      api(
        `/api/v1/dashboard/live-plan?symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(tf)}`
      ),
    ]);
    if (data?.price > 0) {
      lastLivePrice = data.price;
      lastPriceSource = data.source || "bybit_live";
      const el = $("lvlPrice");
      if (el) el.textContent = formatPrice(data.price);
      const liveEl = $("livePriceSidebar");
      if (liveEl) liveEl.textContent = formatPrice(data.price);
      updatePriceContextBanner(null, data);
    }
    if (planRes?.plan && planRes.symbol === symbol) {
      const chartTf = selectedChartTimeframe();
      if (!planRes.plan.chart_timeframe || planRes.plan.chart_timeframe === chartTf) {
        lastLivePlan = planRes.plan;
        applyLivePlanToLevelCards(planRes.plan);
        renderTfSetups(planRes.plan);
      }
    }
  } catch (e) {
    console.debug("live-price poll", e);
  }
}

function startLivePricePoll() {
  if (livePriceTimer) clearInterval(livePriceTimer);
  lastLivePrice = null;
  lastLivePlan = null;
  pollLivePrice();
  livePriceTimer = setInterval(pollLivePrice, 2000);
}

function setStatusHint(msg) {
  const el = $("lastRun");
  if (el) el.textContent = msg || "";
}

function timeframeToTvInterval(tf) {
  const map = {
    "1": "1",
    "3": "3",
    "5": "5",
    "15": "15",
    "30": "30",
    "60": "60",
    "240": "240",
    D: "D",
    W: "W",
    M: "M",
  };
  return map[tf] || tf;
}

function renderTradingViewChart(symbol, timeframe, chartData) {
  const container = $("mainChartContainer");
  const statusEl = $("levelsChartStatus");
  if (!container) return;

  const tvSym = chartData?.tradingview_symbol || symbolToTradingView(symbol);
  const link = $("tvOpenLink");
  if (link) {
    link.href = `https://www.tradingview.com/chart/?symbol=${encodeURIComponent(tvSym)}&interval=${timeframeToTvInterval(timeframe)}`;
  }

  const key = `${tvSym}:${timeframeToTvInterval(timeframe)}`;
  if (key === tvChartKey && container.querySelector(".tv-embed")) {
    updateTvChartFootnote(chartData, symbol, timeframe, statusEl);
    return;
  }
  tvChartKey = key;
  container.innerHTML = "";

  const wrap = document.createElement("div");
  wrap.className = "tradingview-widget-container tv-embed";
  wrap.style.height = "100%";
  const inner = document.createElement("div");
  inner.className = "tradingview-widget-container__widget";
  inner.style.height = "100%";
  wrap.appendChild(inner);

  const script = document.createElement("script");
  script.type = "text/javascript";
  script.src = "https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js";
  script.async = true;
  script.innerHTML = JSON.stringify({
    autosize: true,
    symbol: tvSym,
    interval: timeframeToTvInterval(timeframe),
    timezone: "Etc/UTC",
    theme: "dark",
    style: "1",
    locale: "ru",
    enable_publishing: false,
    allow_symbol_change: false,
    calendar: false,
    hide_side_toolbar: false,
    hide_top_toolbar: false,
    hide_legend: false,
    hide_volume: false,
    save_image: false,
    support_host: "https://www.tradingview.com",
  });
  wrap.appendChild(script);
  container.appendChild(wrap);

  updateTvChartFootnote(chartData, symbol, timeframe, statusEl);
}

function updateTvChartFootnote(chartData, symbol, timeframe, statusEl) {
  if (!statusEl) return;
  const levels = chartData?.trade_levels || [];
  const dropped = chartData?.candles_dropped || 0;
  const src = chartData?.trade_plan?.source === "open_position" ? "открытая позиция" : "последний сигнал";
  const plan = chartData?.trade_plan;
  const hz = plan?.horizon_label || plan?.chart_timeframe_label || tfLabel(timeframe);
  let msg = `TradingView · ${symbol} · ${tfLabel(timeframe)}`;
  if (levels.length) {
    msg += ` · Entry/SL/TP (${hz}) в карточках (${src})`;
  } else if (plan?.suggested_chart_action) {
    msg += ` · на ${hz}: ${plan.suggested_chart_action} (MTF: ${plan.action})`;
  }
  if (dropped > 0) {
    msg += ` · отфильтровано ${dropped} битых свечей`;
  }
  statusEl.textContent = msg;
}

function renderMainChart(chartData, symbol, timeframe) {
  renderTradingViewChart(symbol, timeframe, chartData);
}

function updateChartChrome(chartData, symbol, timeframe) {
  const status = $("chartStatus");
  const legend = $("chartLegend");
  const candles = chartData?.candles || [];

  updateTradeLevelsPanel(chartData, null);

  if (status) {
    const srcLabel =
      {
        database: "БД (Bybit)",
        bybit_live: "Bybit (онлайн)",
        empty: "нет данных",
      }[chartData.candle_source] || chartData.candle_source || "data";
    const dropped = chartData?.candles_dropped ? ` · −${chartData.candles_dropped} выбросов` : "";
    status.textContent = candles.length
      ? `${symbol} · ${tfLabel(timeframe)} · TradingView · ${srcLabel}${dropped}`
      : "TradingView · загрузка…";
  }

  const levels = chartData?.trade_levels || [];
  if (legend && levels.length) {
    legend.textContent =
      "Уровни Entry / SL / TP — в карточках над графиком. На TradingView нарисуй горизонтальные линии вручную или пришли Charting Library для автолиний бота.";
  }
}

async function fetchChartData(symbol, timeframe, fetchOpts = {}) {
  return api(
    `/api/v1/dashboard/chart?symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(timeframe)}`,
    fetchOpts
  );
}

function $(id) {
  return document.getElementById(id);
}

function showApiError(msg) {
  const el = $("apiError");
  if (!el) return;
  if (msg) {
    el.hidden = false;
    el.textContent = msg;
  } else {
    el.hidden = true;
    el.textContent = "";
  }
}

async function api(path, options = {}) {
  const opts = { ...options };
  opts.headers = { ...(opts.headers || {}) };
  const token = getAdminToken();
  if (token) opts.headers["X-Admin-Token"] = token;
  if (opts.method && opts.method !== "GET" && !opts.headers["Content-Type"]) {
    opts.headers["Content-Type"] = "application/json";
  }
  let res;
  try {
    res = await fetch(API + path, opts);
  } catch (err) {
    if (err?.name === "AbortError") throw err;
    const msg = String(err?.message || err);
    if (msg.includes("Failed to fetch") || msg.includes("NetworkError") || msg.includes("Load failed")) {
      throw new Error(
        "Нет связи с API. Запустите в терминале: uvicorn app.main:app --reload --port 8000"
      );
    }
    throw new Error(`Ошибка сети: ${msg}`);
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = await res.json();
      detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail || j);
    } catch {
      try {
        detail = await res.text();
      } catch {
        /* ignore */
      }
    }
    throw new Error(detail || `HTTP ${res.status}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

async function withButton(btn, fn, loadingLabel) {
  if (!btn) return;
  const prevDisabled = btn.disabled;
  const prevText = btn.textContent;
  btn.disabled = true;
  if (loadingLabel) btn.textContent = loadingLabel;
  try {
    await fn();
    showApiError("");
  } catch (e) {
    console.error(e);
    showApiError(e.message || String(e));
  } finally {
    btn.disabled = prevDisabled;
    if (loadingLabel) btn.textContent = prevText;
  }
}

function symbolToTradingView(sym) {
  const s = (sym || "BTCUSDT").toUpperCase();
  return s.includes(":") ? s : `BYBIT:${s}`;
}

function normalizeTimeframes(status, meta) {
  if (status?.timeframes?.length) return status.timeframes;
  if (meta?.timeframes?.length) {
    return meta.timeframes.map((t) => (typeof t === "string" ? t : t.code));
  }
  return ["1", "5", "15", "30", "60", "240", "D", "W", "M"];
}

function normalizeSymbols(status, meta) {
  if (meta?.symbols?.length) return meta.symbols;
  if (status?.symbols?.length) return status.symbols;
  return ["BTCUSDT"];
}

function renderIndicators(indicators) {
  const row = $("indicatorRow");
  if (!row) return;
  row.innerHTML = "";
  Object.entries(indicators || {}).forEach(([k, v]) => {
    const chip = document.createElement("span");
    chip.className = "ind-chip";
    chip.textContent = `${k.toUpperCase()}: ${Number(v).toFixed(4)}`;
    row.appendChild(chip);
  });
}

function renderMultiTf(allTf, labels) {
  const panel = $("multiTfPanel");
  if (!panel) return;
  const keys = Object.keys(allTf || {});
  if (!keys.length) {
    panel.innerHTML = '<p class="hint">Нет данных — нажми «Загрузить свечи»</p>';
    return;
  }
  panel.innerHTML = "";
  keys.forEach((tf) => {
    const ind = allTf[tf];
    const card = document.createElement("div");
    card.className = "tf-card";
    const title = (labels && labels[tf]) || tfLabel(tf);
    card.innerHTML = `<h4>${title}</h4><dl>
      <dt>Закрытие свечи</dt><dd>${fmt(ind.close)}</dd>
      <dt>RSI</dt><dd>${fmt(ind.rsi)}</dd>
      <dt>ADX</dt><dd>${fmt(ind.adx)}</dd>
      <dt>EMA</dt><dd>${fmt(ind.ema)}</dd>
      <dt>ATR</dt><dd>${fmt(ind.atr)}</dd>
    </dl>`;
    panel.appendChild(card);
  });
}

function applyTradingParams(params) {
  if (!params) return;
  const usdt = $("orderUsdt");
  const entry = $("entryOrderType");
  const mode = $("positionSizeMode");
  if (usdt != null && params.order_usdt != null) usdt.value = params.order_usdt;
  if (entry && params.entry_order_type) entry.value = params.entry_order_type;
  if (mode && params.position_size_mode) mode.value = params.position_size_mode;
}

async function saveTradingParams() {
  const body = {
    order_usdt: Number($("orderUsdt")?.value || 100),
    entry_order_type: $("entryOrderType")?.value || "Market",
    position_size_mode: $("positionSizeMode")?.value || "fixed_usdt",
  };
  await api("/api/v1/bot/trading-params", {
    method: "POST",
    body: JSON.stringify(body),
  });
  setStatusHint("Настройки сделки сохранены");
}

function renderBotActivity(activity, lastCycleDecisions, symbol) {
  const el = $("botActivity");
  if (!el) return;
  const sym = symbol || $("symbolSelect")?.value || "BTCUSDT";
  const row =
    (lastCycleDecisions || []).find((d) => d.symbol === sym) ||
    (lastCycleDecisions || [])[0];
  const text = activity || row?.activity;
  if (!text) {
    el.hidden = true;
    return;
  }
  el.hidden = false;
  el.textContent = text;
  el.className = "bot-activity";
  if (text.includes("не исполнен") || text.includes("заблокирован")) {
    el.classList.add("warn");
  } else if (text.includes("HOLD")) {
    el.classList.add("muted");
  }
}

function renderTradePlan(plan, signal, tradingParams, lastCycleDecisions) {
  const el = $("tradePlan");
  if (!el) return;
  const sym = $("symbolSelect")?.value || "BTCUSDT";
  const lc = (lastCycleDecisions || []).find((d) => d.symbol === sym);
  let data =
    plan ||
    (signal && signal.action !== "HOLD"
      ? {
          action: signal.action,
          entry: signal.entry_price,
          stop_loss: signal.stop_loss,
          take_profit: signal.take_profit,
          confidence: signal.confidence,
          reason: signal.reason,
          explanation: signal.explanation,
          regime: signal.regime,
        }
      : null);

  const chartTf = selectedChartTimeframe();
  const chartSetup = (data?.setups || []).find((s) => s.timeframe === chartTf);
  if ((!data || data.action === "HOLD") && !chartSetup) {
    el.className = "trade-plan empty";
    const blocked = lc?.risk_blocks?.length
      ? `Риск: ${lc.risk_blocks.join(", ")}`
      : "HOLD — ждём сигнал или согласованность ТФ";
    el.textContent = `Нет сделки — ${blocked}`;
    return;
  }
  if (data?.action === "HOLD" && chartSetup) {
    data = {
      ...data,
      action: chartSetup.action,
      entry: chartSetup.entry,
      stop_loss: chartSetup.stop_loss,
      take_profit: chartSetup.take_profit,
      horizon_label: chartSetup.label,
      reason: `На ${chartSetup.label}: ${chartSetup.reason} (MTF: HOLD)`,
    };
  }

  const sizeUsdt =
    lc?.suggested_usdt ||
    (tradingParams?.position_size_mode === "fixed_usdt" ? tradingParams?.order_usdt : null);
  const entryType = tradingParams?.entry_order_type || "Market";
  const horizon = data.horizon_label ? ` · горизонт ${data.horizon_label}` : "";
  const pnl = data.pnl_estimate || {};
  const rr =
    data.risk_reward_ratio != null
      ? Number(data.risk_reward_ratio).toFixed(2)
      : pnl.risk_reward_ratio != null
        ? Number(pnl.risk_reward_ratio).toFixed(2)
        : null;
  const pnlLine =
    pnl.risk_usdt != null && pnl.reward_usdt != null
      ? `<dt>≈ USDT (SL / TP)</dt><dd class="pnl-est">−${pnl.risk_usdt} / +${pnl.reward_usdt}</dd>`
      : "";

  const cls = data.action === "BUY" || data.action === "Buy" ? "buy" : "sell";
  const aiTag = data.ai_influenced
    ? '<p class="hint">План скорректирован ИИ (AI_INFLUENCE_TRADES)</p>'
    : "";
  el.className = "trade-plan";
  el.innerHTML = `
    <div class="action ${cls}">${data.action}</div>
    ${aiTag}
    ${data.regime ? `<p class="hint">Режим: ${escapeHtml(data.regime)}</p>` : ""}
    <dl>
      <dt>Уверенность</dt><dd>${data.confidence != null ? (data.confidence * 100).toFixed(0) + "%" : "—"}</dd>
      <dt>Размер</dt><dd>${sizeUsdt ? `~${Number(sizeUsdt).toFixed(0)} USDT` : "—"} · ${entryType === "Market" ? "рынок" : "лимит"}</dd>
      <dt>Вход (сейчас)</dt><dd>${fmt(data.entry)}${horizon}</dd>
      <dt>Текущая цена</dt><dd>${fmt(data.live_price || lastLivePrice)}</dd>
      <dt>Stop Loss</dt><dd>${fmt(data.stop_loss)}</dd>
      <dt>Take Profit</dt><dd>${fmt(data.take_profit)}</dd>
      ${rr ? `<dt>R:R</dt><dd>1:${rr}</dd>` : ""}
      ${pnlLine}
    </dl>
    <div class="reason">${escapeHtml(data.reason || "")}</div>
  `;
}

function renderSignal(signal) {
  const el = $("signalBox");
  if (!el) return;
  if (!signal) {
    el.textContent = "Сигналов пока нет";
    return;
  }
  el.innerHTML = `<strong>${escapeHtml(signal.action || "—")}</strong> · ${
    signal.confidence != null ? (Number(signal.confidence) * 100).toFixed(0) + "%" : "—"
  }<br/>
    <span class="hint">${escapeHtml(signal.reason || "")}</span>`;
}

function renderTraderBriefing(briefing, overview) {
  const el = $("traderBriefing");
  if (!el) return;

  const b =
    briefing ||
    (overview.last_cycle_decisions || []).find(
      (d) => d.symbol === ($("symbolSelect")?.value || "BTCUSDT")
    )?.trader_briefing;

  if (!b) {
    el.innerHTML =
      '<p class="hint">Нажми «Один цикл» или «Старт бота» — бот загрузит свечи Bybit, изучит таймфреймы и опишет план.</p>';
    return;
  }

  const conf = b.confluence || {};
  const trade = b.trade || {};
  const livePx = b.live_price || lastLivePrice;
  const biasClass = { bullish: "bias-up", bearish: "bias-down", neutral: "bias-flat" };

  const tierLabel = { higher: "старший", mid: "средний", lower: "младший" };
  const tfRows = (b.timeframes || [])
    .map((row) => {
      const cls = biasClass[row.bias] || "bias-flat";
      const biasLabel =
        { bullish: "Бычий", bearish: "Медвежий", neutral: "Нейтральный" }[row.bias] || row.bias;
      const chartMark = row.is_chart_tf ? ' <strong class="chart-tf-mark">← график</strong>' : "";
      return `<tr class="${cls}${row.is_chart_tf ? " chart-tf-row" : ""}">
        <td>${escapeHtml(tierLabel[row.tier] || "")} · ${escapeHtml(row.label)}${chartMark}</td>
        <td>${biasLabel}</td>
        <td>${escapeHtml(row.reason || "")}</td>
        <td class="num">${fmt(row.close)}</td>
      </tr>`;
    })
    .join("");

  let planHtml = "";
  if (trade.action && trade.action !== "HOLD") {
    planHtml = `
      <div class="brief-plan">
        <h4>План: ${escapeHtml(trade.action)} · уверенность ${trade.confidence_pct ?? "—"}%</h4>
        <dl class="brief-dl">
          <dt>Вход (цикл бота)</dt><dd>${fmt(trade.entry)}</dd>
          ${trade.current_price && trade.entry && Math.abs(Number(trade.current_price) - Number(trade.entry)) > 1 ? `<dt>Сейчас на рынке</dt><dd>${fmt(trade.current_price)}</dd>` : ""}
          <dt>Stop Loss</dt><dd>${fmt(trade.stop_loss)} <span class="hint">(${trade.risk_pct_signed ?? trade.risk_pct ?? "—"}%)</span></dd>
          <dt>Take Profit</dt><dd>${fmt(trade.take_profit)} <span class="hint">(+${trade.reward_pct_signed ?? trade.reward_pct ?? "—"}%)</span></dd>
          ${trade.risk_reward ? `<dt>R:R</dt><dd>1:${Number(trade.risk_reward).toFixed(2)}</dd>` : ""}
          ${
            trade.pnl_estimate?.risk_usdt != null
              ? `<dt>≈ USDT</dt><dd>−${trade.pnl_estimate.risk_usdt} / +${trade.pnl_estimate.reward_usdt}</dd>`
              : ""
          }
        </dl>
      </div>`;
  } else {
    const chartLbl = b.chart_timeframe_label || tfLabel(selectedChartTimeframe());
    planHtml = `<p class="brief-hold">MTF: без входа. Смотрите уклон на <strong>${escapeHtml(chartLbl)}</strong> в таблице (строка «← график»).</p>`;
  }

  const topDown =
    conf.higher_edge != null
      ? `<br/><span class="hint">Top-down: старшие ${conf.higher_edge > 0 ? "+" : ""}${conf.higher_edge} · средние ${conf.mid_edge > 0 ? "+" : ""}${conf.mid_edge} · младшие ${conf.lower_edge > 0 ? "+" : ""}${conf.lower_edge}</span>`
      : "";

  el.innerHTML = `
    <p class="brief-headline">${escapeHtml(b.headline || "")}</p>
    ${livePx ? `<p class="brief-live-price">Текущая цена (Bybit, как TradingView): <strong>${formatPrice(livePx)}</strong></p>` : ""}
    <p class="hint">${escapeHtml(b.mtf_summary || "")}${topDown}</p>
    <div class="brief-confluence">
      <span>Консенсус ТФ: бычьи <strong>${conf.bullish_weight ?? "—"}</strong> · медвежьи <strong>${conf.bearish_weight ?? "—"}</strong> · edge <strong>${conf.edge ?? "—"}</strong></span>
      <span class="badge-muted">режим: ${escapeHtml(b.regime || "—")}</span>
    </div>
    ${planHtml}
    <table class="brief-tf-table">
      <thead><tr><th>ТФ</th><th>Уклон</th><th>Почему</th><th>Цена</th></tr></thead>
      <tbody>${tfRows || "<tr><td colspan='4'>Нет данных — загрузи свечи</td></tr>"}</tbody>
    </table>
    <p class="hint brief-foot">${escapeHtml(b.data_note || "")}</p>
  `;
}

function renderDecisionExplanation(overview, chartData) {
  const el = $("decisionExplanation");
  if (!el) return;

  const pos = (overview.positions || []).find(
    (p) => p.symbol === ($("symbolSelect")?.value || "BTCUSDT")
  );
  const plan = chartData?.trade_plan;
  const signal = overview.signal;
  const lastCycle = (overview.last_cycle_decisions || []).find(
    (d) => d.symbol === ($("symbolSelect")?.value || "BTCUSDT")
  );

  let text = "";
  if (pos?.entry_explanation) {
    text = "📥 Открытая позиция — почему вошли:\n\n" + pos.entry_explanation;
    if (pos.exit_explanation) {
      text += "\n\n📤 Последний выход:\n\n" + pos.exit_explanation;
    }
  } else if (lastCycle?.explanation) {
    text = lastCycle.explanation;
    if (lastCycle.risk_blocks?.length) {
      text += `\n\n⚠ Риск заблокировал: ${lastCycle.risk_blocks.join(", ")}`;
    }
  } else if (signal?.explanation) {
    text = signal.explanation;
  } else if (plan?.explanation) {
    text = plan.explanation;
  } else if (signal?.reason) {
    text = signal.reason;
  } else {
    text = "Запусти «Один цикл» — бот опишет режим рынка, индикаторы и причину BUY/SELL/HOLD.";
  }

  el.textContent = text;
}

function renderDecisionJournal(journal, lastCycle) {
  const ul = $("decisionJournal");
  if (!ul) return;
  ul.innerHTML = "";

  const items = [];
  (lastCycle || []).forEach((d) => {
    items.push({
      when: "последний цикл",
      action: d.action,
      reason: d.reason,
      explanation: d.explanation,
      blocks: d.risk_blocks,
    });
  });
  (journal || []).forEach((d) => {
    items.push({
      when: d.created_at || "",
      action: d.action,
      reason: d.reason,
      explanation: d.explanation,
      regime: d.regime,
    });
  });

  if (!items.length) {
    ul.innerHTML = "<li class='hint'>Пока нет записей</li>";
    return;
  }

  items.slice(0, 10).forEach((item) => {
    const li = document.createElement("li");
    const blocks =
      item.blocks?.length ? `<div class="hint">Риск: ${escapeHtml(item.blocks.join(", "))}</div>` : "";
    li.innerHTML = `
      <div class="journal-head">
        <strong>${escapeHtml(item.action || "?")}</strong>
        <span class="meta">${escapeHtml(item.when || "")}${item.regime ? " · " + escapeHtml(item.regime) : ""}</span>
      </div>
      <div class="journal-summary">${escapeHtml(item.reason || "")}</div>
      ${blocks}
      ${item.explanation ? `<details><summary>Полное объяснение</summary><pre class="journal-detail">${escapeHtml(item.explanation)}</pre></details>` : ""}
    `;
    ul.appendChild(li);
  });
}

function renderRisk(guide, bot, events) {
  const el = $("riskBox");
  if (!el) return;
  const g = guide || {};
  const ks = g.kill_switch_ok
    ? '<p class="risk-ok">Аварийный стоп: выкл (норма)</p>'
    : '<p class="risk-block">⚠ Аварийный стоп ВКЛ — новые сделки запрещены</p>';
  const summary = g.summary
    ? `<p class="risk-guide-summary">${escapeHtml(g.summary)}</p>`
    : "<p class='hint'>Запустите бота — здесь будет причина, если вход заблокирован.</p>";
  const blocks = (g.blocks || [])
    .map((b) => `<li>${escapeHtml(b.text || b.code || "")}</li>`)
    .join("");
  const blocksHtml = blocks
    ? `<ul class="risk-guide-blocks">${blocks}</ul>`
    : "";
  const tech = (events || [])
    .slice(0, 3)
    .map((e) => `<li class="hint">${escapeHtml(e.message)}</li>`)
    .join("");
  el.innerHTML =
    ks +
    summary +
    blocksHtml +
    (tech ? `<details class="hint"><summary>Технический журнал</summary><ul class="audit-list">${tech}</ul></details>` : "");
}

function setAnalysisNote(plan) {
  const el = $("analysisNote");
  if (!el) return;
  el.textContent =
    plan?.analysis_note ||
    "Бот анализирует свечи Bybit (не скриншот TV). Смените таймфрейм — уровни пересчитаются.";
}

function renderLearning(learning) {
  const el = $("learningBox");
  if (!el) return;
  if (!learning) {
    el.textContent = "Нет данных обучения";
    return;
  }
  const wr = ((learning.win_rate || 0) * 100).toFixed(0);
  el.innerHTML = `
    <p>Исходов: <strong>${learning.total_outcomes || 0}</strong> · Win rate: <strong>${wr}%</strong></p>
    <p class="hint">W: ${learning.wins || 0} / L: ${learning.losses || 0}</p>
    <ul class="audit-list">
      ${(learning.recent || [])
        .slice(0, 5)
        .map(
          (o) =>
            `<li>${o.symbol} ${o.outcome} ${o.pnl_pct != null ? Number(o.pnl_pct).toFixed(2) : "—"}% (${o.exit_reason || ""})</li>`
        )
        .join("") || "<li>Пока нет закрытых сделок</li>"}
    </ul>`;
}

function renderChanges(changes) {
  const ul = $("changesList");
  if (!ul) return;
  ul.innerHTML = "";
  (changes || []).forEach((c) => {
    const li = document.createElement("li");
    li.innerHTML = `<span class="meta">${c.severity} · ${c.timeframe || ""}</span>
      <strong>${escapeHtml(c.change_type)}</strong> — ${escapeHtml(c.message || "")}`;
    ul.appendChild(li);
  });
  if (!changes?.length) {
    ul.innerHTML =
      "<li class='hint'>Изменения появятся после циклов бота (память снапшотов)</li>";
  }
}

function renderAudit(audit) {
  const ul = $("auditList");
  if (!ul) return;
  ul.innerHTML = "";
  (audit || []).forEach((a) => {
    const li = document.createElement("li");
    li.innerHTML = `<span class="meta">${a.created_at || ""}</span> · <strong>${a.event_type}</strong>`;
    ul.appendChild(li);
  });
}

function updateBotBadges(bot, candleSource) {
  if (!bot) return;
  const st = $("botStatus");
  if (st) {
    st.textContent = bot.running ? "Работает" : "Остановлен";
    st.className = "badge " + (bot.running ? "on" : "off");
  }
  const mode = $("modeBadge");
  if (mode) {
    mode.textContent = (bot.trading_mode || "paper").toUpperCase();
    mode.className = "badge " + (bot.live_enabled ? "live" : "");
  }
  const marketBadge = $("marketBadge");
  if (marketBadge) {
    marketBadge.textContent =
      bot.market_source === "bybit"
        ? `Bybit · ${candleSource || "data"}`
        : "Mock data";
  }

  const bg = bot.background || {};
  const monitorBadge = $("monitorBadge");
  if (monitorBadge) {
    if (bg.running) {
      monitorBadge.textContent = bg.last_position_at ? "SL/TP 24/7 ✓" : "SL/TP 24/7 …";
      monitorBadge.className = "badge on";
    } else {
      monitorBadge.textContent = "Monitor off";
      monitorBadge.className = "badge muted";
    }
  }

  const lastRun = $("lastRun");
  if (lastRun) {
    lastRun.textContent = bot.last_run_at
      ? `Последний цикл: ${bot.last_run_at}${bot.last_error ? " · Ошибка: " + bot.last_error : ""}`
      : "";
  }

  const bgEl = $("backgroundStatus");
  if (bgEl && bg.running) {
    bgEl.textContent = `Фон: мониторинг SL/TP каждые ${bg.position_interval_seconds || "?"}s · последняя проверка: ${bg.last_position_at || "—"}`;
  }
}

function populateTimeframes(timeframes, labels) {
  const sel = $("timeframeSelect");
  if (!sel) return;
  const prev = sel.value;
  sel.innerHTML = "";
  const list = timeframes || ["1", "5", "15", "30", "60", "240", "D"];
  list.forEach((tf) => {
    const opt = document.createElement("option");
    opt.value = tf;
    opt.textContent = (labels && labels[tf]) || tfLabel(tf);
    sel.appendChild(opt);
  });
  if (prev && list.includes(prev)) sel.value = prev;
  else if (!sel.value && list.includes("5")) sel.value = "5";
}

async function loadRatioSection() {
  const holdingsEl = $("ratioHoldings");
  const pairsEl = $("ratioPairsTable");
  const proposalsEl = $("ratioProposals");
  if (!holdingsEl || !pairsEl || !proposalsEl) return;

  let holdings = {};
  let pairs = [];
  let pending = [];
  try {
    const [h, p, pr] = await Promise.all([
      api("/api/v1/ratio-swaps/holdings"),
      api("/api/v1/ratio-swaps/pairs"),
      api("/api/v1/ratio-swaps/proposals?status=pending"),
    ]);
    holdings = h?.holdings || {};
    pairs = p?.pairs || [];
    pending = pr?.proposals || [];
  } catch (e) {
    console.warn("ratio load failed", e);
    return;
  }

  const holdingsData = holdings;
  const entries = Object.entries(holdingsData);
  holdingsEl.innerHTML = entries.length
    ? `<p class="hint">Paper-портфель для ротации:</p><div class="holdings-chips">${entries
        .map(
          ([a, q]) =>
            `<span class="hold-chip"><strong>${escapeHtml(a)}</strong> ${Number(q).toFixed(6)}</span>`
        )
        .join("")}</div>`
    : "<p class='hint'>Нет holdings — нажми «Сканировать соотношения»</p>";

  if (!pairs.length) {
    pairsEl.innerHTML = "<p class='hint'>Загрузи свечи (D) и запусти сканирование</p>";
  } else {
    pairsEl.innerHTML = `<table class="ratio-table"><thead><tr>
      <th>Пара</th><th>Сейчас</th><th>Мин</th><th>Сред</th><th>Макс</th><th>%</th>
    </tr></thead><tbody>${pairs
      .map(
        (p) => `<tr>
        <td>${escapeHtml(p.pair_label)}</td>
        <td>${Number(p.ratio_current).toFixed(2)}</td>
        <td>${Number(p.ratio_min).toFixed(2)}</td>
        <td>${Number(p.ratio_mean).toFixed(2)}</td>
        <td>${Number(p.ratio_max).toFixed(2)}</td>
        <td>${Number(p.ratio_percentile).toFixed(0)}%</td>
      </tr>`
      )
      .join("")}</tbody></table>`;
  }

  proposalsEl.innerHTML = "";
  if (!pending.length) {
    proposalsEl.innerHTML = "<li class='hint'>Нет ожидающих обменов</li>";
    return;
  }

  pending.forEach((p) => {
    const li = document.createElement("li");
    li.className = "ratio-proposal-item";
    li.innerHTML = `
      <div class="journal-head">
        <strong>${escapeHtml(p.from_asset)} → ${escapeHtml(p.to_asset)}</strong>
        <span class="meta">${escapeHtml(p.pair_label)} · ${Number(p.ratio_current).toFixed(2)} · ${Number(p.ratio_percentile || 0).toFixed(0)}%</span>
      </div>
      <p>${escapeHtml(p.from_qty?.toFixed?.(6) ?? p.from_qty)} → ${escapeHtml(p.to_qty?.toFixed?.(6) ?? p.to_qty)}</p>
      <details><summary>Объяснение</summary><pre class="journal-detail">${escapeHtml(p.explanation || "")}</pre></details>
      <div class="proposal-actions">
        <button type="button" class="btn primary btn-sm" data-approve="${p.id}">✓ Подтвердить</button>
        <button type="button" class="btn danger btn-sm" data-reject="${p.id}">✗ Отклонить</button>
      </div>`;
  proposalsEl.appendChild(li);
  });

  proposalsEl.querySelectorAll("[data-approve]").forEach((btn) => {
    btn.addEventListener("click", () =>
      withButton(btn, async () => {
        await api(`/api/v1/ratio-swaps/proposals/${btn.dataset.approve}/approve`, { method: "POST" });
        await refreshAll();
      })
    );
  });
  proposalsEl.querySelectorAll("[data-reject]").forEach((btn) => {
    btn.addEventListener("click", () =>
      withButton(btn, async () => {
        await api(`/api/v1/ratio-swaps/proposals/${btn.dataset.reject}/reject`, { method: "POST" });
        await refreshAll();
      })
    );
  });
}

function symbolOptionLabel(sym) {
  const p = symbolPickMap[sym];
  if (!p) return sym;
  const act = p.action || "—";
  if (p.confidence != null && p.confidence > 0) {
    return `${sym} · ${act} ${Math.round(Number(p.confidence) * 100)}%`;
  }
  if (p.score != null && Number(p.score) > 0) {
    return `${sym} · ${act} ${Math.round(Number(p.score))}`;
  }
  return `${sym} · ${act}`;
}

function opportunityPickOrder() {
  const order = new Map();
  (lastOpportunityMeta?.picks || []).forEach((p, i) => {
    if (p?.symbol) order.set(String(p.symbol).toUpperCase(), i);
  });
  (lastOpportunityMeta?.scanner_top || []).forEach((s, i) => {
    const su = String(s).toUpperCase();
    if (!order.has(su)) order.set(su, 100 + i);
  });
  return order;
}

function sortSymbolsByOpportunity(list) {
  const order = opportunityPickOrder();
  return [...list].sort((a, b) => {
    const ia = order.has(a) ? order.get(a) : 9999;
    const ib = order.has(b) ? order.get(b) : 9999;
    if (ia !== ib) return ia - ib;
    return a.localeCompare(b);
  });
}

function applyOpportunityMeta(opp) {
  if (!opp) return;
  lastOpportunityMeta = opp;
  symbolPickMap = {};
  (opp.picks || []).forEach((p) => {
    if (p?.symbol) symbolPickMap[String(p.symbol).toUpperCase()] = p;
  });
  renderOpportunitiesPanel(opp);
  filterSymbolOptions($("symbolFilter")?.value || "");
}

function renderOpportunitiesPanel(opp) {
  const el = $("opportunitiesPanel");
  if (!el) return;
  const picks = (opp?.picks || [])
    .filter((p) => p.action !== "HOLD" || Number(p.score) > 0)
    .slice(0, 10);
  if (!picks.length) {
    el.innerHTML =
      '<p class="hint">Запустите бота или «Один цикл» — здесь появятся лучшие монеты.</p>';
    return;
  }
  const cur = selectedSymbol();
  el.innerHTML = picks
    .map((p) => {
      const sym = p.symbol;
      const cls = [
        "opp-chip",
        sym === cur ? "active" : "",
        p.executed ? "executed" : "",
      ]
        .filter(Boolean)
        .join(" ");
      const conf =
        p.confidence != null && p.confidence > 0
          ? `${Math.round(Number(p.confidence) * 100)}%`
          : p.score != null
            ? `+${Math.round(Number(p.score))}`
            : "";
      const badge = p.executed ? "✓" : p.risk_allowed === false ? "⛔" : "";
      const title = escapeHtml(p.reason || p.activity || "");
      return `<button type="button" class="${cls}" data-opp-symbol="${sym}" title="${title}">
        <span class="opp-sym">${sym.replace(/USDT$/i, "")}</span>
        <span class="opp-act ${String(p.action || "").toLowerCase()}">${p.action || "—"}</span>
        <span class="opp-score">${conf}</span>${badge ? `<span class="opp-badge">${badge}</span>` : ""}
      </button>`;
    })
    .join("");

  el.querySelectorAll("[data-opp-symbol]").forEach((btn) => {
    btn.addEventListener("click", () => {
      userPinnedSymbol = true;
      const auto = $("autoSymbolFollow");
      if (auto) auto.checked = false;
      setSymbolProgrammatic(btn.dataset.oppSymbol);
      tvChartKey = "";
      lastLivePlan = null;
      lastOverview = null;
      startLivePricePoll();
      refreshAll();
    });
  });
}

function setSymbolProgrammatic(sym) {
  const su = String(sym || "").toUpperCase();
  if (!su) return;
  programmaticSymbolChange = true;
  const select = $("symbolSelect");
  if (select) {
    if (![...select.options].some((o) => o.value === su)) {
      const opt = document.createElement("option");
      opt.value = su;
      opt.textContent = symbolOptionLabel(su);
      select.insertBefore(opt, select.firstChild);
    }
    select.value = su;
  }
  programmaticSymbolChange = false;
}

function maybeAutoFocusChartSymbol(opp) {
  if (!opp || userPinnedSymbol) return false;
  const rec = opp.recommended_chart_symbol;
  if (!rec) return false;
  const cur = selectedSymbol();
  if (rec === cur) return false;
  const known =
    allSymbols.includes(rec) ||
    (lastOpportunityMeta?.picks || []).some((p) => p.symbol === rec);
  if (!known) return false;
  setSymbolProgrammatic(rec);
  setStatusHint(`График: ${rec} — лучший сигнал бота`);
  return true;
}

function opportunitiesFromScannerStatus(st) {
  const scan = st?.last_scan;
  if (!scan?.ranked?.length) return null;
  const picks = scan.ranked.map((r) => ({
    symbol: r.symbol,
    score: r.score,
    action: r.action || "HOLD",
    source: "scanner",
  }));
  return {
    picks,
    recommended_chart_symbol: (scan.top_symbols || [])[0] || picks[0]?.symbol,
    scanner_top: scan.top_symbols || [],
    trading_universe: [],
  };
}

async function loadScannerOpportunities() {
  try {
    const st = await api("/api/v1/scanner/status");
    const opp = opportunitiesFromScannerStatus(st);
    if (opp) applyOpportunityMeta(opp);
    return opp;
  } catch (e) {
    console.debug("scanner status", e);
    return null;
  }
}

function populateSymbols(symbols) {
  allSymbols = (symbols || []).map((s) => String(s).toUpperCase());
  const select = $("symbolSelect");
  if (!select) return;
  const prev = select.value;
  select.innerHTML = "";
  sortSymbolsByOpportunity(allSymbols).forEach((s) => {
    const opt = document.createElement("option");
    opt.value = s;
    opt.textContent = symbolOptionLabel(s);
    if (symbolPickMap[s]) opt.className = "opportunity-top";
    select.appendChild(opt);
  });
  if (prev && allSymbols.includes(prev)) select.value = prev;
  const hint = $("symbolCountHint");
  if (hint) hint.textContent = `${allSymbols.length} пар USDT с Bybit`;
  filterSymbolOptions($("symbolFilter")?.value || "");
}

function filterSymbolOptions(query) {
  const select = $("symbolSelect");
  if (!select || !allSymbols.length) return;
  const q = String(query || "")
    .trim()
    .toUpperCase();
  let filtered = q
    ? allSymbols.filter((s) => s.includes(q))
    : allSymbols;
  filtered = sortSymbolsByOpportunity(filtered);
  const prev = select.value;
  select.innerHTML = "";
  filtered.slice(0, 200).forEach((s) => {
    const opt = document.createElement("option");
    opt.value = s;
    opt.textContent = symbolOptionLabel(s);
    if (symbolPickMap[s]) opt.className = "opportunity-top";
    select.appendChild(opt);
  });
  if (prev && filtered.includes(prev)) select.value = prev;
  else if (filtered.length) select.value = filtered[0];
}

function applyDashboardData(overview, chartData, symbol, timeframe) {
  lastOverview = overview;
  updateBotBadges(overview.bot, overview.candle_source || chartData?.candle_source);
  renderIndicators(overview.indicators || chartData?.indicators);
  renderMultiTf(overview.indicators_all_timeframes, overview.bot?.timeframe_labels);
  applyTradingParams(overview.trading_params);
  const displayPlan = overview.trade_plan || chartData?.trade_plan;
  if (displayPlan) lastLivePlan = displayPlan;
  renderTradePlan(
    displayPlan,
    overview.signal,
    overview.trading_params,
    overview.last_cycle_decisions
  );
  renderBotActivity(overview.bot_activity, overview.last_cycle_decisions, symbol);
  renderSignal(overview.signal);
  renderTraderBriefing(overview.trader_briefing, overview);
  renderDecisionExplanation(overview, chartData);
  renderDecisionJournal(overview.decision_journal, overview.last_cycle_decisions);
  renderRisk(overview.risk_guide, overview.bot, overview.risk_events);
  setAnalysisNote(displayPlan);
  renderTfSetups(displayPlan);
  if (displayPlan?.ai) renderAiAnalysis(displayPlan.ai);
  renderAudit(overview.audit);
  renderLearning(overview.learning);
  renderChanges(overview.market_changes);

  lastLivePrice = overview.last_price > 0 ? overview.last_price : lastLivePrice;
  lastPriceSource = overview.price_source || lastPriceSource;
  updatePriceContextBanner(overview, overview.price_info);
  updateTradeLevelsPanel(chartData, overview);
  updateChartChrome(chartData, symbol, timeframe);
  renderMainChart(chartData, symbol, timeframe);
}

async function loadOverview(fetchOpts = {}) {
  const symbol = $("symbolSelect")?.value || "BTCUSDT";
  const timeframe = $("timeframeSelect")?.value || "5";
  const [overview, chartData] = await Promise.all([
    api(
      `/api/v1/dashboard/overview?symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(timeframe)}&include_ratios=false`,
      fetchOpts
    ),
    fetchChartData(symbol, timeframe, fetchOpts),
  ]);
  applyDashboardData(overview, chartData, symbol, timeframe);
  return { overview, chartData };
}

async function ensureCandlesForChart(symbol, timeframe, signal) {
  try {
    await api(
      `/api/v1/dashboard/refresh-market?symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(timeframe)}`,
      { method: "POST", signal }
    );
  } catch (e) {
    if (e?.name !== "AbortError") console.debug("auto refresh candles", e);
  }
}

async function refreshChartOnly() {
  const symbol = $("symbolSelect")?.value || "BTCUSDT";
  const timeframe = $("timeframeSelect")?.value || "5";
  if (refreshAbort) refreshAbort.abort();
  refreshAbort = new AbortController();
  const signal = refreshAbort.signal;
  try {
    setStatusHint(`ТФ ${tfLabel(timeframe)}: свечи Bybit + анализ…`);
    await ensureCandlesForChart(symbol, timeframe, signal);
    const chartData = await fetchChartData(symbol, timeframe, { signal });
    const overview = lastOverview || { trade_plan: chartData.trade_plan, price_info: chartData.price_info };
    if (chartData.trade_plan) {
      lastLivePlan = chartData.trade_plan;
      setAnalysisNote(chartData.trade_plan);
    }
    updateTradeLevelsPanel(chartData, overview);
    updateChartChrome(chartData, symbol, timeframe);
    renderMainChart(chartData, symbol, timeframe);
    if (chartData.trader_briefing) {
      renderTraderBriefing(chartData.trader_briefing, lastOverview);
    }
    if (chartData.price_note) {
      updatePriceContextBanner({ price_note: chartData.price_note }, chartData.price_info);
    }
    if (lastOverview) {
      renderTradePlan(
        resolvePlanForChart(chartData.trade_plan || lastOverview.trade_plan),
        lastOverview.signal,
        lastOverview.trading_params,
        lastOverview.last_cycle_decisions
      );
    }
    renderTfSetups(chartData.trade_plan || lastOverview?.trade_plan);
    showApiError("");
    setStatusHint("");
  } catch (e) {
    if (e?.name === "AbortError") return;
    console.error(e);
    showApiError(e.message || String(e));
  }
}

async function refreshAll() {
  if (refreshAbort) refreshAbort.abort();
  refreshAbort = new AbortController();
  const signal = refreshAbort.signal;
  try {
    let { overview } = await loadOverview({ signal });
    const opp = overview?.trading_opportunities || lastOpportunityMeta;
    if (opp) {
      applyOpportunityMeta(opp);
      if (maybeAutoFocusChartSymbol(opp)) {
        tvChartKey = "";
        lastLivePlan = null;
        lastOverview = null;
        startLivePricePoll();
        ({ overview } = await loadOverview({ signal }));
        if (overview?.trading_opportunities) {
          applyOpportunityMeta(overview.trading_opportunities);
        }
      }
    }
    showApiError("");
  } catch (e) {
    if (e?.name === "AbortError") return;
    console.error(e);
    showApiError(e.message || String(e));
  }
}

function fmt(v) {
  return v == null || Number.isNaN(Number(v)) ? "—" : Number(v).toFixed(2);
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

/** Bind buttons first — works even if API is down. */
function bindControls() {
  const btnStart = $("btnStart");
  const btnStop = $("btnStop");
  const btnOnce = $("btnOnce");
  const btnRefreshMarket = $("btnRefreshMarket");
  const btnRatioScan = $("btnRatioScan");
  const btnRefreshMarketFull = $("btnRefreshMarketFull");

  if (btnStart) {
    btnStart.addEventListener("click", () =>
      withButton(btnStart, async () => {
        const r = await api("/api/v1/bot/start", { method: "POST" });
        setStatusHint(
          r?.hint ||
            "Бот запущен: первый цикл сразу, далее каждые несколько сек. Смотри «Что сделал бот»."
        );
        await refreshAll();
      }, "Запуск…")
    );
  }
  if (btnStop) {
    btnStop.addEventListener("click", () =>
      withButton(btnStop, async () => {
        await api("/api/v1/bot/stop", { method: "POST" });
        setStatusHint("Бот остановлен");
        await refreshAll();
      }, "Стоп…")
    );
  }
  if (btnOnce) {
    btnOnce.addEventListener("click", () =>
      withButton(
        btnOnce,
        async () => {
          await api("/api/v1/bot/run-once", { method: "POST" });
          setStatusHint("Цикл завершён");
          await refreshAll();
        },
        "Цикл… (30–90 сек)"
      )
    );
  }
  if (btnRefreshMarket) {
    btnRefreshMarket.addEventListener("click", () =>
      withButton(
        btnRefreshMarket,
        async () => {
          const sym = $("symbolSelect")?.value || "BTCUSDT";
          const tf = $("timeframeSelect")?.value || "5";
          await api(
            `/api/v1/dashboard/refresh-market?symbol=${encodeURIComponent(sym)}&timeframe=${encodeURIComponent(tf)}`,
            { method: "POST" }
          );
          setStatusHint(`Свечи обновлены: ${sym} ${tfLabel(tf)}`);
          await refreshAll();
        },
        "Загрузка…"
      )
    );
  }
  if (btnRefreshMarketFull) {
    btnRefreshMarketFull.addEventListener("click", () =>
      withButton(
        btnRefreshMarketFull,
        async () => {
          if (!confirm("Загрузить ВСЕ монеты и таймфреймы? Это может занять несколько минут.")) {
            return;
          }
          await api("/api/v1/dashboard/refresh-market?full=true", { method: "POST" });
          setStatusHint("Полная загрузка завершена");
          await refreshAll();
        },
        "Все ТФ…"
      )
    );
  }
  const btnSaveTrading = $("btnSaveTrading");
  if (btnSaveTrading) {
    btnSaveTrading.addEventListener("click", () =>
      withButton(btnSaveTrading, () => saveTradingParams(), "Сохранение…")
    );
  }
  const btnAi = $("btnAiAnalyze");
  if (btnAi) {
    btnAi.addEventListener("click", () =>
      withButton(btnAi, () => requestAiAnalysis(), "ИИ…")
    );
  }
  if (btnRatioScan) {
    btnRatioScan.addEventListener("click", () =>
      withButton(
        btnRatioScan,
        async () => {
          const r = await api("/api/v1/ratio-swaps/scan", { method: "POST" });
          alert(`Новых предложений: ${r?.created ?? 0}`);
          await loadRatioSection();
        },
        "Скан…"
      )
    );
  }
  $("symbolFilter")?.addEventListener("input", (e) => {
    filterSymbolOptions(e.target.value);
  });
  $("symbolSelect")?.addEventListener("change", () => {
    if (!programmaticSymbolChange) {
      userPinnedSymbol = true;
      const auto = $("autoSymbolFollow");
      if (auto) auto.checked = false;
    }
    tvChartKey = "";
    lastLivePlan = null;
    lastOverview = null;
    startLivePricePoll();
    refreshAll();
  });
  $("autoSymbolFollow")?.addEventListener("change", (e) => {
    userPinnedSymbol = !e.target.checked;
    if (!userPinnedSymbol) refreshAll();
  });
  $("adminTokenInput")?.addEventListener("change", (e) => {
    setAdminToken(e.target.value);
  });
  $("adminTokenSave")?.addEventListener("click", () => {
    setAdminToken($("adminTokenInput")?.value || "");
    showApiError("");
    setStatusHint("Токен сохранён в браузере");
  });
  $("timeframeSelect")?.addEventListener("change", () => {
    tvChartKey = "";
    lastLivePlan = null;
    if (tfChangeTimer) clearTimeout(tfChangeTimer);
    tfChangeTimer = setTimeout(() => {
      startLivePricePoll();
      refreshChartOnly();
    }, 300);
  });
}

async function init() {
  bindControls();

  let status = {};
  let meta = { symbols: ["BTCUSDT"], timeframes: [] };

  try {
    await api("/api/v1/health");
    [status, meta] = await Promise.all([
      api("/api/v1/bot/status"),
      api("/api/v1/dashboard/meta"),
    ]);
    showApiError("");
  } catch (e) {
    console.error(e);
    showApiError(e.message || String(e));
    populateSymbols(["BTCUSDT"]);
    populateTimeframes(["1", "5", "60"], TF_LABELS);
    return;
  }

  populateSymbols(normalizeSymbols(status, meta));
  const adminInput = $("adminTokenInput");
  if (adminInput) adminInput.value = getAdminToken();
  if (status.auth_required && !getAdminToken()) {
    showApiError("Задайте API_ADMIN_TOKEN в поле ниже (Дополнительно) для управления ботом.");
  }
  const seedOpp =
    status.trading_opportunities ||
    (await loadScannerOpportunities());
  if (seedOpp && !userPinnedSymbol && seedOpp.recommended_chart_symbol) {
    setSymbolProgrammatic(seedOpp.recommended_chart_symbol);
  }
  const tfs = normalizeTimeframes(status, meta);
  const labels =
    status.timeframe_labels ||
    Object.fromEntries((meta.timeframes || []).map((t) => [t.code, t.label]));
  populateTimeframes(tfs, labels);
  applyTradingParams(status.trading_params);

  await refreshAll();
  loadRatioSection();
  loadAiStatus();
  startLivePricePoll();

  if (refreshTimer) clearInterval(refreshTimer);
  refreshTimer = setInterval(refreshAll, 20000);
  if (ratioTimer) clearInterval(ratioTimer);
  ratioTimer = setInterval(loadRatioSection, 120000);
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
