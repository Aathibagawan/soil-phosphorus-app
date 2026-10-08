nav("about.html");
(async () => {
  let m; try { m = await api("/model/info"); } catch (e) { $("#content").innerHTML = `<div class="alert err">${esc(e.message)}</div>`; return; }
  const t = m.metrics.test, r = m.metrics.baseline_ridge, mean = m.metrics.baseline_mean, h = m.hyperparameters, u = esc(m.target_unit);
  const better = t.rmse < r.rmse;
  $("#content").innerHTML = `
  ${m.synthetic_data ? `<div class="alert warn">⚠ This model was trained on <b>synthetic</b> data (${esc(m.data_source)}). Metrics below demonstrate the pipeline, not real-world accuracy.</div>` : ""}
  <section class="card"><h2>Architecture</h2>
    <p>${esc(m.architecture)}. Input: the last <b>${m.window} hourly readings</b> of ${m.features.length} sensors → two Conv1D layers extract local patterns → a bidirectional LSTM models temporal dependencies → additive attention weights the most informative hours → dense layers output phosphorus. Hyper-parameters (filters, LSTM units, learning rate) were found with Particle Swarm Optimisation.</p>
    <div class="stats">
      <div class="stat"><b>${h.cnn_filters}</b><span>CNN filters (PSO)</span></div><div class="stat"><b>${h.lstm_units}</b><span>BiLSTM units (PSO)</span></div>
      <div class="stat"><b>${h.learning_rate.toFixed(5)}</b><span>Learning rate (PSO)</span></div><div class="stat"><b>${h.pso_particles}×${h.pso_iterations}</b><span>PSO particles × iterations</span></div></div>
    <p class="meta">Version ${esc(m.model_version)} · trained ${esc(fdate(m.trained_at))}</p></section>

  <section class="card"><h2>Held-out test performance</h2>
    <p class="meta">${m.metrics.n_test_windows} chronologically later windows, never used for training, tuning or scaling.</p>
    <div class="table-wrap"><table><thead><tr><th>Model</th><th>RMSE (${u})</th><th>MAE (${u})</th><th>R²</th></tr></thead><tbody>
      <tr><td><b>PSO-CNN-BiLSTM-Attention</b></td><td>${fmt(t.rmse, 3)}</td><td>${fmt(t.mae, 3)}</td><td>${fmt(t.r2, 3)}</td></tr>
      <tr><td>Ridge regression (baseline)</td><td>${fmt(r.rmse, 3)}</td><td>${fmt(r.mae, 3)}</td><td>${fmt(r.r2, 3)}</td></tr>
      <tr><td>Always predict the training mean</td><td>${fmt(mean.rmse, 3)}</td><td>${fmt(mean.mae, 3)}</td><td>${fmt(mean.r2, 3)}</td></tr></tbody></table></div>
    ${better ? "" : `<div class="alert info">On this dataset a simple linear baseline performs on par with or better than the deep model — worth knowing before claiming a deep-learning advantage. Real, noisier data is where the architecture should be re-evaluated.</div>`}
    <h2 style="margin-top:18px">Actual vs predicted (test set)</h2>
    ${lineChart([{ name: "Actual", values: m.test_curve.actual, color: "var(--muted)" }, { name: "Predicted", values: m.test_curve.predicted, color: "var(--brand)", dashed: true }])}
  </section>

  <section class="card"><h2>Training loss</h2>
    ${lineChart([{ name: "Train", values: m.loss_curve.train, color: "var(--brand)" }, { name: "Validation", values: m.loss_curve.val, color: "var(--neg)" }], { height: 160 })}</section>

  <section class="card"><h2>Input features & accepted ranges</h2>
    <div class="table-wrap"><table><thead><tr><th>Feature</th><th>Unit</th><th>Accepted</th><th>Seen in training</th></tr></thead><tbody>
    ${m.features.map(f => { const tr = m.train_range[f.key]; return `<tr><td>${esc(f.label)}</td><td>${esc(f.unit)}</td><td>${f.min} – ${f.max}</td><td>${fmt(tr.min, 2)} – ${fmt(tr.max, 2)}</td></tr>`; }).join("")}
    </tbody></table></div>
    <p class="meta">Values outside the accepted range are rejected; values outside the training range are accepted but flagged as unreliable.</p></section>`;
})();
