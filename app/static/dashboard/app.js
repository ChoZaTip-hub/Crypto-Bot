const API = "";

const TF_LABELS = {
  "1": "1m", "3": "3m", "5": "5m", "15": "15m", "30": "30m",
  "60": "1h", "240": "4h", "D": "1D", "W": "1W", "M": "1MN",
};

let tvWidgetNonce = 0;
let refreshTimer = null;
let levelsChart = null;
let candleSeries = null;
let levelPriceLines = [];
let levelsResizeObserver = null;
let lastLevelsKey = "";
let candlesAutoFetched = false;

const TV_INTERVAL_MAP = {
  "1": "1",
  "3": "3",
  "5": "5",
  "15": "15",
  "30": "30",
  "60": "60",
  "240": "240",
  "D": "D",
  "W": "W",
  "M": "M",
};

function updateTradeLevelsPanel(chartData) {
  const plan = chartData?.trade_plan;
  const last = chartData?.last_price;
  const set = (id, v) => {
    const el = $(id);
    if (el) el.textContent = v == null ? "—" : Number(v).toLocaleString("en-US", { maximumFractionDigits: 2 });
  };
  set("lvlEntry", plan?.entry);
  set("lvlStop", plan?.stop_loss);
  set("lvlTp", plan?.take_profit);
  set("lvlPrice", last);
}

function destroyLevelsChart() {
  if (levelsResizeObserver) {
    levelsResizeObserver.disconnect();
    levelsResizeObserver = null;
  }
  if (levelsChart) {
    levelsChart.remove();
    levelsChart = null;
    candleSeries = null;
    levelPriceLines = [];
  }
}

function renderLevelsChart(chartData, symbol, timeframe) {
  const container = $("levelsChartContainer");
  const statusEl = $("levelsChartStatus");
  if (!container) return;

  const candles = chartData?.candles || [];
  const key = `${symbol}:${timeframe}`;
  if (key !== lastLevelsKey) {
    destroyLevelsChart();
    lastLevelsKey = key;
  }

  if (!candles.length) {
    destroyLevelsChart();
    container.innerHTML = '<p class="hint chart-empty">Нет свечей — нажми «Загрузить свечи Bybit» или подожди авто-загрузку</p>';
    if (statusEl) statusEl.textContent = "";
    return;
  }

  if (typeof LightweightCharts === "undefined") {
    container.innerHTML = '<p class="hint chart-empty">Библиотека TradingView Lightweight Charts не загрузилась</p>';
    return;
  }

  container.innerHTML = "";
  const width = container.clientWidth || 800;

  if (!levelsChart) {
    levelsChart = LightweightCharts.createChart(container, {
      width,
      height: 360,
      layout: { background: { color: "#0f0f0f" }, textColor: "#d1d5db" },
      grid: {
        vertLines: { color: "rgba(242, 242, 242, 0.06)" },
        horzLines: { color: "rgba(242, 242, 242, 0.06)" },
      },
      rightPriceScale: { borderColor: "#243044" },
      timeScale: { borderColor: "#243044", timeVisible: true, secondsVisible: false },
    });
    candleSeries = levelsChart.addCandlestickSeries({
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderVisible: false,
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
    });
    levelsResizeObserver = new ResizeObserver(() => {
      if (levelsChart && container.clientWidth > 0) {
        levelsChart.applyOptions({ width: container.clientWidth });
      }
    });
    levelsResizeObserver.observe(container);
  }

  candleSeries.setData(
    candles.map((c) => ({
      time: c.time,
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    }))
  );

  levelPriceLines.forEach((pl) => candleSeries.removePriceLine(pl));
  levelPriceLines = [];

  const levels = chartData?.trade_levels || [];
  levels.forEach((lvl) => {
    const lineStyle =
      lvl.lineStyle === "dashed"
        ? LightweightCharts.LineStyle.Dashed
        : LightweightCharts.LineStyle.Solid;
    levelPriceLines.push(
      candleSeries.createPriceLine({
        price: lvl.price,
        color: lvl.color,
        lineWidth: lvl.name === "Entry" ? 3 : 2,
        lineStyle,
        axisLabelVisible: true,
        title: lvl.name,
      })
    );
  });

  levelsChart.timeScale().fitContent();

  if (statusEl) {
    const src = chartData?.trade_plan?.source === "open_position" ? "открытая позиция" : "последний сигнал";
    statusEl.textContent = levels.length
      ? `${symbol} · ${tfLabel(timeframe)} · ${levels.length} линии (${src})`
      : `${symbol} · ${tfLabel(timeframe)} · свечи загружены, уровни после «Один цикл»`;
  }
}

function loadTradingViewChart(symbol, interval, chartData) {
  const wrap = $("tvChartContainer");
  if (!wrap) return;

  tvWidgetNonce += 1;
  const nonce = tvWidgetNonce;
  const tvSymbol = chartData?.tradingview_symbol || symbolToTradingView(symbol);
  const tvInterval = TV_INTERVAL_MAP[interval] || interval || "5";

  const link = $("tvOpenLink");
  if (link) {
    link.href = `https://www.tradingview.com/chart/?symbol=${encodeURIComponent(tvSymbol)}&interval=${tvInterval}`;
  }

  wrap.innerHTML = `<div class="tradingview-widget-container__widget" style="height:100%;width:100%"></div>`;

  const script = document.createElement("script");
  script.type = "text/javascript";
  script.src = "https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js";
  script.async = true;
  script.text = JSON.stringify({
    allow_symbol_change: false,
    calendar: false,
    details: false,
    hide_side_toolbar: false,
    hide_top_toolbar: false,
    hide_legend: false,
    hide_volume: false,
    interval: tvInterval,
    locale: "ru",
    save_image: true,
    style: "1",
    symbol: tvSymbol,
    theme: "dark",
    timezone: "Etc/UTC",
    backgroundColor: "#0F0F0F",
    gridColor: "rgba(242, 242, 242, 0.06)",
    watchlist: [],
    withdateranges: true,
    compareSymbols: [],
    studies: [],
    autosize: true,
  });
  script.onload = () => {
    if (nonce !== tvWidgetNonce) script.remove();
  };
  wrap.appendChild(script);
}

function updateChartChrome(chartData, symbol, timeframe) {
  const status = $("chartStatus");
  const legend = $("chartLegend");
  const candles = chartData?.candles || [];

  updateTradeLevelsPanel(chartData);

  if (status) {
    status.textContent = candles.length
      ? `${symbol} · ${tfLabel(timeframe)} · ${chartData.candle_source || "data"} · ${candles.length} свечей`
      : "Загрузка свечей с Bybit…";
  }

  const levels = chartData?.trade_levels || [];
  if (legend) {
    legend.textContent = levels.length
      ? "Верхний график (TradingView Lightweight Charts): синяя линия — вход, красная пунктир — Stop Loss, зелёная — Take Profit. Ниже — полный TradingView для рисования."
      : "Свечи Bybit на верхнем графике. Уровни Entry / SL / TP появятся после «Один цикл» или при открытой позиции.";
  }
}

async function fetchChartData(symbol, timeframe) {
  let chartData = await api(
    `/api/v1/dashboard/chart?symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(timeframe)}`
  );
  if (!chartData.candles?.length && !candlesAutoFetched) {
    candlesAutoFetched = true;
    try {
      await api("/api/v1/dashboard/refresh-market", { method: "POST" });
      chartData = await api(
        `/api/v1/dashboard/chart?symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(timeframe)}`
      );
    } catch (e) {
      console.warn("auto candle fetch failed", e);
    }
  }
  return chartData;
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
  if (opts.method && opts.method !== "GET" && !opts.headers) {
    opts.headers = { "Content-Type": "application/json" };
  }
  let res;
  try {
    res = await fetch(API + path, opts);
  } catch (err) {
    throw new Error(
      "Нет связи с API. Запустите в терминале: uvicorn app.main:app --reload --port 8000"
    );
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

async function withButton(btn, fn) {
  if (!btn) return;
  const prev = btn.disabled;
  btn.disabled = true;
  try {
    await fn();
    showApiError("");
  } catch (e) {
    console.error(e);
    showApiError(e.message || String(e));
    alert("Ошибка: " + (e.message || e));
  } finally {
    btn.disabled = prev;
  }
}

function tfLabel(code) {
  return TF_LABELS[code] || code;
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
  if (status?.symbols?.length) return status.symbols;
  if (meta?.symbols?.length) return meta.symbols;
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
  panel.innerHTML = "";
  const keys = Object.keys(allTf || {});
  if (!keys.length) {
    panel.innerHTML = '<p class="hint">Нет данных — нажми «Загрузить свечи Bybit»</p>';
    return;
  }
  keys.forEach((tf) => {
    const ind = allTf[tf];
    const card = document.createElement("div");
    card.className = "tf-card";
    const title = (labels && labels[tf]) || tfLabel(tf);
    card.innerHTML = `<h4>${title}</h4><dl>
      <dt>Цена</dt><dd>${fmt(ind.close)}</dd>
      <dt>RSI</dt><dd>${fmt(ind.rsi)}</dd>
      <dt>ADX</dt><dd>${fmt(ind.adx)}</dd>
      <dt>EMA</dt><dd>${fmt(ind.ema)}</dd>
      <dt>ATR</dt><dd>${fmt(ind.atr)}</dd>
    </dl>`;
    panel.appendChild(card);
  });
}

function renderTradePlan(plan, signal) {
  const el = $("tradePlan");
  if (!el) return;
  const data =
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

  if (!data || data.action === "HOLD") {
    el.className = "trade-plan empty";
    el.textContent = "Нет сделки — HOLD или риск заблокировал вход";
    return;
  }

  const cls = data.action === "BUY" || data.action === "Buy" ? "buy" : "sell";
  el.className = "trade-plan";
  el.innerHTML = `
    <div class="action ${cls}">${data.action}</div>
    ${data.regime ? `<p class="hint">Режим: ${escapeHtml(data.regime)}</p>` : ""}
    <dl>
      <dt>Уверенность</dt><dd>${data.confidence != null ? (data.confidence * 100).toFixed(0) + "%" : "—"}</dd>
      <dt>Вход</dt><dd>${fmt(data.entry)}</dd>
      <dt>Stop Loss</dt><dd>${fmt(data.stop_loss)}</dd>
      <dt>Take Profit</dt><dd>${fmt(data.take_profit)}</dd>
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
  el.innerHTML = `<strong>${signal.action}</strong> · ${(signal.confidence * 100).toFixed(0)}%<br/>
    <span class="hint">${escapeHtml(signal.reason || "")}</span>`;
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

function renderRisk(events, bot) {
  const el = $("riskBox");
  if (!el || !bot) return;
  const ks = bot.kill_switch
    ? '<p class="risk-block">⚠ Kill switch ВКЛ</p>'
    : '<p class="risk-ok">Kill switch выкл</p>';
  const items = (events || [])
    .slice(0, 5)
    .map((e) => `<li>${escapeHtml(e.message)}</li>`)
    .join("");
  el.innerHTML = ks + `<ul class="audit-list">${items || "<li>Нет событий</li>"}</ul>`;
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
  sel.innerHTML = "";
  (timeframes || ["1", "5", "60"]).forEach((tf, i) => {
    const opt = document.createElement("option");
    opt.value = tf;
    opt.textContent = (labels && labels[tf]) || tfLabel(tf);
    if (i === 1 || tf === "5") opt.selected = true;
    sel.appendChild(opt);
  });
}

function populateSymbols(symbols) {
  const select = $("symbolSelect");
  if (!select) return;
  select.innerHTML = "";
  symbols.forEach((s) => {
    const opt = document.createElement("option");
    opt.value = s;
    opt.textContent = s;
    select.appendChild(opt);
  });
}

let lastTvSymbol = "";
let lastTvInterval = "";

async function loadOverview() {
  const symbol = $("symbolSelect")?.value || "BTCUSDT";
  const timeframe = $("timeframeSelect")?.value || "5";
  const [overview, chartData] = await Promise.all([
    api(`/api/v1/dashboard/overview?symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(timeframe)}`),
    fetchChartData(symbol, timeframe),
  ]);

  updateBotBadges(overview.bot, overview.candle_source || chartData?.candle_source);
  renderIndicators(overview.indicators || chartData?.indicators);
  renderMultiTf(overview.indicators_all_timeframes, overview.bot?.timeframe_labels);
  renderTradePlan(chartData?.trade_plan, overview.signal);
  renderSignal(overview.signal);
  renderDecisionExplanation(overview, chartData);
  renderDecisionJournal(overview.decision_journal, overview.last_cycle_decisions);
  renderRisk(overview.risk_events, overview.bot);
  renderAudit(overview.audit);
  renderLearning(overview.learning);
  renderChanges(overview.market_changes);

  updateChartChrome(chartData, symbol, timeframe);
  renderLevelsChart(chartData, symbol, timeframe);

  const tvKey = `${symbol}:${timeframe}`;
  if (tvKey !== `${lastTvSymbol}:${lastTvInterval}`) {
    lastTvSymbol = symbol;
    lastTvInterval = timeframe;
    loadTradingViewChart(symbol, timeframe, chartData);
  }
}

async function refreshAll() {
  try {
    await loadOverview();
    showApiError("");
  } catch (e) {
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
  if (btnStart) {
    btnStart.addEventListener("click", () =>
      withButton(btnStart, async () => {
        await api("/api/v1/bot/start", { method: "POST" });
        await refreshAll();
      })
    );
  }
  if (btnStop) {
    btnStop.addEventListener("click", () =>
      withButton(btnStop, async () => {
        await api("/api/v1/bot/stop", { method: "POST" });
        await refreshAll();
      })
    );
  }
  if (btnOnce) {
    btnOnce.addEventListener("click", () =>
      withButton(btnOnce, async () => {
        await api("/api/v1/bot/run-once", { method: "POST" });
        await refreshAll();
      })
    );
  }
  if (btnRefreshMarket) {
    btnRefreshMarket.addEventListener("click", () =>
      withButton(btnRefreshMarket, async () => {
        const r = await api("/api/v1/dashboard/refresh-market", { method: "POST" });
        alert(`Свечи загружены для ТФ: ${(r?.timeframes || []).join(", ")}`);
        await refreshAll();
      })
    );
  }
  $("symbolSelect")?.addEventListener("change", () => {
    lastTvSymbol = "";
    lastTvInterval = "";
    lastLevelsKey = "";
    refreshAll();
  });
  $("timeframeSelect")?.addEventListener("change", () => {
    lastTvSymbol = "";
    lastTvInterval = "";
    lastLevelsKey = "";
    refreshAll();
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
  const tfs = normalizeTimeframes(status, meta);
  const labels =
    status.timeframe_labels ||
    Object.fromEntries((meta.timeframes || []).map((t) => [t.code, t.label]));
  populateTimeframes(tfs, labels);

  await refreshAll();

  if (refreshTimer) clearInterval(refreshTimer);
  refreshTimer = setInterval(refreshAll, 15000);
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
