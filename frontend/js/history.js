nav("history.html");
const LIMIT = 10; let offset = 0, total = 0;

async function load() {
  try {
    const [page, st] = await Promise.all([api(`/history?limit=${LIMIT}&offset=${offset}`), api("/history/stats")]);
    total = page.total;
    $("#stats").innerHTML = [["Predictions", st.count], ["Mean", st.mean == null ? "–" : fmt(st.mean) + " " + st.unit],
      ["Min", st.min == null ? "–" : fmt(st.min)], ["Max", st.max == null ? "–" : fmt(st.max)]]
      .map(([k, v]) => `<div class="stat"><b>${esc(v)}</b><span>${k}</span></div>`).join("");
    $("#trend").innerHTML = st.series.length
      ? `<h2>Recent predictions (${esc(st.unit)})</h2>` + lineChart([{ name: "Prediction", values: st.series.map(s => s.prediction), color: "var(--brand)" }],
          { labels: [fdate(st.series[0].created_at), fdate(st.series.at(-1).created_at)] }) : "";
    $("#rows").innerHTML = page.items.length ? page.items.map(r => `
      <tr><td>${r.id}</td><td>${esc(fdate(r.created_at))}</td><td>${esc(r.label || "–")}</td>
      <td>${r.input_mode === "single_reading" ? '<span class="pill warn">single</span>' : '<span class="pill">' + r.rows_used + "h series</span>"}
          <div class="meta">pH ${fmt(r.inputs.mean?.ph, 2)} · soil ${fmt(r.inputs.mean?.soil_temperature, 1)}°C · hum ${fmt(r.inputs.mean?.soil_humidity, 1)}%</div></td>
      <td><b>${fmt(r.prediction)}</b> ${esc(r.unit)}</td>
      <td class="meta">${r.warnings.length ? r.warnings.length + " warning" + (r.warnings.length > 1 ? "s" : "") : "–"}</td>
      <td><button class="btn danger" data-del="${r.id}" aria-label="Delete prediction ${r.id}">✕</button></td></tr>`).join("")
      : `<tr><td colspan="7" class="meta">No predictions yet. <a href="index.html">Make your first one →</a></td></tr>`;
    $("#pageinfo").textContent = total ? `${offset + 1}–${Math.min(offset + LIMIT, total)} of ${total}` : "";
    $("#prev").disabled = offset === 0; $("#next").disabled = offset + LIMIT >= total;
    $("#msg").innerHTML = "";
  } catch (e) { $("#msg").innerHTML = `<div class="alert err">${esc(e.message)}</div>`; }
}

$("#prev").onclick = () => { offset = Math.max(0, offset - LIMIT); load(); };
$("#next").onclick = () => { offset += LIMIT; load(); };
$("#rows").addEventListener("click", async e => {
  const id = e.target.dataset?.del; if (!id) return;
  await api(`/history/${id}`, { method: "DELETE" }); if (offset >= total - 1 && offset > 0) offset -= LIMIT; toast("Deleted"); load();
});
$("#clear").onclick = async () => { if (!confirm("Delete all your saved predictions?")) return; await api("/history", { method: "DELETE" }); offset = 0; toast("History cleared"); load(); };
$("#export").onclick = async () => {
  const res = await api("/history/export.csv", { raw: true }), blob = await res.blob();
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "phosphorus_predictions.csv"; a.click(); URL.revokeObjectURL(a.href);
};
load();
