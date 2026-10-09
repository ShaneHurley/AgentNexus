/**
 * workspace.js — AgentNexus workspace controller.
 *
 * This is the primary orchestrator for the new IDE-style dashboard shell.
 * It manages:
 *   - Top-bar agent launch chips
 *   - Session tabs (one per active agent run)
 *   - Chat panel rendering (bubbles, thinking stream, composer)
 *   - Panel dock (browser / code / plan)
 *   - Left sidebar (session rail + daily tasks)
 *   - Resize handles (sidebar, dock)
 *   - Keyboard shortcuts
 *   - Status bar (agents, sessions, panels, clock)
 *
 * Talks exclusively to the existing /api/* Python gateway.
 * Zero backend changes required.
 */

import { api, getToken, setToken } from "./api.js";
import { fetchAgents } from "./agents.js";
import { renderMarkdown } from "./markdown.js";
import { registerPoller, unregisterPoller, setActiveAppTab } from "./poll.js";
import { renderChatPanel, renderHomeScreen, appendMessageBubble, setThinkingState } from "./chat-panel.js";
import { renderDockPanel, renderDockEmpty, PANEL_ICONS } from "./panel-dock.js";
import { renderSidebar, loadTasks } from "./sidebar.js";
import { setupResize } from "./resize.js";
import * as st from "./state.js";

// ── Helpers ───────────────────────────────────────────────────────────────────

const _esc = (s) =>
  String(s == null ? "" : s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );

const AGENT_ICONS = {
  "daily-coder": "⚙️",
  "research-forge": "🔬",
  "daily-task": "📋",
};

// ── In-memory state ───────────────────────────────────────────────────────────

const state = {
  agents: [],            // agent list from /api/agents
  sessions: [],          // active session tabs: [{sessionId, agentId, runId, label, status, messages}]
  activeSessionId: null, // currently visible session tab
  dockPanels: [],        // [{id, type, label, url?, path?, content?}]
  activeDockId: null,
  sidebarCollapsed: st.getRailCollapsed(),
  inFlight: false,       // global poll guard
};

// ── Boot ──────────────────────────────────────────────────────────────────────

export async function init() {
  // Poll guard — tell poll.js we own the workspace tab slot
  setActiveAppTab("workspace");

  setupResizeHandles();
  setupKeyboardShortcuts();
  setupSettingsModal();
  startClock();

  await refreshAgents();
  renderLaunchBar();
  renderSidebarPane();
  showHomeOrSession();

  // Start periodic refresh
  registerPoller("workspace-tick", {
    tab: "workspace",
    fn: periodicTick,
    interval: 6000,
  });
}

// ── Agent refresh ─────────────────────────────────────────────────────────────

async function refreshAgents() {
  try {
    state.agents = await fetchAgents();
    updateHealth();
  } catch (err) {
    setHealthBadge("offline", false);
  }
  renderStatusBar();
}

async function periodicTick() {
  if (state.inFlight || document.hidden || !navigator.onLine) return;
  state.inFlight = true;
  try {
    state.agents = await fetchAgents();
    updateHealth();
    renderLaunchBar();
    // Poll activity for active session
    if (state.activeSessionId) {
      await pollActiveSession();
    }
    await renderSidebarPane();
  } catch { /* ignore transient errors */ }
  finally { state.inFlight = false; }
  renderStatusBar();
}

async function pollActiveSession() {
  const sess = state.sessions.find((s) => s.sessionId === state.activeSessionId);
  if (!sess) return;
  try {
    // Fetch latest activity
    const q = sess.runId ? `?run_id=${encodeURIComponent(sess.runId)}` : "";
    const activities = await api(`/api/agents/${encodeURIComponent(sess.agentId)}/activity${q}`);
    const latest = Array.isArray(activities) ? activities.slice(-1)[0] : null;
    const thinking = Boolean(latest && latest.status === "running");
    const thinkingLabel = latest?.phase
      ? `${latest.phase}…`
      : thinking ? "Working…" : "";
    sess.thinking = thinking;
    sess.thinkingLabel = thinkingLabel;
    sess.status = thinking ? "thinking" : "idle";

    // Update thinking indicator in active chat panel
    const chatPanel = document.getElementById("wsChatPanel");
    if (chatPanel && state.activeSessionId === sess.sessionId) {
      setThinkingState(chatPanel, thinking, thinkingLabel);
      updateTabDot(sess.sessionId, sess.status);
    }

    // Fetch thread messages
    const threadQ = sess.runId ? `?run_id=${encodeURIComponent(sess.runId)}` : "";
    const msgs = await api(`/api/agents/${encodeURIComponent(sess.agentId)}/thread${threadQ}`);
    if (Array.isArray(msgs) && msgs.length !== sess.messages.length) {
      const newMsgs = msgs.slice(sess.messages.length);
      sess.messages = msgs;
      newMsgs.forEach((m) => {
        if (chatPanel && state.activeSessionId === sess.sessionId) {
          appendMessageBubble(chatPanel, m, onRefChipClick);
        }
      });
    }
  } catch { /* ignore */ }
}

// ── Launch bar ────────────────────────────────────────────────────────────────

function renderLaunchBar() {
  const bar = document.getElementById("wsLaunchBar");
  if (!bar) return;

  bar.innerHTML = `
    <button type="button" class="ws-launch-chip ws-launch-all" id="launchAllBtn" title="Launch all agents at once">
      ⚡ Launch All
    </button>
    ${state.agents.map((a) => {
      const ready = a.online || a.backend?.state === "ready";
      return `<button type="button" class="ws-launch-chip ${ready ? "online" : ""}"
                      data-launch-agent="${_esc(a.id)}"
                      title="${_esc(a.description || a.name)}">
                <span class="ws-chip-dot"></span>
                ${AGENT_ICONS[a.id] || "🤖"} ${_esc(a.name)}
              </button>`;
    }).join("")}
  `;

  bar.querySelector("#launchAllBtn")?.addEventListener("click", launchAll);
  bar.querySelectorAll("[data-launch-agent]").forEach((btn) => {
    btn.addEventListener("click", () => launchSession(btn.dataset.launchAgent));
  });
}

// ── Session management ────────────────────────────────────────────────────────

/**
 * POST /api/agents/{id}/runs and open a session tab.
 * Default request is empty so the agent enters interactive mode.
 */
async function launchSession(agentId, requestText = "") {
  const agent = state.agents.find((a) => a.id === agentId);
  if (!agent) return;

  // Show optimistic tab immediately
  const sessionId = `${agentId}-${Date.now()}`;
  const sess = {
    sessionId,
    agentId,
    runId: "",
    label: agent.name,
    status: "launching",
    thinking: false,
    thinkingLabel: "Launching…",
    messages: [],
  };
  state.sessions.push(sess);
  state.activeSessionId = sessionId;

  renderSessionTabs();
  renderActiveChatPanel();

  // Fire the run
  try {
    const body = { request: requestText || "Hello — I've launched you. Stand by for instructions." };
    const result = await api(`/api/agents/${encodeURIComponent(agentId)}/runs`, {
      method: "POST",
      body: JSON.stringify(body),
    });
    if (result.run_id) {
      sess.runId = result.run_id;
      sess.label = agent.name;
      sess.status = "thinking";
      sess.thinking = true;
      sess.thinkingLabel = "Starting…";
      // Persist
      st.setRunIdForAgent(agentId, result.run_id);
    }
    renderSessionTabs();
    renderActiveChatPanel();
  } catch (err) {
    sess.status = "error";
    sess.thinking = false;
    // Show error as a system message in the chat
    sess.messages.push({
      role: "system",
      text: `Failed to launch: ${err.message}`,
      created_at: new Date().toISOString(),
    });
    renderActiveChatPanel();
  }
  renderStatusBar();
}

/** Launch all agents simultaneously. */
async function launchAll() {
  await Promise.allSettled(state.agents.map((a) => launchSession(a.id)));
}

function selectSession(sessionId) {
  if (state.activeSessionId === sessionId) return;
  state.activeSessionId = sessionId;
  renderSessionTabs();
  renderActiveChatPanel();
}

function closeSession(sessionId) {
  const idx = state.sessions.findIndex((s) => s.sessionId === sessionId);
  if (idx === -1) return;
  const sess = state.sessions[idx];
  if (sess.status === "thinking") {
    if (!confirm(`Agent "${sess.label}" is still working. Close anyway?`)) return;
  }
  state.sessions.splice(idx, 1);
  if (state.activeSessionId === sessionId) {
    state.activeSessionId = state.sessions[state.sessions.length - 1]?.sessionId || null;
  }
  renderSessionTabs();
  showHomeOrSession();
  renderStatusBar();
}

// ── Session tab strip ─────────────────────────────────────────────────────────

function renderSessionTabs() {
  const tabStrip = document.getElementById("wsSessionTabs");
  if (!tabStrip) return;

  tabStrip.innerHTML = `
    ${state.sessions.map((s) => {
      const active = s.sessionId === state.activeSessionId;
      const dotClass = s.status === "thinking" ? "thinking" : s.status === "error" ? "error" : active ? "active" : "idle";
      return `
        <button type="button" role="tab"
                class="ws-session-tab${active ? "" : ""}"
                aria-selected="${active}"
                data-tab-id="${_esc(s.sessionId)}"
                title="${_esc(s.label)} — ${_esc(s.runId || "launching")}">
          <span class="ws-tab-dot ${dotClass}" aria-hidden="true"></span>
          ${AGENT_ICONS[s.agentId] || "🤖"} ${_esc(s.label)}
          <button type="button" class="ws-session-tab-close"
                  data-close-tab="${_esc(s.sessionId)}"
                  aria-label="Close ${_esc(s.label)}" title="Close">✕</button>
        </button>
      `;
    }).join("")}
    <button type="button" class="ws-tab-new" id="wsTabNew" title="Launch new agent (Ctrl+K)">+</button>
  `;

  tabStrip.querySelectorAll("[data-tab-id]").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      if (e.target.closest("[data-close-tab]")) return;
      selectSession(btn.dataset.tabId);
    });
  });
  tabStrip.querySelectorAll("[data-close-tab]").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      closeSession(btn.dataset.closeTab);
    });
  });
  tabStrip.querySelector("#wsTabNew")?.addEventListener("click", () => openLaunchPicker());
}

function updateTabDot(sessionId, status) {
  const btn = document.querySelector(`[data-tab-id="${CSS.escape(sessionId)}"] .ws-tab-dot`);
  if (!btn) return;
  btn.className = `ws-tab-dot ${status === "thinking" ? "thinking" : status === "error" ? "error" : "active"}`;
}

// ── Chat panel ────────────────────────────────────────────────────────────────

function showHomeOrSession() {
  if (state.activeSessionId) {
    renderActiveChatPanel();
  } else {
    renderHomePanel();
  }
}

function renderHomePanel() {
  const chatPanel = document.getElementById("wsChatPanel");
  if (!chatPanel) return;
  renderHomeScreen(chatPanel, state.agents, (agentId) => launchSession(agentId));
}

function renderActiveChatPanel() {
  const chatPanel = document.getElementById("wsChatPanel");
  if (!chatPanel) return;
  const sess = state.sessions.find((s) => s.sessionId === state.activeSessionId);
  if (!sess) {
    renderHomePanel();
    return;
  }
  renderChatPanel(chatPanel, sess, {
    onSend: onSendMessage,
    onRefChipClick,
    onAction: onComposerAction,
  });
}

async function onSendMessage(sessionId, text) {
  const sess = state.sessions.find((s) => s.sessionId === sessionId);
  if (!sess) return;

  // Optimistically append user message
  const userMsg = {
    role: "user",
    text,
    created_at: new Date().toISOString(),
    status: "queued",
  };
  sess.messages.push(userMsg);
  const chatPanel = document.getElementById("wsChatPanel");
  if (chatPanel && state.activeSessionId === sessionId) {
    appendMessageBubble(chatPanel, userMsg, onRefChipClick);
    setThinkingState(chatPanel, true, "Thinking…");
  }
  sess.thinking = true;
  updateTabDot(sessionId, "thinking");

  try {
    await api(`/api/agents/${encodeURIComponent(sess.agentId)}/thread`, {
      method: "POST",
      body: JSON.stringify({ text, run_id: sess.runId || "" }),
    });
  } catch (err) {
    const errMsg = { role: "system", text: `Send failed: ${err.message}`, created_at: new Date().toISOString() };
    sess.messages.push(errMsg);
    if (chatPanel && state.activeSessionId === sessionId) {
      appendMessageBubble(chatPanel, errMsg, onRefChipClick);
      setThinkingState(chatPanel, false, "");
    }
    sess.thinking = false;
    updateTabDot(sessionId, "idle");
  }
}

function onRefChipClick(ref) {
  openPanel({
    type: ref.type || "code",
    label: ref.label || ref.path || ref.url || "Panel",
    url: ref.url || "",
    path: ref.path || "",
    content: ref.content || "",
  });
}

function onComposerAction(sessionId, action) {
  if (action === "open-code") {
    openPanel({ type: "code", label: "Code", content: "" });
  } else if (action === "open-plan") {
    openPanel({ type: "plan", label: "Plan", content: "" });
  } else if (action === "open-browser") {
    openPanel({ type: "browser", label: "Browser", url: "" });
  } else if (action === "approve") {
    handleApprove(sessionId);
  }
}

async function handleApprove(sessionId) {
  const sess = state.sessions.find((s) => s.sessionId === sessionId);
  if (!sess || !sess.agentId) return;
  try {
    await api(`/api/agents/${encodeURIComponent(sess.agentId)}/thread/apply`, {
      method: "POST",
      body: JSON.stringify({ run_id: sess.runId || "", also_approve: true }),
    });
  } catch (err) {
    console.warn("Approve failed:", err.message);
  }
}

// ── Quick launch picker ───────────────────────────────────────────────────────

function openLaunchPicker() {
  // Simple inline prompt — a full keyboard palette can be added later
  const names = state.agents.map((a) => `${AGENT_ICONS[a.id] || "🤖"} ${a.name}`).join("\n");
  const choice = prompt(`Launch which agent?\n${names}\n\nType agent name or id:`);
  if (!choice) return;
  const match = state.agents.find(
    (a) => a.id.includes(choice.toLowerCase()) || a.name.toLowerCase().includes(choice.toLowerCase())
  );
  if (match) launchSession(match.id);
  else alert(`No agent matching "${choice}"`);
}

// ── Panel dock ────────────────────────────────────────────────────────────────

function openPanel({ type, label, url = "", path = "", content = "" }) {
  const id = `panel-${type}-${Date.now()}`;
  state.dockPanels.push({ id, type, label, url, path, content });
  state.activeDockId = id;
  showDock();
  renderDockTabs();
  renderActiveDockPanel();
  renderStatusBar();
}

function closePanel(id) {
  state.dockPanels = state.dockPanels.filter((p) => p.id !== id);
  if (state.activeDockId === id) {
    state.activeDockId = state.dockPanels[state.dockPanels.length - 1]?.id || null;
  }
  if (!state.dockPanels.length) {
    hideDock();
  } else {
    renderDockTabs();
    renderActiveDockPanel();
  }
  renderStatusBar();
}

function selectDockPanel(id) {
  state.activeDockId = id;
  renderDockTabs();
  renderActiveDockPanel();
}

function showDock() {
  const dock = document.getElementById("wsPanelDock");
  const handle = document.getElementById("dockResizeHandle");
  if (dock) dock.hidden = false;
  if (handle) handle.hidden = false;
}

function hideDock() {
  const dock = document.getElementById("wsPanelDock");
  const handle = document.getElementById("dockResizeHandle");
  if (dock) dock.hidden = true;
  if (handle) handle.hidden = true;
}

function toggleDock() {
  const dock = document.getElementById("wsPanelDock");
  if (!dock) return;
  if (dock.hidden) {
    if (state.dockPanels.length) showDock();
    else openPanel({ type: "browser", label: "Browser", url: "" });
  } else {
    hideDock();
    document.getElementById("dockResizeHandle").hidden = true;
  }
}

function renderDockTabs() {
  const tabStrip = document.getElementById("wsDockTabs");
  if (!tabStrip) return;

  tabStrip.innerHTML = `
    ${state.dockPanels.map((p) => {
      const active = p.id === state.activeDockId;
      return `
        <button type="button" role="tab"
                class="ws-dock-tab"
                aria-selected="${active}"
                data-dock-tab="${_esc(p.id)}"
                title="${_esc(p.label)}">
          <span class="ws-dock-tab-icon">${PANEL_ICONS[p.type] || "🗂"}</span>
          ${_esc(p.label.slice(0, 18))}
          <button type="button" class="ws-dock-tab-close"
                  data-close-dock="${_esc(p.id)}"
                  aria-label="Close ${_esc(p.label)}">✕</button>
        </button>
      `;
    }).join("")}
    <button type="button" class="ws-dock-collapse" id="wsDockCollapse" title="Hide panel dock">✕ Close</button>
  `;

  tabStrip.querySelectorAll("[data-dock-tab]").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      if (e.target.closest("[data-close-dock]")) return;
      selectDockPanel(btn.dataset.dockTab);
    });
  });
  tabStrip.querySelectorAll("[data-close-dock]").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      closePanel(btn.dataset.closeDock);
    });
  });
  tabStrip.querySelector("#wsDockCollapse")?.addEventListener("click", toggleDock);
}

function renderActiveDockPanel() {
  const dockBody = document.getElementById("wsDockBody");
  if (!dockBody) return;
  const panel = state.dockPanels.find((p) => p.id === state.activeDockId);
  if (!panel) {
    renderDockEmpty(dockBody);
    return;
  }
  renderDockPanel(dockBody, panel, {
    onUrlNavigate: (panelId, url) => {
      const p = state.dockPanels.find((x) => x.id === panelId);
      if (p) {
        p.url = url;
        p.label = url.slice(0, 24);
        renderDockTabs();
        renderActiveDockPanel();
      }
    },
  });
}

// ── Sidebar ───────────────────────────────────────────────────────────────────

async function renderSidebarPane() {
  const container = document.getElementById("sidebarContent");
  if (!container) return;
  const sidebar = document.getElementById("wsSidebar");
  const activeSession = state.sessions.find((s) => s.sessionId === state.activeSessionId);

  await renderSidebar(container, {
    agents: state.agents,
    activeAgentId: activeSession?.agentId || "",
    activeRunId: activeSession?.runId || "",
    isCollapsed: state.sidebarCollapsed,
    onSelectRun: (agentId, runId) => {
      // Find existing session or open one
      const existing = state.sessions.find((s) => s.agentId === agentId && s.runId === runId);
      if (existing) {
        selectSession(existing.sessionId);
      } else {
        // Reopen an archived session
        const agent = state.agents.find((a) => a.id === agentId);
        if (!agent) return;
        const sessionId = `${agentId}-${runId}`;
        state.sessions.push({
          sessionId, agentId, runId,
          label: agent.name,
          status: "idle",
          thinking: false,
          thinkingLabel: "",
          messages: [],
        });
        state.activeSessionId = sessionId;
        renderSessionTabs();
        renderActiveChatPanel();
      }
    },
    onLaunchAgent: (agentId) => launchSession(agentId),
    onToggleCollapse: () => {
      state.sidebarCollapsed = !state.sidebarCollapsed;
      st.setRailCollapsed(state.sidebarCollapsed);
      const sidebar = document.getElementById("wsSidebar");
      sidebar?.classList.toggle("collapsed", state.sidebarCollapsed);
      renderSidebarPane();
    },
  });

  if (sidebar) {
    sidebar.classList.toggle("collapsed", state.sidebarCollapsed);
  }
}

function toggleSidebar() {
  state.sidebarCollapsed = !state.sidebarCollapsed;
  st.setRailCollapsed(state.sidebarCollapsed);
  const sidebar = document.getElementById("wsSidebar");
  sidebar?.classList.toggle("collapsed", state.sidebarCollapsed);
  renderSidebarPane();
}

// ── Resize handles ────────────────────────────────────────────────────────────

function setupResizeHandles() {
  const sidebar = document.getElementById("wsSidebar");
  const sidebarHandle = document.getElementById("sidebarResizeHandle");
  const dock = document.getElementById("wsPanelDock");
  const dockHandle = document.getElementById("dockResizeHandle");

  if (sidebar && sidebarHandle) {
    setupResize(sidebarHandle, sidebar, "width", {
      min: 180,
      max: 420,
      cssVar: "--sidebar-w",
      reverse: false,
      onDone: (size) => {
        try { localStorage.setItem("ws_sidebar_w", String(size)); } catch { /* quota */ }
      },
    });
    // Restore saved width
    const saved = localStorage.getItem("ws_sidebar_w");
    if (saved) sidebar.style.width = `${Math.max(180, Math.min(420, Number(saved)))}px`;
  }

  if (dock && dockHandle) {
    setupResize(dockHandle, dock, "width", {
      min: 280,
      max: 700,
      cssVar: "--dock-w",
      reverse: true,
      onDone: (size) => {
        try { localStorage.setItem("ws_dock_w", String(size)); } catch { /* quota */ }
      },
    });
    const saved = localStorage.getItem("ws_dock_w");
    if (saved) dock.style.width = `${Math.max(280, Math.min(700, Number(saved)))}px`;
  }
}

// ── Keyboard shortcuts ────────────────────────────────────────────────────────

function setupKeyboardShortcuts() {
  document.addEventListener("keydown", (e) => {
    const ctrl = e.ctrlKey || e.metaKey;
    if (!ctrl) return;

    switch (e.key) {
      case "b":
        e.preventDefault();
        toggleSidebar();
        break;
      case "j":
        e.preventDefault();
        toggleDock();
        break;
      case "k":
        e.preventDefault();
        openLaunchPicker();
        break;
      case "w":
        e.preventDefault();
        if (state.activeSessionId) closeSession(state.activeSessionId);
        break;
      case "Tab":
        e.preventDefault();
        if (!state.sessions.length) break;
        const idx = state.sessions.findIndex((s) => s.sessionId === state.activeSessionId);
        const next = e.shiftKey
          ? (idx - 1 + state.sessions.length) % state.sessions.length
          : (idx + 1) % state.sessions.length;
        selectSession(state.sessions[next].sessionId);
        break;
    }
  });
}

// ── Status bar ────────────────────────────────────────────────────────────────

function renderStatusBar() {
  const agentEl = document.getElementById("statusAgents");
  const sessEl = document.getElementById("statusSessions");
  const panelEl = document.getElementById("statusPanels");
  if (agentEl) agentEl.textContent = `${state.agents.length} agent${state.agents.length !== 1 ? "s" : ""}`;
  if (sessEl) sessEl.textContent = `${state.sessions.length} session${state.sessions.length !== 1 ? "s" : ""}`;
  if (panelEl) panelEl.textContent = `${state.dockPanels.length} panel${state.dockPanels.length !== 1 ? "s" : ""}`;
}

function startClock() {
  const el = document.getElementById("statusClock");
  if (!el) return;
  function tick() {
    el.textContent = new Date().toLocaleTimeString(undefined, {
      hour: "2-digit", minute: "2-digit", second: "2-digit",
    });
  }
  tick();
  setInterval(tick, 1000);
}

// ── Health badge ──────────────────────────────────────────────────────────────

function updateHealth() {
  const online = state.agents.filter((a) => a.online || a.backend?.state === "ready").length;
  setHealthBadge(`${online}/${state.agents.length} online`, true);
}

function setHealthBadge(text, ok) {
  const el = document.getElementById("health");
  if (!el) return;
  el.textContent = text;
  el.className = ok ? "pill ok" : "pill bad";
}

// ── Settings modal ────────────────────────────────────────────────────────────

function setupSettingsModal() {
  const backdrop = document.getElementById("settingsBackdrop");
  const settingsBtn = document.getElementById("settingsBtn");
  const closeBtn = document.getElementById("settingsClose");
  const tokenInput = document.getElementById("tokenVisible");
  const saveBtn = document.getElementById("saveToken");

  if (tokenInput) tokenInput.value = getToken();

  settingsBtn?.addEventListener("click", () => {
    if (backdrop) backdrop.hidden = false;
  });
  closeBtn?.addEventListener("click", () => {
    if (backdrop) backdrop.hidden = true;
  });
  backdrop?.addEventListener("click", (e) => {
    if (e.target === backdrop) backdrop.hidden = true;
  });
  saveBtn?.addEventListener("click", () => {
    if (tokenInput) setToken(tokenInput.value);
    refreshAgents();
    if (backdrop) backdrop.hidden = true;
  });

  document.getElementById("refreshBtn")?.addEventListener("click", () => {
    refreshAgents().then(() => {
      renderLaunchBar();
      renderSidebarPane();
    });
  });
}
