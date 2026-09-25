/** Composer options — Agent / Model / Context / Thinking / Subagents via side drawer. */

import { api, esc } from "./api.js";
import * as session from "./state.js";
import { attachSlashPalette } from "./slash-palette.js";

const CONTEXT_OPTIONS = [
  { id: "default", label: "Default" },
  { id: "focused", label: "Focused" },
  { id: "broad", label: "Broad" },
];

const THINKING_OPTIONS = [
  { id: "standard", label: "Standard" },
  { id: "careful", label: "Careful" },
  { id: "fast", label: "Fast" },
];

const DRAWER_TITLES = {
  agent: "Agent",
  model: "Model",
  context: "Context",
  thinking: "Thinking",
  subagents: "Force subagents",
};

/**
 * @param {HTMLElement} host
 * @param {{
 *   agents: object[],
 *   agentId: string,
 *   onAgentChange: (id: string) => void | Promise<void>,
 *   onProviderChange?: (provider: string) => void | Promise<void>,
 * }} ctx
 */
export function mountComposerPicker(host, ctx) {
  if (!host) return { destroy() {}, getValues() { return {}; }, sync() {} };

  let openDrawer = null;
  let onDocClick = null;
  let onKey = null;
  let slashApi = null;
  let runtimes = [];
  let paletteSubagents = [];
  let modelBlockedReason = "";

  const state = {
    agentId: ctx.agentId || "",
    model: session.getProvider() || "mock",
    context: session.getComposerContext(),
    thinking: session.getComposerThinking(),
    forced: session.getForcedSubagents(ctx.agentId || "") || [],
  };

  function agentName(id) {
    const a = (ctx.agents || []).find((x) => x.id === id);
    return a?.name || id || "Agent";
  }

  function modelLabel(id) {
    return runtimes.find((m) => m.id === id)?.label || id;
  }

  function contextLabel(id) {
    return CONTEXT_OPTIONS.find((c) => c.id === id)?.label || id;
  }

  function thinkingLabel(id) {
    return THINKING_OPTIONS.find((t) => t.id === id)?.label || id;
  }

  function currentAgent() {
    return (ctx.agents || []).find((a) => a.id === state.agentId);
  }

  function isDailyCoder() {
    return state.agentId === "daily-coder";
  }

  function availableModels() {
    const bridges = currentAgent()?.backend?.bridges || { command: false, http: false };
    return (runtimes.length ? runtimes : [{ id: "mock", label: "mock", configured: true, live: false }]).filter(
      (m) => {
        if (m.id === "mock" || m.id === "local") return true;
        if (m.id === "command") return Boolean(bridges.command) && m.configured !== false;
        if (m.id === "http") return Boolean(bridges.http) && m.configured !== false;
        return m.configured !== false;
      }
    );
  }

  function updateModelGate() {
    const models = availableModels();
    const selected = models.find((m) => m.id === state.model);
    modelBlockedReason = "";
    if (isDailyCoder() && state.model !== "mock" && state.model !== "local") {
      if (!selected) {
        modelBlockedReason = "Selected provider is not configured — set an API key in APIs & abilities → Setup.";
      }
    }
    const btn = host.querySelector("#startBtn");
    const gate = host.querySelector("#modelGateMsg");
    if (btn) btn.disabled = Boolean(modelBlockedReason) || !state.agentId;
    if (gate) {
      if (modelBlockedReason) {
        gate.hidden = false;
        gate.innerHTML = `${esc(modelBlockedReason)} <a href="#/apis">Open Setup</a>`;
      } else {
        gate.hidden = true;
        gate.textContent = "";
      }
    }
  }

  async function loadRuntimes() {
    try {
      const data = await api("/api/setup/runtimes");
      runtimes = Array.isArray(data.providers) ? data.providers : [];
    } catch {
      runtimes = [
        { id: "mock", label: "mock", configured: true, live: false },
        { id: "local", label: "local / Ollama", configured: true, live: true },
      ];
    }
    const models = availableModels();
    if (!models.some((m) => m.id === state.model)) {
      state.model = models[0]?.id || "mock";
      session.setProvider(state.model);
    }
  }

  async function loadPaletteSubagents() {
    try {
      const data = await api(
        `/api/setup/palette?agent_id=${encodeURIComponent(state.agentId || "daily-coder")}`
      );
      paletteSubagents = Array.isArray(data.subagents) ? data.subagents : [];
    } catch {
      paletteSubagents = [];
    }
  }

  function closeDrawer() {
    openDrawer = null;
    const drawer = host.querySelector(".composer-drawer");
    const backdrop = host.querySelector(".composer-drawer-backdrop");
    if (drawer) {
      drawer.classList.remove("open");
      drawer.setAttribute("aria-hidden", "true");
      drawer.hidden = true;
    }
    if (backdrop) {
      backdrop.classList.remove("open");
      backdrop.hidden = true;
    }
    host.querySelectorAll(".composer-drawer-trigger").forEach((el) => {
      el.setAttribute("aria-expanded", "false");
    });
  }

  function openDrawerPanel(drawerId) {
    const drawer = host.querySelector(".composer-drawer");
    const backdrop = host.querySelector(".composer-drawer-backdrop");
    const body = host.querySelector(".composer-drawer-body");
    const title = host.querySelector(".composer-drawer-title");
    if (!drawer || !body || !title) return;

    openDrawer = drawerId;
    title.textContent = DRAWER_TITLES[drawerId] || drawerId;
    body.innerHTML = drawerContent(drawerId);
    wireDrawerOptions();

    drawer.hidden = false;
    drawer.setAttribute("aria-hidden", "false");
    void drawer.offsetWidth;
    drawer.classList.add("open");
    if (backdrop) {
      backdrop.hidden = false;
      backdrop.classList.add("open");
    }
    host.querySelectorAll(".composer-drawer-trigger").forEach((el) => {
      el.setAttribute(
        "aria-expanded",
        el.getAttribute("data-drawer") === drawerId ? "true" : "false"
      );
    });
  }

  function toggleDrawer(drawerId) {
    if (openDrawer === drawerId) {
      closeDrawer();
      return;
    }
    openDrawerPanel(drawerId);
  }

  function drawerContent(drawerId) {
    const agents = ctx.agents || [];

    if (drawerId === "agent") {
      const items = agents
        .map(
          (a) =>
            `<button type="button" class="composer-option${a.id === state.agentId ? " selected" : ""}" data-pick-agent="${esc(a.id)}">${esc(a.name)}</button>`
        )
        .join("");
      return items || '<span class="muted small">No agents</span>';
    }

    if (drawerId === "model") {
      const models = availableModels();
      if (!models.length) {
        return `<p class="muted small">No configured providers. <a href="#/apis">Open Setup</a></p>`;
      }
      return models
        .map(
          (m) =>
            `<button type="button" class="composer-option${m.id === state.model ? " selected" : ""}" data-pick-model="${esc(m.id)}">${esc(m.label)}${m.live ? " · live" : ""}${m.configured === false ? " · not configured" : ""}</button>`
        )
        .join("");
    }

    if (drawerId === "context") {
      const contextItems = CONTEXT_OPTIONS.map(
        (c) =>
          `<button type="button" class="composer-option${c.id === state.context ? " selected" : ""}" data-pick-context="${esc(c.id)}">${esc(c.label)}</button>`
      ).join("");
      const showRepo = isDailyCoder();
      return `
        <p class="muted small composer-pref-note">UI preference</p>
        ${contextItems}
        <div class="composer-repo-field"${showRepo ? "" : " hidden"}>
          <label class="muted small" for="workRepo">Repo path</label>
          <input id="workRepo" placeholder="local repo path (coder)" />
        </div>`;
    }

    if (drawerId === "thinking") {
      const thinkingItems = THINKING_OPTIONS.map(
        (t) =>
          `<button type="button" class="composer-option${t.id === state.thinking ? " selected" : ""}" data-pick-thinking="${esc(t.id)}">${esc(t.label)}</button>`
      ).join("");
      return `
        <p class="muted small composer-pref-note">UI preference</p>
        ${thinkingItems}`;
    }

    if (drawerId === "subagents") {
      if (!paletteSubagents.length) {
        return `<p class="muted small">No subagents listed for this actor. Type <code>/</code> in the prompt for skills.</p>`;
      }
      return `
        <p class="muted small">Force these for this session (stored with the run).</p>
        ${paletteSubagents
          .map((s) => {
            const on = state.forced.includes(s.id);
            return `<button type="button" class="composer-option${on ? " selected forced-on" : ""}" data-toggle-forced="${esc(s.id)}">${esc(s.label || s.id)}</button>`;
          })
          .join("")}
        <button type="button" class="composer-option" data-clear-forced>Clear all</button>`;
    }

    return "";
  }

  function wireDrawerOptions() {
    host.querySelectorAll("[data-pick-agent]").forEach((btn) => {
      btn.addEventListener("click", async (e) => {
        e.preventDefault();
        e.stopPropagation();
        const id = btn.getAttribute("data-pick-agent");
        state.agentId = id;
        state.forced = session.getForcedSubagents(id);
        closeDrawer();
        await loadPaletteSubagents();
        render();
        await slashApi?.refresh?.();
        await ctx.onAgentChange?.(id);
      });
    });

    host.querySelectorAll("[data-pick-model]").forEach((btn) => {
      btn.addEventListener("click", async (e) => {
        e.preventDefault();
        e.stopPropagation();
        const id = btn.getAttribute("data-pick-model");
        state.model = id;
        session.setProvider(id);
        closeDrawer();
        render();
        await ctx.onProviderChange?.(id);
      });
    });

    host.querySelectorAll("[data-pick-context]").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        const id = btn.getAttribute("data-pick-context");
        state.context = id;
        session.setComposerContext(id);
        closeDrawer();
        render();
      });
    });

    host.querySelectorAll("[data-pick-thinking]").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        const id = btn.getAttribute("data-pick-thinking");
        state.thinking = id;
        session.setComposerThinking(id);
        closeDrawer();
        render();
      });
    });

    host.querySelectorAll("[data-toggle-forced]").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        const id = btn.getAttribute("data-toggle-forced");
        const set = new Set(state.forced);
        if (set.has(id)) set.delete(id);
        else set.add(id);
        state.forced = [...set];
        session.setForcedSubagents(state.agentId, state.forced);
        openDrawerPanel("subagents");
      });
    });

    host.querySelector("[data-clear-forced]")?.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      state.forced = [];
      session.setForcedSubagents(state.agentId, []);
      openDrawerPanel("subagents");
    });

    host.querySelector(".composer-repo-field")?.addEventListener("click", (e) => {
      e.stopPropagation();
    });
  }

  function forcedChipLabel() {
    if (!state.forced.length) return "None";
    if (state.forced.length === 1) return state.forced[0];
    return `${state.forced.length} selected`;
  }

  function render() {
    const live = state.model && state.model !== "mock";
    const wasOpen = openDrawer;
    const prompt = host.querySelector("#workRequest")?.value;
    const repo = host.querySelector("#workRepo")?.value;

    host.innerHTML = `
      <div class="composer-shell">
        <div class="composer-main">
          <div class="composer-prompt-row">
            <div class="composer-prompt-wrap">
              <textarea id="workRequest" class="composer-prompt" rows="3" placeholder="Pitch your idea… (type / for skills &amp; subagents)"></textarea>
            </div>
            <button type="button" id="startBtn" class="primary composer-send">Start work</button>
          </div>
          <p id="modelGateMsg" class="warn small" hidden></p>
          <div class="composer-triggers" role="toolbar" aria-label="Composer options">
            <button type="button" class="composer-drawer-trigger" data-drawer="agent" aria-expanded="false" aria-haspopup="dialog">
              <span class="chip-kind">Agent</span>
              <span class="chip-value">${esc(agentName(state.agentId))}</span>
            </button>
            <button type="button" class="composer-drawer-trigger"${isDailyCoder() ? "" : " hidden"} data-drawer="model" aria-expanded="false" aria-haspopup="dialog">
              <span class="chip-kind">Model</span>
              <span class="chip-value">${esc(modelLabel(state.model))}</span>
            </button>
            <button type="button" class="composer-drawer-trigger" data-drawer="context" aria-expanded="false" aria-haspopup="dialog" title="UI preference until runtimes support context">
              <span class="chip-kind">Context</span>
              <span class="chip-value">${esc(contextLabel(state.context))}</span>
            </button>
            <button type="button" class="composer-drawer-trigger" data-drawer="thinking" aria-expanded="false" aria-haspopup="dialog" title="UI preference until runtimes support thinking">
              <span class="chip-kind">Thinking</span>
              <span class="chip-value">${esc(thinkingLabel(state.thinking))}</span>
            </button>
            <button type="button" class="composer-drawer-trigger" data-drawer="subagents" aria-expanded="false" aria-haspopup="dialog" title="Force subagents for this session">
              <span class="chip-kind">Subagents</span>
              <span class="chip-value">${esc(forcedChipLabel())}</span>
            </button>
          </div>
          <div class="composer-live-row" id="liveConfirmRow" ${live && isDailyCoder() ? "" : "hidden"}>
            <label class="live-confirm-row">
              <input type="checkbox" id="liveConfirm" />
              Start LIVE provider (may spend API credits)
            </label>
          </div>
          <p id="providerRestartWarn" class="warn small provider-restart-warn" hidden>Provider changed while the server is running — use <b>Restart</b> to apply.</p>
          <div id="startResult" class="muted start-result"></div>
        </div>
        <div class="composer-drawer-backdrop" hidden></div>
        <aside class="composer-drawer" hidden aria-hidden="true" role="dialog" aria-labelledby="composerDrawerTitle">
          <div class="composer-drawer-header">
            <h3 id="composerDrawerTitle" class="composer-drawer-title">Options</h3>
            <button type="button" class="composer-drawer-close" data-drawer-close aria-label="Close">×</button>
          </div>
          <div class="composer-drawer-body" role="listbox"></div>
        </aside>
      </div>
    `;

    wire();
    const ta = host.querySelector("#workRequest");
    if (prompt != null && ta) ta.value = prompt;
    if (repo != null && host.querySelector("#workRepo")) {
      host.querySelector("#workRepo").value = repo;
    }
    slashApi?.destroy?.();
    if (ta) {
      slashApi = attachSlashPalette(ta, {
        getAgentId: () => state.agentId,
      });
    }
    updateModelGate();
    if (wasOpen) openDrawerPanel(wasOpen);
  }

  function wire() {
    host.querySelectorAll(".composer-drawer-trigger[data-drawer]").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        toggleDrawer(btn.getAttribute("data-drawer"));
      });
    });

    host.querySelector("[data-drawer-close]")?.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      closeDrawer();
    });

    host.querySelector(".composer-drawer-backdrop")?.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      closeDrawer();
    });
  }

  onDocClick = (e) => {
    if (!openDrawer) return;
    const t = e.target;
    if (t.closest?.(".composer-drawer-trigger")) return;
    if (t.closest?.(".composer-drawer")) return;
    closeDrawer();
  };
  onKey = (e) => {
    if (e.key === "Escape" && openDrawer) closeDrawer();
  };
  document.addEventListener("click", onDocClick);
  document.addEventListener("keydown", onKey);

  Promise.all([loadRuntimes(), loadPaletteSubagents()]).then(() => render());

  return {
    destroy() {
      document.removeEventListener("click", onDocClick);
      document.removeEventListener("keydown", onKey);
      slashApi?.destroy?.();
      host.innerHTML = "";
    },
    async sync(next = {}) {
      const prompt = host.querySelector("#workRequest")?.value;
      const repo = host.querySelector("#workRepo")?.value;
      if (next.agents) ctx.agents = next.agents;
      if (next.agentId != null) {
        state.agentId = next.agentId;
        state.forced = session.getForcedSubagents(next.agentId);
      }
      if (next.model != null) state.model = next.model;
      await loadRuntimes();
      await loadPaletteSubagents();
      render();
      if (prompt != null && host.querySelector("#workRequest")) {
        host.querySelector("#workRequest").value = prompt;
      }
      if (repo != null && host.querySelector("#workRepo")) {
        host.querySelector("#workRepo").value = repo;
      }
      await slashApi?.refresh?.();
    },
    getValues() {
      return {
        request: host.querySelector("#workRequest")?.value?.trim() || "",
        repo: host.querySelector("#workRepo")?.value?.trim() || "",
        model: state.model,
        context: state.context,
        thinking: state.thinking,
        agentId: state.agentId,
        forced_subagents: state.forced.slice(),
        modelBlocked: Boolean(modelBlockedReason),
      };
    },
    selectedProvider() {
      return isDailyCoder() ? state.model : session.getProvider();
    },
    showRestartWarn(show) {
      const el = host.querySelector("#providerRestartWarn");
      if (el) el.hidden = !show;
    },
  };
}
