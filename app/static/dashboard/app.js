const API = "";

const TF_LABELS = {
  "1": "1m", "3": "3m", "5": "5m", "15": "15m", "30": "30m",
  "60": "1h", "240": "4h", "D": "1D", "W": "1W", "M": "1MN",
};

let refreshTimer = null;
let ratioTimer = null;
let tvChartKey = "";

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
  const inner = document.createElement("div");
  inner.className = "tradingview-widget-container__widget";
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
  let msg = `TradingView · ${symbol} · ${tfLabel(timeframe)}`;
  if (levels.length) {
    msg += ` · Entry/SL/TP в панели (${src})`;
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

  updateTradeLevelsPanel(chartData);

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

async function fetchChartData(symbol, timeframe) {
  return api(
    `/api/v1/dashboard/chart?symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(timeframe)}`
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
  const biasClass = { bullish: "bias-up", bearish: "bias-down", neutral: "bias-flat" };

  const tfRows = (b.timeframes || [])
    .map((row) => {
      const cls = biasClass[row.bias] || "bias-flat";
      const biasLabel =
        { bullish: "Бычий", bearish: "Медвежий", neutral: "Нейтральный" }[row.bias] || row.bias;
      return `<tr class="${cls}">
        <td>${escapeHtml(row.label)}</td>
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
          <dt>Вход</dt><dd>${fmt(trade.entry)}</dd>
          <dt>Stop Loss</dt><dd>${fmt(trade.stop_loss)} <span class="hint">(${trade.risk_pct_signed ?? trade.risk_pct ?? "—"}%)</span></dd>
          <dt>Take Profit</dt><dd>${fmt(trade.take_profit)} <span class="hint">(+${trade.reward_pct_signed ?? trade.reward_pct ?? "—"}%)</span></dd>
          ${trade.risk_reward ? `<dt>R:R</dt><dd>${Number(trade.risk_reward).toFixed(2)}</dd>` : ""}
        </dl>
      </div>`;
  } else {
    planHtml = '<p class="brief-hold">Сейчас без входа — бот ждёт согласованности по таймфреймам или лучшей точки.</p>';
  }

  el.innerHTML = `
    <p class="brief-headline">${escapeHtml(b.headline || "")}</p>
    <p class="hint">${escapeHtml(b.mtf_summary || "")}</p>
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

async function loadOverview() {
  const symbol = $("symbolSelect")?.value || "BTCUSDT";
  const timeframe = $("timeframeSelect")?.value || "5";
  const [overview, chartData] = await Promise.all([
    api(
      `/api/v1/dashboard/overview?symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(timeframe)}&include_ratios=false`
    ),
    fetchChartData(symbol, timeframe),
  ]);

  updateBotBadges(overview.bot, overview.candle_source || chartData?.candle_source);
  renderIndicators(overview.indicators || chartData?.indicators);
  renderMultiTf(overview.indicators_all_timeframes, overview.bot?.timeframe_labels);
  renderTradePlan(chartData?.trade_plan, overview.signal);
  renderSignal(overview.signal);
  renderTraderBriefing(overview.trader_briefing, overview);
  renderDecisionExplanation(overview, chartData);
  renderDecisionJournal(overview.decision_journal, overview.last_cycle_decisions);
  renderRisk(overview.risk_events, overview.bot);
  renderAudit(overview.audit);
  renderLearning(overview.learning);
  renderChanges(overview.market_changes);

  updateChartChrome(chartData, symbol, timeframe);
  renderMainChart(chartData, symbol, timeframe);
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
  const btnRatioScan = $("btnRatioScan");
  const btnRefreshMarketFull = $("btnRefreshMarketFull");

  if (btnStart) {
    btnStart.addEventListener("click", () =>
      withButton(btnStart, async () => {
        await api("/api/v1/bot/start", { method: "POST" });
        setStatusHint("Бот запущен в фоне");
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
  $("symbolSelect")?.addEventListener("change", () => {
    lastChartKey = "";
    refreshAll();
  });
  $("timeframeSelect")?.addEventListener("change", () => {
    lastChartKey = "";
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
  loadRatioSection();

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
