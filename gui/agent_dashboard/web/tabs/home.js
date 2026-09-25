/** Home tab — snapshot cards; poll only when #/home (G8). */

import { api, esc } from "../api.js";
import { registerPoller, unregisterPoller } from "../poll.js";

const POLL_ID = "home-snapshot";
let mounted = false;

function fmtTime(ts) {
  if (!ts) return "—";
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return String(ts);
  }
}

function renderCards(data) {
  const agents = data.agents || [];
  const runs = data.recent_runs || [];
  const events = data.recent_usage_events || [];

  const agentCards = agents
    .map(
      (a) => `
    <article class="home-card">
      <h3>${esc(a.name || a.id)}</h3>
      <p class="muted small">${esc(a.description || "")}</p>
      <p class="pill ${a.online ? "ok" : "bad"}">${a.online ? "online" : "offline"}</p>
    </article>`
    )
    .join("");

  const runRows = runs
    .map(
      (r) =>
        `<tr><td>${esc(r.agent_id)}</td><td>${esc(String(r.run_id || "").slice(0, 12))}</td><td>${esc(r.status)}</td><td class="muted small">${esc(fmtTime(r.updated_at))}</td></tr>`
    )
    .join("");

  const eventRows = events
    .slice(-10)
    .reverse()
    .map(
      (e) =>
        `<tr><td class="muted small">${esc(fmtTime(e.ts))}</td><td>${esc(e.event)}</td><td>${esc(e.agent_id || "")}</td></tr>`
    )
    .join("");

  return `
    <section class="panel" data-panel="home">
      <div class="home-header">
        <h2>Overview</h2>
        <p class="muted small" id="homeGenerated">Snapshot ${fmtTime(data.generated_at ? data.generated_at * 1000 : null)}</p>
      </div>
      <div class="home-agent-grid">${agentCards || '<p class="muted">No agents</p>'}</div>
      <div class="split home-split">
        <div>
          <h2>Recent runs</h2>
          <div class="table-wrap">
            <table><thead><tr><th>Agent</th><th>Run</th><th>Status</th><th>Updated</th></tr></thead>
            <tbody>${runRows || '<tr><td colspan="4" class="muted">None</td></tr>'}</tbody></table>
          </div>
        </div>
        <div>
          <h2>Usage events</h2>
          <div class="table-wrap">
            <table><thead><tr><th>Time</th><th>Event</th><th>Agent</th></tr></thead>
            <tbody>${eventRows || '<tr><td colspan="3" class="muted">None</td></tr>'}</tbody></table>
          </div>
        </div>
      </div>
    </section>`;
}

async function refreshSnapshot(container) {
  try {
    const data = await api("/api/home/snapshot");
    container.innerHTML = renderCards(data);
  } catch (err) {
    container.innerHTML = `<section class="panel"><p class="bad">${esc(err.message)}</p></section>`;
  }
}

export function mount(container) {
  mounted = true;
  container.innerHTML = '<section class="panel"><p class="muted">Loading snapshot…</p></section>';
  refreshSnapshot(container);
  registerPoller(POLL_ID, {
    tab: "home",
    fn: () => refreshSnapshot(container),
  });
}

export function unmount() {
  mounted = false;
  unregisterPoller(POLL_ID);
}
