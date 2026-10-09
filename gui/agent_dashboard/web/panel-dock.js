/**
 * panel-dock.js — Right-side panel dock.
 *
 * Supported panel types:
 *   'browser' — embedded iframe with URL bar (internal/local URLs)
 *   'code'    — syntax-highlighted file viewer via /api/workspace/file
 *   'plan'    — rendered markdown document viewer
 *
 * Design note: external iframes are shown with a warning because browser
 * CORS/frame-ancestor restrictions typically block them. For external pages,
 * we render a clickable open-in-new-tab link as graceful fallback.
 */

import { renderMarkdown } from "./markdown.js";

const _esc = (s) =>
  String(s == null ? "" : s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );

export const PANEL_ICONS = {
  browser: "🌐",
  code: "📄",
  plan: "📋",
};

/**
 * Render a panel's content into dockBody.
 *
 * @param {HTMLElement} dockBody   The #wsDockBody element.
 * @param {{
 *   id: string,
 *   type: "browser"|"code"|"plan",
 *   label: string,
 *   url?: string,
 *   path?: string,
 *   content?: string,
 * }} panel
 * @param {{ onUrlNavigate: (id: string, url: string) => void }} handlers
 */
export function renderDockPanel(dockBody, panel, handlers) {
  dockBody.innerHTML = "";
  if (panel.type === "browser") {
    renderBrowserPanel(dockBody, panel, handlers);
  } else if (panel.type === "code") {
    renderCodePanel(dockBody, panel);
  } else if (panel.type === "plan") {
    renderPlanPanel(dockBody, panel);
  } else {
    dockBody.innerHTML = `<div class="ws-dock-empty">
      <div class="ws-dock-empty-icon">🗂</div>
      <p>Unknown panel type: ${_esc(panel.type)}</p>
    </div>`;
  }
}

/** Render an empty dock placeholder. */
export function renderDockEmpty(dockBody) {
  dockBody.innerHTML = `
    <div class="ws-dock-empty">
      <div class="ws-dock-empty-icon">🗂</div>
      <p>Open a file, plan, or browser panel<br>from the chat to see it here.</p>
      <p class="muted small">Use the 📄 Code, 📋 Plan, and 🌐 Browser<br>pills in the composer to add panels.</p>
    </div>
  `;
}

// ── Panel renderers ───────────────────────────────────────────────────────────

function renderBrowserPanel(el, panel, handlers) {
  const url = panel.url || "";
  const isLocal = isLocalUrl(url);

  el.innerHTML = `
    <div class="ws-panel-type-browser">
      <div class="ws-browser-bar">
        <input class="ws-browser-url" id="browserUrl-${_esc(panel.id)}"
               type="text" value="${_esc(url)}"
               placeholder="Enter URL or /api path…"
               aria-label="URL" />
        <button class="ws-browser-go" type="button" data-panel-id="${_esc(panel.id)}">Go</button>
      </div>
      <div class="ws-browser-content" id="browserContent-${_esc(panel.id)}"></div>
    </div>
  `;

  const contentEl = el.querySelector(`#browserContent-${CSS.escape(panel.id)}`);
  if (url) {
    loadBrowserContent(contentEl, panel.id, url, isLocal, handlers);
  } else {
    contentEl.innerHTML = `<div class="ws-dock-empty">
      <div class="ws-dock-empty-icon">🌐</div>
      <p>Enter a URL above to load a preview.</p>
      <p class="muted small">Local /api paths and workspace files work best.</p>
    </div>`;
  }

  // Wire Go button
  el.querySelector(".ws-browser-go")?.addEventListener("click", () => {
    const input = el.querySelector(`#browserUrl-${CSS.escape(panel.id)}`);
    const newUrl = input?.value?.trim() || "";
    if (!newUrl) return;
    handlers.onUrlNavigate?.(panel.id, newUrl);
  });

  // Wire Enter key in URL bar
  el.querySelector(`#browserUrl-${CSS.escape(panel.id)}`)?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      el.querySelector(".ws-browser-go")?.click();
    }
  });
}

function loadBrowserContent(contentEl, panelId, url, isLocal, _handlers) {
  if (isLocal) {
    // Safe iframe for same-origin /api or workspace paths
    contentEl.innerHTML = `
      <iframe class="ws-browser-frame"
              src="${_esc(url)}"
              title="Browser panel"
              sandbox="allow-scripts allow-same-origin allow-forms"
              loading="lazy"></iframe>
    `;
  } else {
    // External URL — browsers block most cross-origin iframes.
    // Show a "open in new tab" card instead of a broken iframe.
    contentEl.innerHTML = `
      <div class="ws-dock-empty">
        <div class="ws-dock-empty-icon">🌐</div>
        <p><strong>${_esc(new URL(url, location.href).hostname)}</strong></p>
        <p class="muted small">External pages can't be embedded here due to browser security.<br>
           Use the link below to open in a new tab.</p>
        <a href="${_esc(url)}" target="_blank" rel="noopener noreferrer"
           style="color:var(--teal);font-size:13px;">
          Open ${_esc(url)} ↗
        </a>
      </div>
    `;
  }
}

function renderCodePanel(el, panel) {
  const content = panel.content || "";
  const path = panel.path || panel.label || "File";
  const lang = detectLang(path);

  el.innerHTML = `
    <div class="ws-panel-type-code">
      <div class="ws-panel-header">
        <span class="ws-panel-header-title" title="${_esc(path)}">📄 ${_esc(path)}</span>
        ${lang ? `<span class="ws-panel-lang-badge">${_esc(lang)}</span>` : ""}
      </div>
      ${content
        ? `<pre class="ws-code-view"><code>${_esc(content)}</code></pre>`
        : `<div class="ws-dock-empty">
             <div class="ws-dock-empty-icon">📄</div>
             <p>No content loaded.</p>
           </div>`}
    </div>
  `;
}

function renderPlanPanel(el, panel) {
  const content = panel.content || "";

  el.innerHTML = `
    <div class="ws-panel-type-plan">
      <div class="ws-panel-header">
        <span class="ws-panel-header-title" title="${_esc(panel.label)}">📋 ${_esc(panel.label)}</span>
      </div>
      ${content
        ? `<div class="ws-plan-view ws-msg-bubble">${renderMarkdown(content)}</div>`
        : `<div class="ws-dock-empty">
             <div class="ws-dock-empty-icon">📋</div>
             <p>No plan content.</p>
           </div>`}
    </div>
  `;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function isLocalUrl(url) {
  if (!url) return false;
  if (url.startsWith("/") || url.startsWith("./")) return true;
  try {
    const u = new URL(url);
    return (
      u.hostname === "localhost" ||
      u.hostname === "127.0.0.1" ||
      u.hostname === location.hostname
    );
  } catch {
    return true; // treat unparseable as local
  }
}

function detectLang(path) {
  const ext = String(path || "").split(".").pop().toLowerCase();
  const map = {
    js: "JavaScript", ts: "TypeScript", py: "Python", md: "Markdown",
    json: "JSON", html: "HTML", css: "CSS", sh: "Shell", yaml: "YAML",
    yml: "YAML", txt: "Text",
  };
  return map[ext] || "";
}
