/** Documentation tab — list + safe markdown render. */

import { api, esc } from "../api.js";
import { renderMarkdown } from "../markdown.js";
import { hashFor } from "../router.js";

let currentName = "";
let rootContainer = null;
let suppressHash = false;

async function loadList(container) {
  const listEl = container.querySelector("#docsList");
  const view = container.querySelector("#docsView");
  const data = await api("/api/docs");
  const docs = data.docs || [];
  if (!docs.length) {
    const hint =
      data.warning ||
      "No documentation files found. Run via start.py from the agent-dashboard folder, or set AGENT_DASHBOARD_ROOT.";
    listEl.innerHTML = `<p class="muted">${esc(hint)}</p>`;
    if (view) {
      view.innerHTML = `<p class="bad">${esc(hint)}</p><p class="muted small">docs_dir: ${esc(data.docs_dir || "(unknown)")}</p>`;
    }
    return docs;
  }
  listEl.innerHTML = docs
    .map(
      (d) =>
        `<button type="button" class="docs-item${d.name === currentName ? " active" : ""}" data-name="${esc(d.name)}">${esc(d.title || d.name)}</button>`
    )
    .join("");
  return docs;
}

function syncDocHash(name) {
  if (suppressHash) return;
  suppressHash = true;
  window.location.hash = hashFor({ tab: "docs", doc: name || "" });
  suppressHash = false;
}

async function loadDoc(container, name, { updateHash = true } = {}) {
  currentName = name;
  const view = container.querySelector("#docsView");
  view.innerHTML = '<p class="muted">Loading…</p>';
  const slug = name.replace(/\.md$/, "");
  const data = await api(`/api/docs/${encodeURIComponent(slug)}`);
  view.innerHTML = `
    <header class="docs-view-header">
      <h2>${esc(data.title || name)}</h2>
      <p class="muted small">${esc(name)}</p>
    </header>
    <article class="docs-markdown">${renderMarkdown(data.content || "")}</article>`;
  await loadList(container);
  if (updateHash) syncDocHash(name);
}

/**
 * Re-apply deep-link when already on the docs tab (hash sync).
 * @param {{ doc?: string }} route
 */
export function syncRoute(route = {}) {
  if (!rootContainer) return;
  const doc = route.doc || "";
  if (!doc || doc === currentName) return;
  loadDoc(rootContainer, doc, { updateHash: false }).catch((err) => {
    rootContainer.querySelector("#docsView").innerHTML = `<p class="bad">${esc(err.message)}</p>`;
  });
}

export function mount(container, route = {}) {
  rootContainer = container;
  container.innerHTML = `
    <div class="docs-layout">
      <aside class="panel docs-sidebar">
        <h2>Docs</h2>
        <nav id="docsList" class="docs-list" aria-label="Documentation files"><p class="muted">Loading…</p></nav>
      </aside>
      <main class="panel docs-main">
        <div id="docsView"><p class="muted">Select a document.</p></div>
      </main>
    </div>`;

  const list = container.querySelector("#docsList");
  list.addEventListener("click", (e) => {
    const btn = e.target.closest(".docs-item");
    if (!btn) return;
    loadDoc(container, btn.getAttribute("data-name")).catch((err) => {
      container.querySelector("#docsView").innerHTML = `<p class="bad">${esc(err.message)}</p>`;
    });
  });

  const initialDoc = route.doc || "";
  loadList(container)
    .then(async (docs) => {
      if (initialDoc) {
        await loadDoc(container, initialDoc, { updateHash: false });
        return;
      }
      const firstBtn = list.querySelector(".docs-item");
      if (firstBtn) await loadDoc(container, firstBtn.getAttribute("data-name"));
    })
    .catch((err) => {
      list.innerHTML = `<p class="bad">${esc(err.message)}</p>`;
    });
}

export function unmount() {
  currentName = "";
  rootContainer = null;
}
