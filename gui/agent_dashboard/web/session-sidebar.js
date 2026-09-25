/** Slide-in session rail — per-agent groups, 5 newest, archive-aware. */

import { api, esc } from "./api.js";
import { fetchAgents, stateLabel } from "./agents.js";
import * as session from "./state.js";

const NEWEST = 5;
const SHOW_ALL_LIMIT = 40;

/**
 * @param {object} run
 * @returns {string}
 */
export function sessionDisplayName(run) {
  const title = (run.title || run.request || "").trim();
  if (title) return title.length > 60 ? `${title.slice(0, 57)}…` : title;
  return run.run_id || "untitled";
}

/**
 * @param {object[]} runs
 * @param {string} agentId
 * @param {{ showArchived?: boolean, limit?: number }} opts
 */
export function filterSessions(runs, agentId, opts = {}) {
  const showArchived = opts.showArchived ?? session.getShowArchived();
  const limit = opts.limit ?? SHOW_ALL_LIMIT;
  let list = Array.isArray(runs) ? runs.slice() : [];
  list.sort((a, b) => {
    const ta = String(a.updated_at || a.created_at || a.run_id || "");
    const tb = String(b.updated_at || b.created_at || b.run_id || "");
    return tb.localeCompare(ta);
  });
  if (!showArchived) {
    list = list.filter((r) => !session.isRunArchived(agentId, r.run_id));
  }
  return list.slice(0, limit);
}

/**
 * @param {HTMLElement} root
 * @param {{
 *   selectedAgentId: string,
 *   selectedRunId: string,
 *   onSelectAgent: (id: string) => void | Promise<void>,
 *   onSelectRun: (agentId: string, runId: string) => void | Promise<void>,
 *   onBackend: (agentId: string, action: string) => void | Promise<void>,
 *   agents?: object[],
 * }} ctx
 */
export async function renderSessionSidebar(root, ctx) {
  if (!root) return [];

  const agents = ctx.agents || (await fetchAgents());
  const collapsed = session.getRailCollapsed();
  const openMap = session.getRailAgentOpen();
  const showArchived = session.getShowArchived();

  function isAgentOpen(id) {
    if (Object.prototype.hasOwnProperty.call(openMap, id)) return Boolean(openMap[id]);
    if (ctx.selectedAgentId) return id === ctx.selectedAgentId;
    return Boolean(agents[0] && agents[0].id === id);
  }

  const showAllMap = root._showAllMap || (root._showAllMap = {});

  const railEl = root.closest(".session-rail") || root;
  railEl.classList.toggle("session-rail-collapsed", collapsed);
  root.classList.toggle("session-rail-collapsed", collapsed);

  const header = `
    <div class="session-rail-header">
      <h2>Session history</h2>
      <button type="button" class="session-rail-toggle" data-rail-toggle title="${collapsed ? "Expand" : "Collapse"} session rail">${collapsed ? "»" : "«"}</button>
    </div>
    <div class="agent-peer-switcher" role="tablist" aria-label="Agents">
      ${agents
        .map((a) => {
          const b = a.backend || {};
          const ready = a.online || b.state === "ready";
          const selected = a.id === ctx.selectedAgentId;
          return `<button type="button" role="tab" class="agent-peer${selected ? " active" : ""}" data-peer-agent="${esc(a.id)}" aria-selected="${selected}" title="${esc(a.description || a.name)}">
            <span class="dot ${ready ? "on" : "off"}"></span>
            <span class="agent-peer-label">${esc(a.name)}</span>
          </button>`;
        })
        .join("")}
    </div>
    <p class="muted small session-rail-one">Open selects your one working session.</p>
    <label class="session-rail-archived muted small">
      <input type="checkbox" data-show-archived ${showArchived ? "checked" : ""} />
      Show archived
    </label>`;

  if (!agents.length) {
    root.innerHTML = `${header}<p class="muted">No agents registered. Edit config/agents.json.</p>`;
    wireRailChrome(root, ctx);
    return agents;
  }

  const sections = [];
  for (const a of agents) {
    const b = a.backend || {};
    const ready = a.online || b.state === "ready";
    const startable = !!b.startable;
    const open = isAgentOpen(a.id);
    const label = stateLabel(b);
    const showRestart =
      startable &&
      (b.state === "unauthorized" ||
        b.state === "ready" ||
        b.state === "degraded" ||
        b.state === "down");
    const showStop = startable && (b.managed || b.online);

    let runsHtml = "";
    if (open) {
      let runs = [];
      try {
        if (!startable || b.state === "ready") {
          runs = await api(`/api/agents/${encodeURIComponent(a.id)}/runs?limit=40`);
        } else {
          runsHtml = `<p class="muted small session-rail-hint">${esc(b.message || "Server not ready — start work will auto-start.")}</p>`;
        }
      } catch (err) {
        runsHtml = `<p class="bad small">${esc(err.message)}</p>`;
      }

      if (!runsHtml) {
        const showAll = Boolean(showAllMap[a.id]);
        const filtered = filterSessions(runs, a.id, {
          showArchived,
          limit: SHOW_ALL_LIMIT,
        });
        const visible = showAll ? filtered : filtered.slice(0, NEWEST);
        const more = filtered.length > NEWEST && !showAll;

        if (!visible.length) {
          runsHtml = `<p class="muted small">No sessions yet.</p>`;
        } else {
          runsHtml = `<ul class="session-list">${visible
            .map((r) => {
              const archived = session.isRunArchived(a.id, r.run_id);
              const active =
                a.id === ctx.selectedAgentId && r.run_id === ctx.selectedRunId;
              const name = sessionDisplayName(r);
              return `<li class="session-row${active ? " active" : ""}${archived ? " archived" : ""}">
                <button type="button" class="session-row-main" data-select-run data-agent="${esc(a.id)}" data-run="${esc(r.run_id)}" title="${esc(name)}">
                  <span class="session-name">${esc(name)}</span>
                  <span class="muted small session-status">${esc(r.status || "")}</span>
                </button>
                <button type="button" class="session-open-btn" data-select-run data-agent="${esc(a.id)}" data-run="${esc(r.run_id)}" title="Set as the one active session">Open</button>
                <button type="button" class="session-archive-btn" data-archive="${archived ? "unarchive" : "archive"}" data-agent="${esc(a.id)}" data-run="${esc(r.run_id)}" title="${archived ? "Unarchive" : "Archive"}">${archived ? "↩" : "Archive"}</button>
              </li>`;
            })
            .join("")}</ul>`;
          if (more) {
            runsHtml += `<button type="button" class="session-show-all" data-show-all="${esc(a.id)}">Show all (${filtered.length})</button>`;
          } else if (showAll && filtered.length > NEWEST) {
            runsHtml += `<button type="button" class="session-show-all" data-show-less="${esc(a.id)}">Show fewer</button>`;
          }
        }
      }
    }

    sections.push(`
      <div class="session-agent ${open ? "open" : ""}" data-agent-block="${esc(a.id)}">
        <div class="session-agent-head">
          <button type="button" class="session-agent-toggle" data-toggle-agent="${esc(a.id)}" aria-expanded="${open}">
            <span class="dot ${ready ? "on" : "off"}"></span>
            <span class="session-agent-name">${esc(a.name)}</span>
            ${label ? `<span class="muted small">${esc(label)}</span>` : ""}
            <span class="session-chevron" aria-hidden="true">${open ? "▾" : "▸"}</span>
          </button>
          <div class="session-agent-overflow">
            <button type="button" class="session-overflow-btn" data-overflow="${esc(a.id)}" title="Server actions" aria-haspopup="true">⋯</button>
            <div class="session-overflow-menu" hidden data-overflow-menu="${esc(a.id)}">
              ${showRestart ? `<button type="button" data-be="restart" data-id="${esc(a.id)}">Restart</button>` : ""}
              ${showStop ? `<button type="button" data-be="stop" data-id="${esc(a.id)}">Stop</button>` : ""}
              ${!showRestart && !showStop ? `<span class="muted small">No server actions</span>` : ""}
            </div>
          </div>
        </div>
        <div class="session-agent-body" ${open ? "" : "hidden"}>
          ${runsHtml}
        </div>
      </div>`);
  }

  root.innerHTML = `${header}<div class="session-rail-body">${sections.join("")}</div>`;
  wireRailChrome(root, ctx);
  return agents;
}

function wireRailChrome(root, ctx) {
  root.querySelector("[data-rail-toggle]")?.addEventListener("click", () => {
    session.setRailCollapsed(!session.getRailCollapsed());
    renderSessionSidebar(root, ctx);
  });

  root.querySelectorAll("[data-peer-agent]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-peer-agent");
      session.setRailAgentOpen(id, true);
      await ctx.onSelectAgent(id);
      await renderSessionSidebar(root, {
        ...ctx,
        selectedAgentId: id,
      });
    });
  });

  root.querySelector("[data-show-archived]")?.addEventListener("change", (e) => {
    session.setShowArchived(e.target.checked);
    renderSessionSidebar(root, ctx);
  });

  root.querySelectorAll("[data-toggle-agent]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-toggle-agent");
      const map = session.getRailAgentOpen();
      const wasOpen = Object.prototype.hasOwnProperty.call(map, id)
        ? Boolean(map[id])
        : id === ctx.selectedAgentId || (!ctx.selectedAgentId && (ctx.agents?.[0]?.id === id));
      session.setRailAgentOpen(id, !wasOpen);
      await ctx.onSelectAgent(id);
      await renderSessionSidebar(root, {
        ...ctx,
        selectedAgentId: id,
      });
    });
  });

  root.querySelectorAll("[data-select-run]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const agentId = btn.getAttribute("data-agent");
      const runId = btn.getAttribute("data-run");
      await ctx.onSelectAgent(agentId);
      await ctx.onSelectRun(agentId, runId);
    });
  });

  root.querySelectorAll("[data-archive]").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const agentId = btn.getAttribute("data-agent");
      const runId = btn.getAttribute("data-run");
      const action = btn.getAttribute("data-archive");
      if (action === "archive") session.archiveRun(agentId, runId);
      else session.unarchiveRun(agentId, runId);
      renderSessionSidebar(root, ctx);
    });
  });

  root.querySelectorAll("[data-show-all]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = btn.getAttribute("data-show-all");
      root._showAllMap = root._showAllMap || {};
      root._showAllMap[id] = true;
      renderSessionSidebar(root, ctx);
    });
  });

  root.querySelectorAll("[data-show-less]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = btn.getAttribute("data-show-less");
      root._showAllMap = root._showAllMap || {};
      root._showAllMap[id] = false;
      renderSessionSidebar(root, ctx);
    });
  });

  function hideOverflowMenus() {
    root.querySelectorAll("[data-overflow-menu]").forEach((m) => {
      m.hidden = true;
    });
  }

  root.querySelectorAll("[data-overflow]").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      const id = btn.getAttribute("data-overflow");
      const menu = root.querySelector(`[data-overflow-menu="${CSS.escape(id)}"]`);
      if (!menu) return;
      const willOpen = menu.hidden;
      hideOverflowMenus();
      menu.hidden = !willOpen;
    });
  });

  root.querySelectorAll("[data-be]").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      e.preventDefault();
      e.stopPropagation();
      btn.disabled = true;
      try {
        await ctx.onBackend(btn.dataset.id, btn.dataset.be);
      } finally {
        btn.disabled = false;
        hideOverflowMenus();
      }
    });
  });

  // One document-level dismiss pair per root (re-render must not stack listeners).
  if (root._overflowDismissClick) {
    document.removeEventListener("click", root._overflowDismissClick);
    document.removeEventListener("keydown", root._overflowDismissKey);
  }
  root._overflowDismissClick = (e) => {
    if (e.target.closest?.("[data-overflow]") || e.target.closest?.("[data-overflow-menu]")) {
      return;
    }
    hideOverflowMenus();
  };
  root._overflowDismissKey = (e) => {
    if (e.key === "Escape") hideOverflowMenus();
  };
  document.addEventListener("click", root._overflowDismissClick);
  document.addEventListener("keydown", root._overflowDismissKey);
}
