nav("index.html");
let INFO = null, busy = false;

const errorsBox = $("#errors"), resultBox = $("#result");

function showErrors(e) {
  const items = [...(e.fields || []).map(f => `${f.field ? "<b>" + esc(f.field) + "</b>: " : ""}${esc(f.message)}`), ...(e.details || []).map(esc)];
  errorsBox.innerHTML = `<div class="alert err" role="alert">${esc(e.message)}${items.length ? "<ul>" + items.map(i => `<li>${i}</li>`).join("") + "</ul>" : ""}</div>`;
  document.querySelectorAll("#fields input").forEach(i => i.classList.remove("bad"));
  (e.fields || []).forEach(f => {
    const key = (f.field || "").split(".").pop(), inp = $(`#f-${key}`);
    if (inp) { inp.classList.add("bad"); $(`#e-${key}`).textContent = f.message; }
  });
}
const clearErrors = () => { errorsBox.innerHTML = ""; document.querySelectorAll(".fe").forEach(e => e.textContent = ""); document.querySelectorAll("#fields input").forEach(i => i.classList.remove("bad")); };

function buildForm() {
  $("#fields").innerHTML = INFO.features.map(f => `
    <div><label for="f-${f.key}">${esc(f.label)} <small>(${esc(f.unit)})</small></label>
    <input type="number" id="f-${f.key}" name="${f.key}" step="any" min="${f.min}" max="${f.max}" required inputmode="decimal">
    <div class="fe" id="e-${f.key}"></div></div>`).join("");
  $("#single-note").textContent = `The model reads a ${INFO.window}-hour history. With one reading, it is repeated across the whole window (steady-state assumption) — use the time-series tab for best accuracy.`;
  $("#csv-note").innerHTML = `Upload at least <b>${INFO.window} hourly rows</b> (oldest first; the latest ${INFO.window} are used). Columns: ${INFO.features.map(f => `<code>${f.key}</code>`).join(", ")}. Extra columns (timestamp, phosphorus) are ignored.`;
  fillDefaults();
}
function fillDefaults() { INFO.features.forEach(f => $(`#f-${f.key}`).value = f.default); }

function setBusy(b) { busy = b; document.querySelectorAll(".btn").forEach(x => x.disabled = b); }

async function submit(fn) {
  if (busy) return; clearErrors(); setBusy(true);
  try { render(await fn()); }
  catch (e) { showErrors(e instanceof ApiError ? e : new ApiError(String(e))); resultBox.classList.add("hidden"); }
  finally { setBusy(false); }
}

function render(r) {
  const actual = r._actual;
  const eff = r.feature_effects.map(e => ({ label: e.label, value: e.effect }));
  resultBox.classList.remove("hidden");
  resultBox.innerHTML = `
    <h2>Result</h2>
    <div class="big">${fmt(r.prediction, 2)} <small>${esc(r.unit)}</small></div>
    <div class="meta">${r.input_mode === "single_reading" ? "Single reading" : r.window + "-hour time series"} · model ${esc(r.model_version)} · ${r.latency_ms} ms · <a href="history.html">saved to history</a></div>
    ${actual != null ? `<div class="alert info">True value for this held-out window: <b>${fmt(actual, 2)} ${esc(r.unit)}</b> (error ${fmt(Math.abs(actual - r.prediction), 2)})</div>` : ""}
    ${r.warnings.map(w => `<div class="alert warn">⚠ ${esc(w)}</div>`).join("")}
    <div class="two" style="margin-top:14px">
      <div><h2>What the model attended to</h2>
        ${barChart(r.attention, { labelFirst: `${r.window}h ago`, labelLast: "now" })}
        <p class="meta">Attention weight per hour of the input window. Taller bars = hours that influenced this prediction more.</p></div>
      <div><h2>Feature sensitivity</h2>
        ${divergingBars(eff, r.unit)}
        <p class="meta">Change in the prediction (${esc(r.unit)}) versus setting that feature to its training average. An approximation — correlated features share credit.</p></div>
    </div>`;
  resultBox.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function selectTab(single) {
  $("#single").classList.toggle("hidden", !single); $("#csvpane").classList.toggle("hidden", single);
  $("#tab-single").setAttribute("aria-selected", single); $("#tab-csv").setAttribute("aria-selected", !single); clearErrors();
}

async function init() {
  try { INFO = await api("/model/info"); }
  catch (e) { $("#banner").innerHTML = `<div class="alert err">${esc(e.message)}</div>`; return; }
  if (INFO.synthetic_data) $("#banner").innerHTML = `<div class="alert warn">⚠ Demo model trained on <b>synthetic</b> data — predictions are illustrative only.</div>`;
  buildForm();

  $("#tab-single").onclick = () => selectTab(true); $("#tab-csv").onclick = () => selectTab(false);
  $("#fill-defaults").onclick = fillDefaults;

  $("#single").addEventListener("submit", ev => {
    ev.preventDefault();
    const reading = {}; let bad = false;
    INFO.features.forEach(f => { const v = $(`#f-${f.key}`).value; if (v === "" || isNaN(+v)) { bad = true; $(`#f-${f.key}`).classList.add("bad"); $(`#e-${f.key}`).textContent = "Required number"; } reading[f.key] = +v; });
    if (bad) return showErrors(new ApiError("Please fill in every field with a number."));
    submit(() => api("/predict", { method: "POST", json: { reading, label: $("#label1").value || null } }));
  });

  $("#csv-go").onclick = () => {
    const f = $("#file").files[0]; if (!f) return showErrors(new ApiError("Choose a CSV file first."));
    const fd = new FormData(); fd.append("file", f); if ($("#label2").value) fd.append("label", $("#label2").value);
    submit(() => api("/predict/csv", { method: "POST", form: fd }));
  };
  $("#sample-go").onclick = () => submit(async () => {
    const s = await api("/model/sample");
    const window = s.window.map(row => Object.fromEntries(s.keys.map((k, i) => [k, row[i]])));
    const r = await api("/predict", { method: "POST", json: { window, label: "Example window" } });
    r._actual = s.actual_next; return r;
  });

  $("#tpl").onclick = () => {
    const head = INFO.features.map(f => f.key).join(",");
    const rows = Array.from({ length: INFO.window }, () => INFO.features.map(f => f.default).join(","));
    const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([[head, ...rows].join("\n")], { type: "text/csv" }));
    a.download = "soil_window_template.csv"; a.click(); URL.revokeObjectURL(a.href);
  };
  const drop = $("#drop");
  ["dragover", "dragenter"].forEach(t => drop.addEventListener(t, e => { e.preventDefault(); drop.classList.add("over"); }));
  ["dragleave", "drop"].forEach(t => drop.addEventListener(t, e => { e.preventDefault(); drop.classList.remove("over"); }));
  drop.addEventListener("drop", e => { if (e.dataTransfer.files.length) $("#file").files = e.dataTransfer.files; });
}
init();
