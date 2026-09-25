/** Usage tab — SVG charts from GET /api/usage. */

import { api, esc } from "../api.js";
import { lineChart, barChart } from "../charts/svg_series.js";

function metricsTable(metrics) {
  if (!metrics?.length) return '<p class="muted">No metrics</p>';
  return `<table><thead><tr><th>Agent</th><th>Runs</th><th>Active</th><th>Spend USD</th></tr></thead><tbody>${metrics
    .map((m) => {
      const t = m.totals || {};
      return `<tr><td>${esc(m.agent_id)}</td><td>${esc(t.runs ?? "—")}</td><td>${esc(t.active ?? "—")}</td><td>${esc(m.spend_usd ?? "—")}</td></tr>`;
    })
    .join("")}</tbody></table>`;
}

export function mount(container) {
  container.innerHTML = `
    <section class="panel usage-panel" data-panel="usage">
      <h2>Usage</h2>
      <p class="muted small">Events from hub JSONL + normalized adapter metrics.</p>
      <div class="row usage-filters">
        <label>Bucket <select id="usageBucket"><option value="">none</option><option value="hour">hour</option><option value="day" selected>day</option></select></label>
        <button type="button" id="usageRefresh">Refresh</button>
      </div>
      <div id="usageCharts" class="usage-charts"></div>
      <h2>Metrics</h2>
      <div id="usageMetrics" class="table-wrap"><p class="muted">Loading…</p></div>
      <h2>Recent events</h2>
      <div id="usageEvents" class="table-wrap"><p class="muted">Loading…</p></div>
    </section>`;

  async function load() {
    const bucket = container.querySelector("#usageBucket").value;
    const q = new URLSearchParams();
    if (bucket) q.set("bucket", bucket);
    const data = await api(`/api/usage?${q}`);

    const charts = container.querySelector("#usageCharts");
    const buckets = data.buckets || [];
    if (buckets.length) {
      charts.innerHTML = `
        ${lineChart({
          title: "Events per bucket (total)",
          points: buckets.map((b) => ({ x: b.bucket, y: b.total || 0 })),
        })}
        ${barChart({
          title: "Latest bucket event mix",
          bars: Object.entries(buckets[buckets.length - 1]?.counts || {}).map(([label, value]) => ({
            label,
            value,
          })),
        })}`;
    } else {
      charts.innerHTML = lineChart({ title: "Events", points: [] });
    }

    container.querySelector("#usageMetrics").innerHTML = metricsTable(data.metrics);
    const events = (data.events || []).slice(-30).reverse();
    container.querySelector("#usageEvents").innerHTML = events.length
      ? `<table><thead><tr><th>Time</th><th>Event</th><th>Agent</th><th>Run</th></tr></thead><tbody>${events
          .map(
            (e) =>
              `<tr><td class="muted small">${esc(e.ts)}</td><td>${esc(e.event)}</td><td>${esc(e.agent_id || "")}</td><td>${esc(e.run_id || "")}</td></tr>`
          )
          .join("")}</tbody></table>`
      : '<p class="muted">No events yet — start runs from Agent tab.</p>';
  }

  container.querySelector("#usageRefresh").addEventListener("click", () => {
    load().catch((err) => {
      container.querySelector("#usageMetrics").innerHTML = `<p class="bad">${esc(err.message)}</p>`;
    });
  });
  container.querySelector("#usageBucket").addEventListener("change", () => container.querySelector("#usageRefresh").click());

  load().catch((err) => {
    container.querySelector("#usageMetrics").innerHTML = `<p class="bad">${esc(err.message)}</p>`;
  });
}

export function unmount() {}
