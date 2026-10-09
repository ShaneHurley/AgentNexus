/**
 * sidebar.js — Workspace left sidebar.
 *
 * Sections:
 *   1. Agent peer switcher (one button per registered agent, with status dot)
 *   2. Session list (runs grouped by agent, collapsible)
 *   3. Daily Tasks (localStorage-persisted checklist)
 *
 * All session data comes from the existing /api/agents/{id}/runs endpoint.
 * Daily tasks are stored locally under key ws_tasks.
 */

import { api } from "./api.js";
import { fetchAgents, stateLabel } from "./agents.js";

const _esc = (s) =>
  String(s == null ? "" : s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );

const TASK_KEY = "ws_tasks";
const AGENT_ICONS = {
  "daily-coder": "⚙️",
  "research-forge": "🔬",
  "daily-task": "📋",
};

// ── Public API ────────────────────────────────────────────────────────────────

/**
 * Render the complete sidebar into `container`.
 *
 * @param {HTMLElement} container  The #sidebarContent element.
 * @param {{
 *   agents: object[],
 *   activeAgentId: string,
 *   activeRunId: string,
 *   onSelectRun: (agentId: string, runId: string) => void,
 *   onLaunchAgent: (agentId: string) => void,
 *   onToggleCollapse: () => void,
 *   isCollapsed: boolean,
 * }} ctx
 */
export async function renderSidebar(container, ctx) {
  const { agents, activeAgentId, activeRunId, isCollapsed } = ctx;

  if (isCollapsed) {
    renderCollapsedSidebar(container, agents, ctx);
    return;
  }

  // Build session groups for each agent
  const groups = await buildAgentGroups(agents, activeAgentId, activeRunId);

  const tasks = loadTasks();

  container.innerHTML = `
    <!-- Header -->
    <div class="ws-sidebar-header">
      <span class="ws-sidebar-title">Sessions</span>
      <button type="button" class="ws-icon-btn" id="sbCollapseBtn" title="Collapse sidebar">«</button>
    </div>

    <!-- Agent peer switcher -->
    <div class="ws-peer-switcher" role="tablist" aria-label="Agents">
      ${agents.map((a) => buildPeerBtn(a, activeAgentId)).join("")}
    </div>

    <!-- Session groups -->
    <div class="ws-session-groups" id="sbSessionGroups">
      ${groups.join("")}
    </div>

    <!-- Daily tasks -->
    <div class="ws-sidebar-header" style="margin-top:12px;border-top:1px solid var(--line);padding-top:10px">
      <span class="ws-sidebar-title">Daily Tasks</span>
      <button type="button" class="ws-icon-btn" id="sbAddTaskBtn" title="Add task" style="font-size:18px;color:var(--teal)">+</button>
    </div>
    <ul class="ws-task-list" id="sbTaskList">
      ${buildTaskListHTML(tasks)}
    </ul>
    <div class="ws-task-input-row" id="sbTaskInputRow" style="display:none;padding:4px 12px 8px">
      <input type="text" id="sbNewTaskInput" placeholder="New task…"
             style="width:100%;font-size:12px;border-radius:6px;padding:6px 10px;
                    background:var(--bg);color:var(--text);border:1px solid var(--line);" />
    </div>
  `;

  wireSidebarEvents(container, ctx, tasks);
}

// ── Collapsed mode ────────────────────────────────────────────────────────────

function renderCollapsedSidebar(container, agents, ctx) {
  container.innerHTML = `
    <div style="display:flex;flex-direction:column;align-items:center;gap:8px;padding:8px 4px;">
      <button type="button" class="ws-icon-btn" id="sbExpandBtn" title="Expand sidebar" style="font-size:16px">»</button>
      ${agents.map((a) => {
        const ready = a.online || a.backend?.state === "ready";
        return `<button type="button" class="ws-collapsed-agent-btn" data-launch="${_esc(a.id)}"
                        title="${_esc(a.name)}" style="font-size:18px;width:36px;height:36px;
                        border-radius:8px;border:1px solid ${a.id === ctx.activeAgentId ? "var(--teal)" : "var(--line)"};
                        background:${a.id === ctx.activeAgentId ? "var(--teal-dim)" : "transparent"};
                        cursor:pointer;position:relative;">
                  ${AGENT_ICONS[a.id] || "🤖"}
                  <span style="position:absolute;bottom:2px;right:2px;width:6px;height:6px;
                               border-radius:50%;background:${ready ? "var(--ok)" : "var(--muted)"};"></span>
                </button>`;
      }).join("")}
    </div>
  `;

  container.querySelector("#sbExpandBtn")?.addEventListener("click", ctx.onToggleCollapse);
  container.querySelectorAll("[data-launch]").forEach((btn) => {
    btn.addEventListener("click", () => ctx.onLaunchAgent(btn.dataset.launch));
  });
}

// ── Session group builder ─────────────────────────────────────────────────────

async function buildAgentGroups(agents, activeAgentId, activeRunId) {
  const groups = [];
  for (const a of agents) {
    let runs = [];
    let errorMsg = "";
    try {
      if (!a.backend?.startable || a.backend?.state === "ready" || !a.backend) {
        runs = await api(`/api/agents/${encodeURIComponent(a.id)}/runs?limit=20`);
      }
    } catch (err) {
      errorMsg = err.message;
    }

    const isActive = a.id === activeAgentId;
    const runsHTML = errorMsg
      ? `<p class="muted small" style="padding:4px 10px">${_esc(errorMsg)}</p>`
      : buildRunListHTML(runs, a.id, activeAgentId, activeRunId);

    groups.push(`
      <div class="ws-agent-group" data-group-id="${_esc(a.id)}">
        <button type="button" class="ws-agent-group-toggle"
                data-toggle-group="${_esc(a.id)}"
                aria-expanded="${isActive ? "true" : "false"}">
          <span class="dot ${(a.online || a.backend?.state === "ready") ? "on" : "off"}"></span>
          <span style="font-size:13px">${AGENT_ICONS[a.id] || "🤖"}</span>
          <span class="ws-agent-group-name">${_esc(a.name)}</span>
          ${a.backend?.state ? `<span class="muted small">${_esc(stateLabel(a.backend))}</span>` : ""}
          <span class="session-chevron" aria-hidden="true">${isActive ? "▾" : "▸"}</span>
        </button>
        <div class="ws-agent-group-body" ${isActive ? "" : "hidden"}>
          ${runsHTML}
        </div>
      </div>
    `);
  }
  return groups;
}

function buildRunListHTML(runs, agentId, activeAgentId, activeRunId) {
  if (!runs.length) {
    return `<p class="muted small" style="padding:4px 10px 8px">No sessions yet — launch one above.</p>`;
  }
  const sorted = [...runs].sort((a, b) => {
    const ta = String(a.updated_at || a.created_at || "");
    const tb = String(b.updated_at || b.created_at || "");
    return tb.localeCompare(ta);
  }).slice(0, 15);

  return `<ul class="ws-run-list">
    ${sorted.map((r) => {
      const isActive = agentId === activeAgentId && r.run_id === activeRunId;
      const title = (r.title || r.request || r.run_id || "").slice(0, 55);
      return `<li class="ws-run-row${isActive ? " active" : ""}">
        <button type="button" class="ws-run-btn"
                data-select-run data-agent="${_esc(agentId)}" data-run="${_esc(r.run_id)}"
                title="${_esc(title || r.run_id)}">
          <span class="ws-run-name">${_esc(title || r.run_id)}</span>
          <span class="muted small ws-run-status">${_esc(r.status || "")}</span>
        </button>
      </li>`;
    }).join("")}
  </ul>`;
}

// ── Peer switcher ─────────────────────────────────────────────────────────────

function buildPeerBtn(agent, activeAgentId) {
  const ready = agent.online || agent.backend?.state === "ready";
  const active = agent.id === activeAgentId;
  return `
    <button type="button" role="tab"
            class="ws-peer-btn${active ? " active" : ""}"
            data-peer-agent="${_esc(agent.id)}"
            aria-selected="${active}"
            title="${_esc(agent.description || agent.name)}">
      <span class="dot ${ready ? "on" : "off"}"></span>
      <span class="ws-peer-label">${_esc(agent.name)}</span>
    </button>
  `;
}

// ── Daily tasks ───────────────────────────────────────────────────────────────

export function loadTasks() {
  try {
    const raw = localStorage.getItem(TASK_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function saveTasks(tasks) {
  try {
    localStorage.setItem(TASK_KEY, JSON.stringify(tasks));
  } catch { /* quota — ignore */ }
}

export function addTask(label) {
  const tasks = loadTasks();
  tasks.push({ id: crypto.randomUUID(), label, done: false, created_at: new Date().toISOString() });
  saveTasks(tasks);
  return tasks;
}

export function toggleTask(id) {
  const tasks = loadTasks();
  const t = tasks.find((t) => t.id === id);
  if (t) t.done = !t.done;
  saveTasks(tasks);
  return tasks;
}

export function deleteTask(id) {
  const tasks = loadTasks().filter((t) => t.id !== id);
  saveTasks(tasks);
  return tasks;
}

function buildTaskListHTML(tasks) {
  if (!tasks.length) {
    return `<li class="muted small" style="padding:4px 12px 8px">No tasks yet. Click + to add one.</li>`;
  }
  return tasks.map((t) => `
    <li class="ws-task-row${t.done ? " done" : ""}">
      <input type="checkbox" ${t.done ? "checked" : ""} data-task-toggle="${_esc(t.id)}"
             aria-label="Mark done" />
      <span class="ws-task-label">${_esc(t.label)}</span>
      <button type="button" class="ws-icon-btn" data-task-delete="${_esc(t.id)}"
              title="Delete task" style="margin-left:auto;flex-shrink:0;opacity:0.4;font-size:12px">✕</button>
    </li>
  `).join("");
}

// ── Event wiring ──────────────────────────────────────────────────────────────

function wireSidebarEvents(container, ctx, initialTasks) {
  // Collapse button
  container.querySelector("#sbCollapseBtn")?.addEventListener("click", ctx.onToggleCollapse);

  // Agent peer switcher
  container.querySelectorAll("[data-peer-agent]").forEach((btn) => {
    btn.addEventListener("click", () => {
      ctx.onLaunchAgent(btn.dataset.peerAgent);
    });
  });

  // Group toggles
  container.querySelectorAll("[data-toggle-group]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = btn.dataset.toggleGroup;
      const body = container.querySelector(`.ws-agent-group[data-group-id="${CSS.escape(id)}"] .ws-agent-group-body`);
      const expanded = btn.getAttribute("aria-expanded") === "true";
      btn.setAttribute("aria-expanded", expanded ? "false" : "true");
      btn.querySelector(".session-chevron").textContent = expanded ? "▸" : "▾";
      if (body) body.hidden = expanded;
    });
  });

  // Run selection
  container.querySelectorAll("[data-select-run]").forEach((btn) => {
    btn.addEventListener("click", () => {
      ctx.onSelectRun(btn.dataset.agent, btn.dataset.run);
    });
  });

  // Add task
  const addBtn = container.querySelector("#sbAddTaskBtn");
  const inputRow = container.querySelector("#sbTaskInputRow");
  const newTaskInput = container.querySelector("#sbNewTaskInput");

  addBtn?.addEventListener("click", () => {
    const hidden = inputRow.style.display === "none";
    inputRow.style.display = hidden ? "block" : "none";
    if (hidden) newTaskInput?.focus();
  });

  newTaskInput?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      const label = newTaskInput.value.trim();
      if (!label) return;
      addTask(label);
      newTaskInput.value = "";
      inputRow.style.display = "none";
      // Re-render task list
      const taskList = container.querySelector("#sbTaskList");
      if (taskList) taskList.innerHTML = buildTaskListHTML(loadTasks());
      wireTaskEvents(container, ctx);
    }
    if (e.key === "Escape") {
      inputRow.style.display = "none";
    }
  });

  wireTaskEvents(container, ctx);
}

function wireTaskEvents(container, _ctx) {
  container.querySelectorAll("[data-task-toggle]").forEach((cb) => {
    cb.addEventListener("change", () => {
      toggleTask(cb.dataset.taskToggle);
      const row = cb.closest(".ws-task-row");
      if (row) row.classList.toggle("done", cb.checked);
    });
  });

  container.querySelectorAll("[data-task-delete]").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      deleteTask(btn.dataset.taskDelete);
      const taskList = container.querySelector("#sbTaskList");
      if (taskList) taskList.innerHTML = buildTaskListHTML(loadTasks());
      wireTaskEvents(container, _ctx);
    });
  });
}
