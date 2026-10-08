/* Shared helpers: anonymous client id, API wrapper, tiny SVG charts. */
const $ = (s, el = document) => el.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function clientId() {
  let id = null;
  try { id = localStorage.getItem("soilp_client"); } catch (_) {}
  if (!id) {
    const rnd = crypto.getRandomValues(new Uint8Array(16));
    id = Array.from(rnd, b => b.toString(16).padStart(2, "0")).join("");
    try { localStorage.setItem("soilp_client", id); } catch (_) {}
  }
  return id;
}

class ApiError extends Error {
  constructor(message, fields = [], details = []) { super(message); this.fields = fields; this.details = details; }
}

async function api(path, { method = "GET", json, form, raw } = {}) {
  const headers = { "X-Client-Id": clientId() };
  let body;
  if (json !== undefined) { headers["Content-Type"] = "application/json"; body = JSON.stringify(json); }
  if (form) body = form;
  let res;
  try { res = await fetch("/api" + path, { method, headers, body }); }
  catch (_) { throw new ApiError("Cannot reach the server. Check your connection."); }
  if (res.status === 204) return null;
  if (raw && res.ok) return res;
  let data = null;
  try { data = await res.json(); } catch (_) {}
  if (!res.ok) {
    if (data && data.error === "validation_error") throw new ApiError("Please fix the highlighted inputs.", data.detail);
    const d = data && data.detail;
    if (d && typeof d === "object" && !Array.isArray(d)) throw new ApiError(d.message || "Request failed", [], d.details || []);
    throw new ApiError(typeof d === "string" ? d : `Request failed (${res.status})`);
  }
  return data;
}

function toast(msg) {
  let t = $("#toast"); if (!t) { t = document.createElement("div"); t.id = "toast"; document.body.append(t); }
  t.textContent = msg; t.classList.add("show"); setTimeout(() => t.classList.remove("show"), 2200);
}

function nav(active) {
  const links = [["index.html", "Predict"], ["history.html", "History"], ["about.html", "About model"], ["/docs", "API docs"]];
  document.body.insertAdjacentHTML("afterbegin",
    `<header class="top"><div class="in"><a class="logo" href="index.html">🌱 Soil Phosphorus Predictor</a><nav>` +
    links.map(([h, t]) => `<a href="${h}" class="${h === active ? "active" : ""}">${t}</a>`).join("") + `</nav></div></header>`);
}

const fmt = (v, d = 2) => (v == null ? "–" : Number(v).toLocaleString(undefined, { maximumFractionDigits: d, minimumFractionDigits: d }));
const fdate = iso => new Date(iso).toLocaleString();

/* ---------- charts (inline SVG, no libraries) ---------- */
function barChart(values, { height = 140, labelFirst = "", labelLast = "", color = "var(--brand)" } = {}) {
  const W = 600, pad = 22, n = values.length, max = Math.max(...values) || 1, bw = (W - 2 * pad) / n;
  const bars = values.map((v, i) => {
    const h = (v / max) * (height - 40);
    return `<rect x="${pad + i * bw + 0.5}" y="${height - 22 - h}" width="${Math.max(bw - 1, 1)}" height="${h}" rx="1.5" fill="${color}"><title>${labelFirst ? "" : ""}${(v * 100).toFixed(2)}%</title></rect>`;
  }).join("");
  return `<svg viewBox="0 0 ${W} ${height}" width="100%" role="img">${bars}
    <text x="${pad}" y="${height - 6}">${esc(labelFirst)}</text><text x="${W - pad}" y="${height - 6}" text-anchor="end">${esc(labelLast)}</text></svg>`;
}

function divergingBars(items, unit) {            // [{label, value}]
  const max = Math.max(...items.map(i => Math.abs(i.value)), 1e-9), W = 600, rowH = 26, mid = 340;
  const rows = items.map((it, i) => {
    const w = (Math.abs(it.value) / max) * 190, y = i * rowH + 4, pos = it.value >= 0;
    const x = pos ? mid : mid - w;
    return `<text x="0" y="${y + 14}">${esc(it.label)}</text>
      <rect x="${x}" y="${y}" width="${Math.max(w, 1)}" height="16" rx="3" fill="${pos ? "var(--pos)" : "var(--neg)"}"/>
      <text x="${pos ? mid + w + 6 : mid - w - 6}" y="${y + 13}" text-anchor="${pos ? "start" : "end"}">${(it.value >= 0 ? "+" : "") + it.value.toFixed(3)}</text>`;
  }).join("");
  return `<svg viewBox="0 0 ${W} ${items.length * rowH + 8}" width="100%" role="img">
    <line x1="${mid}" x2="${mid}" y1="0" y2="${items.length * rowH + 4}" stroke="var(--line)"/>${rows}</svg>`;
}

function lineChart(series, { height = 180, unit = "", labels = [] } = {}) {  // series: [{name, values, color, dashed}]
  const W = 600, L = 46, R = 10, T = 10, B = 24, all = series.flatMap(s => s.values);
  let lo = Math.min(...all), hi = Math.max(...all); if (hi === lo) { hi += 1; lo -= 1; }
  const padv = (hi - lo) * 0.08; lo -= padv; hi += padv;
  const n = Math.max(...series.map(s => s.values.length));
  const X = i => L + (n === 1 ? (W - L - R) / 2 : (i / (n - 1)) * (W - L - R)), Y = v => T + (1 - (v - lo) / (hi - lo)) * (height - T - B);
  const grid = [0, .5, 1].map(t => { const v = lo + t * (hi - lo), y = Y(v);
    return `<line x1="${L}" x2="${W - R}" y1="${y}" y2="${y}" stroke="var(--line)"/><text x="${L - 6}" y="${y + 4}" text-anchor="end">${v.toFixed(2)}</text>`; }).join("");
  const paths = series.map(s => {
    if (s.values.length === 1) return `<circle cx="${X(0)}" cy="${Y(s.values[0])}" r="4" fill="${s.color}"/>`;
    return `<path d="${s.values.map((v, i) => (i ? "L" : "M") + X(i).toFixed(1) + " " + Y(v).toFixed(1)).join("")}" fill="none" stroke="${s.color}" stroke-width="2" ${s.dashed ? 'stroke-dasharray="5 4"' : ""}/>`;
  }).join("");
  const legend = series.length > 1 ? series.map((s, i) => `<text x="${L + i * 110}" y="${height - 4}" fill="${s.color}" style="fill:${s.color}">● ${esc(s.name)}</text>`).join("") : "";
  const xl = labels.length ? `<text x="${L}" y="${height - 4}">${esc(labels[0])}</text><text x="${W - R}" y="${height - 4}" text-anchor="end">${esc(labels[1] || "")}</text>` : "";
  return `<svg viewBox="0 0 ${W} ${height}" width="100%" role="img">${grid}${paths}${legend || xl}</svg>`;
}
