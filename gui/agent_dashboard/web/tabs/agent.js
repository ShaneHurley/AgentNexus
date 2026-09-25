/** Agent orchestration tab — composer + one active session per agent. */

import { api } from "../api.js";
import { fetchAgents, backendAction, setAgentProvider, ensureBackend } from "../agents.js";
import { renderRuns, renderApprovals, renderActivity } from "../runs.js";
import { renderThread, sendMessage, applyQueued } from "../chat.js";
import { renderSessionSidebar } from "../session-sidebar.js";
import { mountComposerPicker } from "../composer-picker.js";
import * as session from "../state.js";
import { registerPoller, unregisterPoller } from "../poll.js";

const AGENT_HTML = `
  <div class="layout agent-layout">
    <aside class="panel agents-panel session-rail" id="sessionRail">
      <div id="agentList" class="agent-list"><p class="muted">loading…</p></div>
    </aside>

    <main class="panel main-panel">
      <div id="staleHubBanner" class="warn banner stale-hub-banner" hidden role="status"></div>
      <section class="composer">
        <h2 id="agentTitle">Select an agent</h2>
        <p id="agentDesc" class="muted">Pick an agent, then Open one session — that becomes your working context.</p>
        <p id="activeSessionLine" class="muted small active-session-line">No session selected.</p>
        <div id="backendBar" class="backend-bar muted">Select an agent to see server status.</div>
        <div class="row backend-token-row" id="backendTokenRow" hidden>
          <input id="backendToken" type="password" placeholder="Daily Coder API token (if started outside the hub)" />
          <button type="button" id="saveBackendToken">Save agent token</button>
        </div>
        <div id="composerPickerHost"></div>
      </section>

      <section class="split">
        <div class="disclose" data-section="runs">
          <button type="button" class="disclose-toggle" aria-expanded="false" data-disclose="runs">
            <span class="disclose-chevron" aria-hidden="true">▸</span>
            <h2>Runs</h2>
          </button>
          <div class="disclose-body" id="runsBody" hidden>
            <div id="runs" class="table-wrap"><p class="muted">—</p></div>
          </div>
        </div>
        <div class="disclose" data-section="waiting">
          <button type="button" class="disclose-toggle" aria-expanded="false" data-disclose="waiting">
            <span class="disclose-chevron" aria-hidden="true">▸</span>
            <h2>Waiting for you</h2>
          </button>
          <div class="disclose-body" id="waitingBody" hidden>
            <div id="approvals" class="table-wrap"><p class="muted">—</p></div>
          </div>
        </div>
      </section>

      <section class="split">
        <div class="disclose" data-section="activity">
          <button type="button" class="disclose-toggle" aria-expanded="true" data-disclose="activity">
            <span class="disclose-chevron" aria-hidden="true">▾</span>
            <h2>Activity</h2>
          </button>
          <div class="disclose-body" id="activityBody">
            <div id="activity" class="table-wrap"><p class="muted">—</p></div>
          </div>
        </div>
        <div class="disclose" data-section="steer">
          <button type="button" class="disclose-toggle" aria-expanded="true" data-disclose="steer">
            <span class="disclose-chevron" aria-hidden="true">▾</span>
            <h2>Steer / talk</h2>
          </button>
          <div class="disclose-body" id="steerBody">
            <p class="muted small">Bound to the one active session. Messages queue until a checkpoint. <b>Mark applied</b> is local only — use <b>Approve</b> on a waiting run to send queued notes to the agent.</p>
            <div id="thread" class="thread"></div>
            <div class="row">
              <input id="chatInput" placeholder="Steering note or follow-up…" />
              <button type="button" id="sendBtn">Send</button>
              <button type="button" id="applyBtn" title="Marks notes applied in the dashboard only. Use Approve on a waiting run to send queued notes to the agent.">Mark applied (local)</button>
            </div>
          </div>
        </div>
      </section>
    </main>
  </div>
`;

const state = {
  agentId: session.getAgentId(),
  runId: session.getRunId(),
  agents: [],
};

let mounted = false;
const AGENT_POLL_ID = "agent-tab";
let inFlight = false;
let onNavigate = null;
let pickerApi = null;

function escSafe(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

function updateActiveSessionLine() {
  const el = document.getElementById("activeSessionLine");
  if (!el) return;
  if (!state.agentId) {
    el.textContent = "No agent selected.";
    return;
  }
  if (!state.runId) {
    el.textContent = "No session selected — Open one from the session rail, or Start work.";
    return;
  }
  el.textContent = `Active session: ${state.runId}`;
}

function applyDiscloseState() {
  const map = session.getAgentSections();
  document.querySelectorAll("[data-disclose]").forEach((btn) => {
    const id = btn.getAttribute("data-disclose");
    const open = Boolean(map[id]);
    btn.setAttribute("aria-expanded", open ? "true" : "false");
    const chev = btn.querySelector(".disclose-chevron");
    if (chev) chev.textContent = open ? "▾" : "▸";
    const body = btn.parentElement?.querySelector(".disclose-body");
    if (body) body.hidden = !open;
  });
}

function wireDisclose() {
  document.querySelectorAll("[data-disclose]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = btn.getAttribute("data-disclose");
      const map = session.getAgentSections();
      const next = !map[id];
      session.setAgentSection(id, next);
      applyDiscloseState();
    });
  });
  applyDiscloseState();
}

function updateBackendBar(agent) {
  const bar = document.getElementById("backendBar");
  const tokenRow = document.getElementById("backendTokenRow");
  if (!bar) return;
  if (!agent) {
    bar.textContent = "Select an agent to see server status.";
    bar.className = "backend-bar muted";
    if (tokenRow) tokenRow.hidden = true;
    return;
  }
  const b = agent.backend || {};
  const stateName = b.state || (agent.online ? "ready" : "down");
  bar.textContent = b.message || stateName;
  bar.className = `backend-bar ${stateName}`;
  if (tokenRow) tokenRow.hidden = !(b.startable && stateName === "unauthorized");
}

function selectedProvider() {
  if (pickerApi) return pickerApi.selectedProvider();
  return session.getProvider();
}

function isLiveProvider(provider) {
  return Boolean(provider && provider !== "mock");
}

function backendServerRunning(backend) {
  if (!backend) return false;
  return Boolean(backend.online || backend.managed);
}

export function requireLiveStartConfirm(agentId, action) {
  if (agentId !== "daily-coder" || (action !== "start" && action !== "restart")) {
    return true;
  }
  const provider = selectedProvider();
  if (!isLiveProvider(provider)) return true;
  const cb = document.getElementById("liveConfirm");
  if (cb?.checked) return true;
  return window.confirm("Start LIVE provider (may spend API credits)?");
}

async function selectAgent(id) {
  const switching = id !== state.agentId;
  state.agentId = id;
  session.setAgentId(id);
  // One session per agent: restore the session this agent last had Opened.
  state.runId = session.getRunIdForAgent(id);
  session.setRunId(state.runId);
  syncRouteHash();
  const agent = state.agents.find((a) => a.id === id);
  const title = document.getElementById("agentTitle");
  const desc = document.getElementById("agentDesc");
  if (title) title.textContent = agent ? agent.name : id;
  if (desc) {
    desc.textContent = agent
      ? `${agent.description || ""} — working context is the one session you Open.`
      : "";
  }

  if (pickerApi) {
    const saved = session.getProvider();
    let model = saved;
    if (id === "daily-coder" && agent?.backend?.provider) {
      model = agent.backend.provider;
    }
    pickerApi.sync({ agents: state.agents, agentId: id, model });
    pickerApi.showRestartWarn(false);
  }
  updateBackendBar(agent);
  updateActiveSessionLine();
  await refreshAgentPanels();
  await refreshSidebar();
  if (switching && state.runId) {
    await renderActivity(state.agentId, state.runId);
    await renderThread(state.agentId, state.runId);
  }
}

async function selectRun(runId) {
  state.runId = runId;
  session.setRunId(runId);
  syncRouteHash();
  updateActiveSessionLine();
  await renderActivity(state.agentId, runId);
  await renderThread(state.agentId, runId);
  await refreshSidebar();
}

async function selectRunFromRail(agentId, runId) {
  if (agentId !== state.agentId) {
    await selectAgent(agentId);
  }
  await selectRun(runId);
}

function syncRouteHash() {
  if (typeof onNavigate !== "function") return;
  onNavigate({
    tab: "agent",
    agentId: state.agentId,
    runId: state.runId,
    doc: "",
  });
}

async function refreshSidebar() {
  const list = document.getElementById("agentList");
  if (!list) return;
  try {
    state.agents = await renderSessionSidebar(list, {
      selectedAgentId: state.agentId,
      selectedRunId: state.runId,
      agents: state.agents.length ? state.agents : undefined,
      onSelectAgent: selectAgent,
      onSelectRun: selectRunFromRail,
      onBackend,
    });
  } catch (err) {
    list.innerHTML = `<p class="bad">${escSafe(err.message)}</p>`;
  }
}

async function refreshAgentPanels() {
  if (!state.agentId) return;
  const agent = state.agents.find((a) => a.id === state.agentId);
  const backend = agent && agent.backend;
  if (backend && backend.startable && backend.state !== "ready") {
    document.getElementById("runs").innerHTML =
      `<p class="muted">${escSafe(backend.message || "Server not ready.")} Starting work will auto-start the server. Use <b>Restart</b> / <b>Stop</b> in the session rail if needed.</p>`;
    document.getElementById("approvals").innerHTML = `<p class="muted">—</p>`;
    document.getElementById("activity").innerHTML = `<p class="muted">—</p>`;
    await renderThread(state.agentId, state.runId || null);
    return;
  }
  try {
    await renderRuns(state.agentId, selectRun, state.runId, agent?.capabilities || []);
    await renderApprovals(state.agentId, refreshAgentPanels);
    await renderActivity(state.agentId, state.runId || null);
  } catch (err) {
    document.getElementById("runs").innerHTML = `<p class="bad">${escSafe(err.message)}</p>`;
  }
  await renderThread(state.agentId, state.runId || null);
}

async function onBackend(agentId, action) {
  if (!requireLiveStartConfirm(agentId, action)) {
    return;
  }
  const bar = document.getElementById("backendBar");
  bar.textContent = action === "stop" ? "Stopping…" : "Starting server…";
  bar.className = "backend-bar muted";
  try {
    const provider = agentId === "daily-coder" ? selectedProvider() : undefined;
    const result = await backendAction(agentId, action, provider);
    if (!result.ok && result.error) throw new Error(result.error);
    await refresh();
  } catch (err) {
    bar.textContent = err.message;
    bar.className = "backend-bar down";
  }
}

async function refresh() {
  if (!mounted) return;
  try {
    state.agents = await fetchAgents();
    try {
      const expected = await api("/api/setup/expected-agents");
      const banner = document.getElementById("staleHubBanner");
      if (banner) {
        if (expected.stale || state.agents.length < (expected.expected?.length || 3)) {
          banner.hidden = false;
          banner.textContent =
            "Hub may be stale — config expects Daily Coder, Research Forge, and Daily Task. Restart with python start.py from gui/.";
        } else {
          banner.hidden = true;
        }
      }
    } catch {
      /* ignore */
    }
    if (!state.agentId && state.agents.length) {
      await selectAgent(state.agents[0].id);
    } else if (state.agentId) {
      await selectAgent(state.agentId);
    } else {
      await refreshSidebar();
    }
    const savedRun = session.getRunIdForAgent(state.agentId);
    if (state.agentId && savedRun && state.runId !== savedRun) {
      state.runId = savedRun;
    }
    if (state.runId) {
      await selectRun(state.runId);
    }
    updateActiveSessionLine();
  } catch (err) {
    const list = document.getElementById("agentList");
    if (list) list.innerHTML = `<p class="bad">${escSafe(err.message)}</p>`;
  }
}

function wireEvents() {
  document.getElementById("saveBackendToken").addEventListener("click", async () => {
    if (!state.agentId) return;
    const token = document.getElementById("backendToken").value.trim();
    try {
      await api(`/api/agents/${encodeURIComponent(state.agentId)}/backend`, {
        method: "POST",
        body: JSON.stringify({ action: "set_token", token }),
      });
      document.getElementById("backendToken").value = "";
      await refresh();
    } catch (err) {
      document.getElementById("backendBar").textContent = err.message;
    }
  });

  document.getElementById("composerPickerHost").addEventListener("click", async (e) => {
    if (!e.target.closest("#startBtn")) return;
    if (!state.agentId) return;
    const values = pickerApi?.getValues() || {};
    const request = values.request;
    if (!request) return;
    if (values.modelBlocked) {
      const startResult = document.getElementById("startResult");
      if (startResult) {
        startResult.textContent = "Configure the selected provider in APIs & abilities → Setup first.";
      }
      return;
    }
    const startResult = document.getElementById("startResult");
    try {
      startResult.textContent = "Ensuring server…";
      await ensureBackend(state.agentId, {
        provider: state.agentId === "daily-coder" ? selectedProvider() : undefined,
        requireLiveConfirm: requireLiveStartConfirm,
        agents: state.agents,
      });
      const body = {
        request,
        context: values.context,
        thinking: values.thinking,
        forced_subagents: values.forced_subagents || [],
      };
      if (state.agentId === "daily-coder") {
        body.model = values.model;
        if (values.repo) body.repo = values.repo;
      }
      const result = await api(`/api/agents/${encodeURIComponent(state.agentId)}/runs`, {
        method: "POST",
        body: JSON.stringify(body),
      });
      const repoBits = [];
      if (result.repo_path) repoBits.push(result.repo_path);
      if (result.git_head) repoBits.push(`HEAD ${result.git_head}`);
      if (result.git_dirty === true) repoBits.push("dirty");
      else if (result.git_dirty === false) repoBits.push("clean");
      const repoLine = repoBits.length ? ` · ${repoBits.join(" · ")}` : "";
      startResult.textContent = `accepted ${result.run_id || ""}${repoLine}`;
      const ta = document.getElementById("workRequest");
      if (ta) ta.value = "";
      if (result.run_id) {
        state.runId = result.run_id;
        session.setRunId(result.run_id);
        updateActiveSessionLine();
      }
      await refresh();
      if (state.runId) await selectRun(state.runId);
    } catch (err) {
      startResult.textContent = err.message;
    }
  });

  document.getElementById("sendBtn").addEventListener("click", async () => {
    if (!state.agentId) return;
    const input = document.getElementById("chatInput");
    const text = input.value.trim();
    if (!text) return;
    await sendMessage(state.agentId, state.runId, text);
    input.value = "";
    await renderThread(state.agentId, state.runId || null);
  });

  document.getElementById("applyBtn").addEventListener("click", async () => {
    if (!state.agentId) return;
    await applyQueued(state.agentId, state.runId, { alsoApprove: false });
    await refreshAgentPanels();
  });

  document.getElementById("chatInput").addEventListener("keydown", (e) => {
    if (e.key === "Enter") document.getElementById("sendBtn").click();
  });
}

async function onProviderChange(provider) {
  session.setProvider(provider);
  const agent = state.agents.find((a) => a.id === state.agentId);
  const backend = agent?.backend;
  const warn =
    state.agentId === "daily-coder" &&
    backendServerRunning(backend) &&
    backend.provider &&
    provider !== backend.provider;
  pickerApi?.showRestartWarn(Boolean(warn));
  if (state.agentId === "daily-coder") {
    try {
      await setAgentProvider(state.agentId, provider);
    } catch (err) {
      const el = document.getElementById("startResult");
      if (el) el.textContent = err.message;
    }
  }
}

async function tick() {
  if (!mounted || inFlight || document.hidden || !navigator.onLine) return;
  inFlight = true;
  try {
    state.agents = await fetchAgents();
    const agent = state.agents.find((a) => a.id === state.agentId);
    updateBackendBar(agent);
    pickerApi?.sync({ agents: state.agents, agentId: state.agentId });
    if (state.agentId) await refreshAgentPanels();
    await refreshSidebar();
  } catch {
    /* ignore transient poll errors */
  } finally {
    inFlight = false;
  }
}

function startPoll() {
  stopPoll();
  registerPoller(AGENT_POLL_ID, { tab: "agent", fn: tick });
}

function stopPoll() {
  unregisterPoller(AGENT_POLL_ID);
}

/**
 * Re-apply deep-link when already on the agent tab (hash sync).
 * @param {{ agentId?: string, runId?: string }} route
 */
export function syncRoute(route = {}) {
  if (!mounted) return;
  const nextAgent = route.agentId || "";
  const nextRun = route.runId || "";
  (async () => {
    if (nextAgent && nextAgent !== state.agentId) {
      await selectAgent(nextAgent);
    }
    if (nextRun && nextRun !== state.runId) {
      await selectRun(nextRun);
    } else if (!nextRun && state.runId && nextAgent === state.agentId) {
      /* keep current run unless hash cleared intentionally with agent only */
    }
  })().catch(() => {});
}

/**
 * @param {HTMLElement} container
 * @param {{ agentId?: string, runId?: string, navigate?: (route: object) => void }} route
 */
export function mount(container, route = {}) {
  mounted = true;
  onNavigate = route.navigate || null;
  container.innerHTML = AGENT_HTML;
  wireDisclose();
  wireEvents();

  state.agentId = route.agentId || session.getAgentId();
  state.runId =
    route.runId ||
    (state.agentId ? session.getRunIdForAgent(state.agentId) : session.getRunId());

  pickerApi = mountComposerPicker(document.getElementById("composerPickerHost"), {
    agents: state.agents,
    agentId: state.agentId,
    onAgentChange: selectAgent,
    onProviderChange,
  });

  updateActiveSessionLine();
  refresh();
  startPoll();
}

export function unmount() {
  mounted = false;
  stopPoll();
  onNavigate = null;
  pickerApi?.destroy?.();
  pickerApi = null;
}

export { refresh as refreshAgentTab };