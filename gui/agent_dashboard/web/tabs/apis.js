/** APIs & abilities — Setup (runtimes/keys) + agent connections + OpenAPI + overlay. */

import { api, esc } from "../api.js";
import { fetchAgents, stateLabel, ensureBackend, backendAction } from "../agents.js";
import * as session from "../state.js";

function renderRoutes(openapi) {
  const paths = openapi.paths || {};
  const rows = Object.keys(paths)
    .sort()
    .flatMap((path) =>
      Object.keys(paths[path]).map((method) => {
        const op = paths[path][method];
        return `<tr><td><code>${esc(method.toUpperCase())}</code></td><td><code>${esc(path)}</code></td><td class="muted small">${esc(op.summary || "")}</td></tr>`;
      })
    );
  return rows.join("");
}

function overlayForm(overlay) {
  const o = overlay || {};
  let val = o.workspace_roots;
  if (Array.isArray(val)) val = JSON.stringify(val, null, 2);
  return `<label class="overlay-field overlay-field-wide"><span>workspace_roots (JSON array)</span>
    <textarea data-key="workspace_roots" rows="4" placeholder='["../some-repo"]'>${esc(val || "")}</textarea></label>
    <p class="muted small">host / port / auth_required are not overlayable — edit <code>config/agents.json</code> and restart.</p>`;
}

function renderAgentConnections(agents) {
  if (!agents.length) {
    return `<p class="muted">No agents registered.</p>`;
  }
  return agents
    .map((a) => {
      const b = a.backend || {};
      const caps = Array.isArray(a.capabilities) ? a.capabilities : [];
      const state = b.state || (a.online ? "ready" : "down");
      const label = stateLabel(b) || state;
      const startable = b.startable === true;
      const msg = b.message || (a.online ? "Connected" : "Offline");
      const base = b.base_url ? `<div class="muted small">URL: <code>${esc(b.base_url)}</code></div>` : "";
      const capsHtml = caps.length
        ? `<ul class="ability-chips">${caps.map((c) => `<li><code>${esc(c)}</code></li>`).join("")}</ul>`
        : `<p class="muted small">No capabilities declared.</p>`;
      return `
      <article class="agent-connection-card backend-bar ${esc(state)}">
        <header class="agent-connection-head">
          <h3>${esc(a.name || a.id)}</h3>
          <span class="pill ${a.online ? "ok" : "bad"}">${a.online ? "online" : "offline"}</span>
        </header>
        <p class="muted small">${esc(a.description || "")}</p>
        <p><b>Connection:</b> ${esc(label)} — ${esc(msg)}</p>
        <p class="muted small">${startable ? "Managed HTTP backend (startable)." : "Local / inbox adapter (no server to start)."}</p>
        ${base}
        <h4 class="ability-heading">Abilities</h4>
        ${capsHtml}
      </article>`;
    })
    .join("");
}

function renderSetupProviders(runtimes) {
  const providers = runtimes?.providers || [];
  const backend = runtimes?.backend || {};
  const ready = runtimes?.ready;
  const rows = providers
    .map((p) => {
      const badge = p.configured
        ? `<span class="pill ok">available</span>`
        : `<span class="pill bad">needs key</span>`;
      const secret = p.secret_name
        ? `<code class="muted small">${esc(p.secret_name)}</code>`
        : `<span class="muted small">—</span>`;
      return `<div class="setup-provider-row">
        <div><b>${esc(p.label || p.id)}</b> ${p.live ? '<span class="muted small">live</span>' : ""}</div>
        ${secret}
        ${badge}
      </div>`;
    })
    .join("");

  const secretOptions = providers
    .filter((p) => p.secret_name)
    .map((p) => `<option value="${esc(p.secret_name)}">${esc(p.label)} → ${esc(p.secret_name)}</option>`)
    .join("");

  return `
    <div class="setup-backend-bar backend-bar ${esc(backend.state || "down")}">
      <p><b>Daily Coder runtime:</b> ${esc(backend.message || backend.state || "unknown")}
        ${ready ? "" : " — start it to manage API keys."}</p>
      <div class="row">
        <button type="button" class="primary" id="setupStartDc">Start / ensure server</button>
        <button type="button" id="setupRestartDc">Restart</button>
        <button type="button" id="setupRefreshRuntimes">Refresh</button>
        <span id="setupStatus" class="muted small"></span>
      </div>
    </div>
    <h3>Providers (shown in Run area when available)</h3>
    <div class="setup-provider-list">${rows || '<p class="muted">No providers.</p>'}</div>
    <form class="setup-secret-form" id="setupSecretForm">
      <label><span>Secret</span>
        <select id="setupSecretName">${secretOptions || "<option value=''>No secrets</option>"}</select>
      </label>
      <label><span>Value</span>
        <input id="setupSecretValue" type="password" autocomplete="off" placeholder="API key (never stored in browser)" />
      </label>
      <button type="submit" class="primary" id="setupSecretSave">Save key</button>
      <button type="button" id="setupSecretClear">Clear key</button>
    </form>
    <p class="muted small">Keys go to Daily Coder SecretStore via the hub — never into <code>agents.json</code> or the browser.</p>`;
}

export function mount(container) {
  container.innerHTML = `
    <section class="panel apis-panel" data-panel="apis">
      <div id="apisRestartBanner" class="warn banner" hidden role="status">Restart the dashboard for overlay changes to take full effect.</div>
      <div id="staleHubBanner" class="warn banner stale-hub-banner" hidden role="status"></div>

      <section class="setup-panel">
        <h2>Setup</h2>
        <p class="muted small">One LLM runtime (Daily Coder). Configure providers and API keys here; only available runtimes appear in the Agent run area.</p>
        <div id="setupRoot"><p class="muted">Loading…</p></div>
      </section>

      <h2>Agent connections &amp; abilities</h2>
      <p class="muted small">Live status from <code>GET /api/agents</code> — Daily Coder, Research Forge, and Daily Task.</p>
      <div id="agentConnections" class="agent-connections"><p class="muted">Loading…</p></div>
      <h2>Hub routes (OpenAPI)</h2>
      <p class="muted small">Hub-owned paths only — agent backends are not listed here (G5).</p>
      <div class="table-wrap" id="openapiTable"><p class="muted">Loading…</p></div>
      <h2>Config overlay</h2>
      <p class="muted small">Writes <code>data_dir/config_overlay.json</code> only — never repo <code>agents.json</code>.</p>
      <form id="overlayForm" class="overlay-form"></form>
      <div class="row">
        <button type="button" id="overlaySave" class="primary">Save overlay</button>
        <span id="overlayStatus" class="muted small"></span>
      </div>
    </section>`;

  const banner = container.querySelector("#apisRestartBanner");
  const stale = container.querySelector("#staleHubBanner");
  const form = container.querySelector("#overlayForm");
  const status = container.querySelector("#overlayStatus");
  const connections = container.querySelector("#agentConnections");
  const setupRoot = container.querySelector("#setupRoot");

  async function refreshSetup() {
    try {
      const runtimes = await api("/api/setup/runtimes");
      setupRoot.innerHTML = renderSetupProviders(runtimes);
      wireSetup();
    } catch (err) {
      setupRoot.innerHTML = `<p class="bad">${esc(err.message)}</p>`;
    }
  }

  function wireSetup() {
    const statusEl = container.querySelector("#setupStatus");
    container.querySelector("#setupStartDc")?.addEventListener("click", async () => {
      if (statusEl) statusEl.textContent = "Starting…";
      try {
        await ensureBackend("daily-coder", {
          provider: "mock",
          requireLiveConfirm: () => true,
        });
        if (statusEl) statusEl.textContent = "Ready";
        await refreshSetup();
        connections.innerHTML = renderAgentConnections(await fetchAgents());
      } catch (err) {
        if (statusEl) statusEl.textContent = err.message;
      }
    });
    container.querySelector("#setupRestartDc")?.addEventListener("click", async () => {
      if (statusEl) statusEl.textContent = "Restarting…";
      try {
        await backendAction("daily-coder", "restart", session.getProvider() || "mock");
        await refreshSetup();
        if (statusEl) statusEl.textContent = "Restarted";
      } catch (err) {
        if (statusEl) statusEl.textContent = err.message;
      }
    });
    container.querySelector("#setupRefreshRuntimes")?.addEventListener("click", () => refreshSetup());

    container.querySelector("#setupSecretForm")?.addEventListener("submit", async (e) => {
      e.preventDefault();
      const name = container.querySelector("#setupSecretName")?.value;
      const value = container.querySelector("#setupSecretValue")?.value;
      if (!name || !value) {
        if (statusEl) statusEl.textContent = "Name and value required";
        return;
      }
      try {
        await api("/api/setup/secrets", {
          method: "POST",
          body: JSON.stringify({ action: "set", name, value }),
        });
        container.querySelector("#setupSecretValue").value = "";
        if (statusEl) statusEl.textContent = "Key saved";
        await refreshSetup();
      } catch (err) {
        if (statusEl) statusEl.textContent = err.message;
      }
    });
    container.querySelector("#setupSecretClear")?.addEventListener("click", async () => {
      const name = container.querySelector("#setupSecretName")?.value;
      if (!name) return;
      try {
        await api("/api/setup/secrets", {
          method: "POST",
          body: JSON.stringify({ action: "delete", name }),
        });
        if (statusEl) statusEl.textContent = "Key cleared";
        await refreshSetup();
      } catch (err) {
        if (statusEl) statusEl.textContent = err.message;
      }
    });
  }

  Promise.all([
    api("/api/openapi.json"),
    api("/api/config/overlay"),
    fetchAgents(),
    api("/api/setup/expected-agents").catch(() => null),
    refreshSetup(),
  ])
    .then(([openapi, cfg, agents, expected]) => {
      connections.innerHTML = renderAgentConnections(agents);
      container.querySelector("#openapiTable").innerHTML = `
        <table><thead><tr><th>Method</th><th>Path</th><th>Summary</th></tr></thead>
        <tbody>${renderRoutes(openapi)}</tbody></table>`;
      form.innerHTML = overlayForm(cfg.overlay);
      banner.hidden = !cfg.restart_required;
      if (expected?.stale || (expected?.expected && agents.length < expected.expected.length)) {
        stale.hidden = false;
        stale.textContent =
          "Hub may be stale: config expects more agents than this process loaded. Restart with python start.py from gui/.";
      } else if (agents.length < 3) {
        stale.hidden = false;
        stale.textContent =
          "Expected Daily Coder, Research Forge, and Daily Task. Restart the hub if Daily Task is missing.";
      } else {
        stale.hidden = true;
      }
    })
    .catch((err) => {
      connections.innerHTML = `<p class="bad">${esc(err.message)}</p>`;
      container.querySelector("#openapiTable").innerHTML = `<p class="bad">${esc(err.message)}</p>`;
    });

  container.querySelector("#overlaySave").addEventListener("click", async () => {
    const body = {};
    const ta = form.querySelector("[data-key=workspace_roots]");
    if (ta) {
      const raw = ta.value.trim();
      if (raw) {
        try {
          body.workspace_roots = JSON.parse(raw);
        } catch {
          status.textContent = "workspace_roots must be valid JSON";
          return;
        }
      } else {
        body.workspace_roots = [];
      }
    }
    try {
      const result = await api("/api/config/overlay", {
        method: "POST",
        body: JSON.stringify(body),
      });
      status.textContent = "Saved";
      banner.hidden = !result.restart_required;
    } catch (err) {
      status.textContent = err.message;
    }
  });
}
