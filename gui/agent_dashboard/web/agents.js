/** Agent list helpers + backend start/stop + ensureBackend. */

import { api, esc } from "./api.js";

const ensureInflight = new Map();

function stateLabel(backend) {
  if (!backend) return "";
  const s = backend.state || "";
  if (s === "ready") return "ready";
  if (s === "unauthorized") return "needs token / restart";
  if (s === "degraded") return "server error";
  if (s === "down") return "server off";
  return s;
}

export { stateLabel };

export async function fetchAgents() {
  return api("/api/agents");
}

/**
 * Ensure a startable agent backend is ready before starting work.
 * Debounced per agentId; no infinite retry. Surfaces port-conflict via thrown Error.
 * @param {string} agentId
 * @param {{
 *   provider?: string,
 *   requireLiveConfirm?: (agentId: string, action: string) => boolean,
 *   agents?: object[],
 * }} [opts]
 */
export async function ensureBackend(agentId, opts = {}) {
  if (!agentId) return { ok: true, skipped: true };

  if (ensureInflight.has(agentId)) {
    return ensureInflight.get(agentId);
  }

  const work = (async () => {
    let agents = opts.agents;
    if (!agents) {
      agents = await fetchAgents();
    }
    const agent = agents.find((a) => a.id === agentId);
    if (!agent) return { ok: false, error: `Unknown agent ${agentId}` };

    const b = agent.backend || {};
    if (!b.startable) {
      return { ok: true, skipped: true, agent };
    }
    if (b.state === "ready") {
      return { ok: true, ready: true, agent };
    }

    if (typeof opts.requireLiveConfirm === "function") {
      if (!opts.requireLiveConfirm(agentId, "start")) {
        return { ok: false, cancelled: true, error: "Live start cancelled" };
      }
    }

    const provider = opts.provider;
    try {
      const result = await backendAction(agentId, "start", provider);
      if (!result.ok && result.error) {
        throw new Error(result.error);
      }
      const refreshed = await fetchAgents();
      const after = refreshed.find((a) => a.id === agentId);
      const state = after?.backend?.state;
      if (state !== "ready") {
        const msg =
          after?.backend?.message ||
          result.message ||
          "Server did not become ready. Use Restart if the port is in use.";
        throw new Error(msg);
      }
      return { ok: true, started: true, agent: after, agents: refreshed };
    } catch (err) {
      const msg = err?.message || String(err);
      const hint = /port|conflict|address already|EADDRINUSE/i.test(msg)
        ? `${msg} — try Restart in the session rail.`
        : msg;
      throw new Error(hint);
    }
  })();

  ensureInflight.set(agentId, work);
  try {
    return await work;
  } finally {
    ensureInflight.delete(agentId);
  }
}

/** @deprecated Prefer session-sidebar; kept for any callers needing card list. */
export async function loadAgents(selectedId, onSelect, onBackend) {
  const agents = await fetchAgents();
  const root = document.getElementById("agentList");
  if (!root) return agents;
  if (!agents.length) {
    root.innerHTML = `<p class="muted">No agents registered. Edit config/agents.json.</p>`;
    return agents;
  }
  root.innerHTML = agents
    .map((a) => {
      const b = a.backend || {};
      const ready = a.online || b.state === "ready";
      const startable = !!b.startable;
      const showRestart =
        startable && (b.state === "unauthorized" || b.state === "ready" || b.state === "degraded" || b.state === "down");
      const showStop = startable && (b.managed || b.online);
      const label = stateLabel(b);
      const message = b.message ? String(b.message) : "";
      return `
    <div class="agent-block">
      <button type="button" class="agent-card ${a.id === selectedId ? "active" : ""}" data-id="${esc(a.id)}">
        <b><span class="dot ${ready ? "on" : "off"}"></span>${esc(a.name)}</b>
        <span class="muted small agent-desc">${esc(a.description || "")}</span>
        ${label ? `<span class="muted small agent-status">${esc(label)}</span>` : ""}
        ${message ? `<span class="muted small agent-msg">${esc(message)}</span>` : ""}
        ${!startable ? `<span class="muted small agent-local-hint">no server needed</span>` : ""}
      </button>
      <div class="agent-actions">
        ${showRestart ? `<button type="button" data-be="restart" data-id="${esc(a.id)}" title="Stops the dashboard-managed server. Force may kill whatever is using the Daily Coder port.">Restart</button>` : ""}
        ${showStop ? `<button type="button" data-be="stop" data-id="${esc(a.id)}">Stop</button>` : ""}
      </div>
    </div>`;
    })
    .join("");

  root.querySelectorAll(".agent-card").forEach((btn) => {
    btn.addEventListener("click", () => onSelect(btn.dataset.id));
  });
  root.querySelectorAll("[data-be]").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      btn.disabled = true;
      try {
        await onBackend(btn.dataset.id, btn.dataset.be);
      } finally {
        btn.disabled = false;
      }
    });
  });
  return agents;
}

export async function backendAction(agentId, action, provider) {
  const body = { action, force: action === "restart" };
  if (provider) body.provider = provider;
  return api(`/api/agents/${encodeURIComponent(agentId)}/backend`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function setAgentProvider(agentId, provider) {
  return api(`/api/agents/${encodeURIComponent(agentId)}/backend`, {
    method: "POST",
    body: JSON.stringify({ action: "set_provider", provider }),
  });
}
