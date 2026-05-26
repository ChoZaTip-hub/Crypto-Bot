const API = "";

const TF_LABELS = {
  "1": "1m", "3": "3m", "5": "5m", "15": "15m", "30": "30m",
  "60": "1h", "240": "4h", "D": "1D", "W": "1W", "M": "1MN",
};

let tvWidgetNonce = 0;

async function api(path, options = {}) {
  const res = await fetch(API + path, options);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = await res.json();
      detail = j.detail || JSON.stringify(j);
    } catch {
      detail = await res.text();
    }
    throw new Error(detail);
  }
  return res.json();
}

function $(id) {
  return document.getElementById(id);
}

function tfLabel(code) {
  return TF_LABELS[code] || code;
}

function symbolToTradingView(sym) {
  const s = (sym || "BTCUSDT").toUpperCase();
  return s.includes(":") ? s : `BYBIT:${s}`;
}

function loadTradingViewChart(symbol, interval) {
  const wrap = $("tvChartContainer");
  if (!wrap) return;
  tvWidgetNonce += 1;
  const nonce = tvWidgetNonce;
  wrap.innerHTML = `
    <div class="tradingview-widget-container__widget" style="height:100%;width:100%"></div>
    <div class="tradingview-widget-copyright">
      <a href="https://www.tradingview.com/" rel="noopener nofollow" target="_blank">
        <span class="blue-text">TradingView</span>
      </a>
    </div>`;

  const script = document.createElement("script");
  script.type = "text/javascript";
  script.src = "https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js";
  script.async = true;
  script.innerHTML = JSON.stringify({
    allow_symbol_change: false,
    calendar: false,
    details: false,
    hide_side_toolbar: true,
    hide_top_toolbar: false,
    hide_legend: false,
    hide_volume: false,
    hotlist: false,
    interval: interval || "5",
    locale: "en",
    save_image: true,
    style: "1",
    symbol: symbolToTradingView(symbol),
    theme: "dark",
    timezone: "Etc/UTC",
    backgroundColor: "#0F0F0F",
    gridColor: "rgba(242, 242, 242, 0.06)",
    watchlist: [],
    withdateranges: true,
    compareSymbols: [],
    studies: ["RSI@tv-basicstudies", "MASimple@tv-basicstudies"],
    autosize: true,
  });
  script.onload = () => {
    if (nonce !== tvWidgetNonce) script.remove();
  };
  wrap.appendChild(script);
}

function renderIndicators(indicators) {
  const row = $("indicatorRow");
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
  const data = plan || (signal && signal.action !== "HOLD" ? {
    action: signal.action,
    entry: signal.entry_price,
    stop_loss: signal.stop_loss,
    take_profit: signal.take_profit,
    confidence: signal.confidence,
    reason: signal.reason,
  } : null);

  if (!data || data.action === "HOLD") {
    el.className = "trade-plan empty";
    el.textContent = "Нет сделки — HOLD или риск заблокировал вход";
    return;
  }

  const cls = data.action === "BUY" ? "buy" : "sell";
  el.className = "trade-plan";
  el.innerHTML = `
    <div class="action ${cls}">${data.action}</div>
    <dl>
      <dt>Уверенность</dt><dd>${(data.confidence * 100).toFixed(0)}%</dd>
      <dt>Вход</dt><dd>${fmt(data.entry)}</dd>
      <dt>Stop Loss</dt><dd>${fmt(data.stop_loss)}</dd>
      <dt>Take Profit</dt><dd>${fmt(data.take_profit)}</dd>
    </dl>
    <div class="reason">${escapeHtml(data.reason || "")}</div>
  `;
}

function renderSignal(signal) {
  const el = $("signalBox");
  if (!signal) {
    el.textContent = "Сигналов пока нет";
    return;
  }
  el.innerHTML = `<strong>${signal.action}</strong> · ${(signal.confidence * 100).toFixed(0)}%<br/>
    <span class="hint">${escapeHtml(signal.reason || "")}</span>`;
}

function renderRisk(events, bot) {
  const el = $("riskBox");
  const ks = bot.kill_switch ? '<p class="risk-block">⚠ Kill switch ВКЛ</p>' : '<p class="risk-ok">Kill switch выкл</p>';
  const items = (events || []).slice(0, 5).map((e) => `<li>${escapeHtml(e.message)}</li>`).join("");
  el.innerHTML = ks + `<ul class="audit-list">${items || "<li>Нет событий</li>"}</ul>`;
}

function renderLearning(learning) {
  const el = $("learningBox");
  if (!learning) {
    el.textContent = "Нет данных обучения";
    return;
  }
  const wr = ((learning.win_rate || 0) * 100).toFixed(0);
  el.innerHTML = `
    <p>Исходов: <strong>${learning.total_outcomes || 0}</strong> · Win rate: <strong>${wr}%</strong></p>
    <p class="hint">W: ${learning.wins || 0} / L: ${learning.losses || 0}</p>
    <ul class="audit-list">
      ${(learning.recent || []).slice(0, 5).map((o) =>
        `<li>${o.symbol} ${o.outcome} ${o.pnl_pct?.toFixed(2)}% (${o.exit_reason})</li>`
      ).join("") || "<li>Пока нет закрытых сделок</li>"}
    </ul>`;
}

function renderChanges(changes) {
  const ul = $("changesList");
  ul.innerHTML = "";
  (changes || []).forEach((c) => {
    const li = document.createElement("li");
    li.innerHTML = `<span class="meta">${c.severity} · ${c.timeframe || ""}</span>
      <strong>${escapeHtml(c.change_type)}</strong> — ${escapeHtml(c.message || "")}`;
    ul.appendChild(li);
  });
  if (!changes?.length) {
    ul.innerHTML = "<li class='hint'>Изменения появятся после циклов бота (память снапшотов)</li>";
  }
}

function renderNews(news) {
  const ul = $("newsList");
  ul.innerHTML = "";
  (news || []).forEach((n) => {
    const li = document.createElement("li");
    const link = n.url ? `<a href="${n.url}" target="_blank">${escapeHtml(n.title)}</a>` : escapeHtml(n.title);
    li.innerHTML = `<div class="meta">${escapeHtml(n.source)} · ${n.published_at || ""}</div>${link}
      <div class="hint">${escapeHtml((n.summary || "").slice(0, 120))}</div>`;
    ul.appendChild(li);
  });
}

function renderAudit(audit) {
  const ul = $("auditList");
  ul.innerHTML = "";
  (audit || []).forEach((a) => {
    const li = document.createElement("li");
    li.innerHTML = `<span class="meta">${a.created_at || ""}</span> · <strong>${a.event_type}</strong>`;
    ul.appendChild(li);
  });
}

function updateBotBadges(bot, candleSource) {
  const st = $("botStatus");
  st.textContent = bot.running ? "Работает" : "Остановлен";
  st.className = "badge " + (bot.running ? "on" : "off");
  const mode = $("modeBadge");
  mode.textContent = bot.trading_mode.toUpperCase();
  mode.className = "badge " + (bot.live_enabled ? "live" : "");
  $("marketBadge").textContent =
    bot.market_source === "bybit"
      ? `Bybit · ${candleSource || "data"}`
      : "Mock data";

  const bg = bot.background || {};
  const newsBadge = $("newsBadge");
  if (bg.running) {
    newsBadge.textContent = bg.last_news_at ? "News 24/7 ✓" : "News 24/7 …";
    newsBadge.className = "badge on";
  } else {
    newsBadge.textContent = "News off";
    newsBadge.className = "badge muted";
  }

  $("lastRun").textContent = bot.last_run_at
    ? `Последний цикл: ${bot.last_run_at}${bot.last_error ? " · Ошибка: " + bot.last_error : ""}`
    : "";

  const bgEl = $("backgroundStatus");
  if (bgEl && bg.running) {
    bgEl.textContent = `Фон: новости каждые ${bg.news_interval_seconds}s · позиции каждые ${bg.position_interval_seconds}s · последние новости: ${bg.last_news_at || "—"}`;
  }
}

function populateTimeframes(timeframes, labels) {
  const sel = $("timeframeSelect");
  sel.innerHTML = "";
  (timeframes || ["1", "5", "60"]).forEach((tf, i) => {
    const opt = document.createElement("option");
    opt.value = tf;
    opt.textContent = (labels && labels[tf]) || tfLabel(tf);
    if (i === 1 || tf === "5") opt.selected = true;
    sel.appendChild(opt);
  });
}

let lastTvSymbol = "";
let lastTvInterval = "";

async function loadOverview() {
  const symbol = $("symbolSelect").value;
  const timeframe = $("timeframeSelect").value;
  const [overview, chartData] = await Promise.all([
    api(`/api/v1/dashboard/overview?symbol=${symbol}&timeframe=${timeframe}`),
    api(`/api/v1/dashboard/chart?symbol=${symbol}&timeframe=${timeframe}`),
  ]);

  updateBotBadges(overview.bot, overview.candle_source || chartData.candle_source);
  renderIndicators(overview.indicators);
  renderMultiTf(overview.indicators_all_timeframes, overview.bot.timeframe_labels);
  renderTradePlan(chartData.trade_plan, overview.signal);
  renderSignal(overview.signal);
  renderRisk(overview.risk_events, overview.bot);
  renderNews(overview.news);
  renderAudit(overview.audit);
  renderLearning(overview.learning);
  renderChanges(overview.market_changes);

  const tv = overview.tradingview || { symbol: symbolToTradingView(symbol), interval: timeframe };
  if (tv.symbol !== lastTvSymbol || tv.interval !== lastTvInterval) {
    lastTvSymbol = tv.symbol;
    lastTvInterval = tv.interval;
    loadTradingViewChart(symbol, timeframe);
  }
}

async function refreshAll() {
  try {
    await loadOverview();
  } catch (e) {
    console.error(e);
    alert("Ошибка загрузки: " + e.message);
  }
}

function fmt(v) {
  return v == null || Number.isNaN(Number(v)) ? "—" : Number(v).toFixed(2);
}

function escapeHtml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

async function init() {
  const [status, meta] = await Promise.all([
    api("/api/v1/bot/status"),
    api("/api/v1/dashboard/meta"),
  ]);

  const select = $("symbolSelect");
  (status.symbols || meta.symbols || ["BTCUSDT"]).forEach((s) => {
    const opt = document.createElement("option");
    opt.value = s;
    opt.textContent = s;
    select.appendChild(opt);
  });

  const tfs = status.timeframes || meta.timeframes.map((t) => t.code);
  const labels = status.timeframe_labels || Object.fromEntries(
    (meta.timeframes || []).map((t) => [t.code, t.label])
  );
  populateTimeframes(tfs, labels);

  loadTradingViewChart(select.value, $("timeframeSelect").value);

  $("symbolSelect").addEventListener("change", () => {
    lastTvSymbol = "";
    refreshAll();
  });
  $("timeframeSelect").addEventListener("change", () => {
    lastTvInterval = "";
    refreshAll();
  });

  $("btnStart").onclick = async () => {
    await api("/api/v1/bot/start", { method: "POST" });
    await refreshAll();
  };
  $("btnStop").onclick = async () => {
    await api("/api/v1/bot/stop", { method: "POST" });
    await refreshAll();
  };
  $("btnOnce").onclick = async () => {
    $("btnOnce").disabled = true;
    try {
      await api("/api/v1/bot/run-once", { method: "POST" });
      await refreshAll();
    } finally {
      $("btnOnce").disabled = false;
    }
  };
  $("btnRefreshMarket").onclick = async () => {
    $("btnRefreshMarket").disabled = true;
    try {
      const r = await api("/api/v1/dashboard/refresh-market", { method: "POST" });
      alert(`Свечи загружены для ТФ: ${(r.timeframes || []).join(", ")}`);
      await refreshAll();
    } finally {
      $("btnRefreshMarket").disabled = false;
    }
  };
  $("btnRefreshNews").onclick = async () => {
    await api("/api/v1/dashboard/refresh-news", { method: "POST" });
    await refreshAll();
  };

  await refreshAll();
  setInterval(refreshAll, 15000);
}

init();
