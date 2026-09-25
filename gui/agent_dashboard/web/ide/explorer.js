/** Explorer — allowlisted roots tree + open tabs list. */

import { api, esc } from "../api.js";
import { allOpenTabs } from "./panes.js";
import { openFileBrowser } from "./file-browser.js";

/**
 * @param {HTMLElement} container
 * @param {{ layout: object, onOpenFile: (root: string, path: string, label: string) => void, onFocusTab: (paneId: number, tabId: string) => void, onRefresh: () => void }} ctx
 */
export function mountExplorer(container, ctx) {
  container.innerHTML = `
    <div class="ide-explorer">
      <div class="ide-explorer-toolbar">
        <button type="button" class="ide-toolbar-btn primary" id="ideBrowseBtn" title="Browse for a file">Open file…</button>
      </div>
      <label class="field-label small" for="ideRootSelect">Root</label>
      <select id="ideRootSelect" class="ide-root-select"></select>
      <div class="ide-explorer-cwd" id="ideExplorerCwd" title="Current folder">/</div>
      <div id="ideTree" class="ide-tree muted small">Loading…</div>
      <h3 class="ide-open-heading">Open tabs</h3>
      <ul id="ideOpenTabs" class="ide-open-tabs"></ul>
    </div>
  `;

  const rootSelect = container.querySelector("#ideRootSelect");
  const cwdEl = container.querySelector("#ideExplorerCwd");
  const treeEl = container.querySelector("#ideTree");
  const openList = container.querySelector("#ideOpenTabs");
  let roots = [];
  let currentRel = "";

  function parentRel(rel) {
    if (!rel) return "";
    const parts = rel.replace(/\\/g, "/").split("/").filter(Boolean);
    parts.pop();
    return parts.join("/");
  }

  function displayPath(rel) {
    const rootLabel = roots.find((r) => r.id === rootSelect.value)?.label || rootSelect.value || "";
    return rel ? `${rootLabel} / ${rel.replace(/\\/g, "/")}` : `${rootLabel || "(root)"} /`;
  }

  async function loadRoots() {
    const data = await api("/api/workspace/roots");
    roots = data.roots || [];
    rootSelect.innerHTML = roots
      .map((r) => `<option value="${esc(r.id)}">${esc(r.label || r.id)}</option>`)
      .join("");
    if (roots.length) await loadTree("");
    else {
      cwdEl.textContent = "(no workspace roots)";
      treeEl.innerHTML = "<p>No workspace roots configured. Add them under APIs → Config overlay.</p>";
    }
  }

  async function loadTree(rel) {
    currentRel = rel || "";
    const rootId = rootSelect.value;
    cwdEl.textContent = displayPath(currentRel);
    if (!rootId) {
      treeEl.innerHTML = "<p>No workspace roots configured.</p>";
      return;
    }
    try {
      const q = new URLSearchParams({ root: rootId, path: currentRel, depth: "1" });
      const data = await api(`/api/workspace/tree?${q}`);
      renderTree(data.entries || []);
    } catch (err) {
      treeEl.innerHTML = `<p class="bad">${esc(err.message)}</p>`;
    }
  }

  function renderTree(entries) {
    const lines = [];
    // Always show .. for parent navigation
    lines.push(
      `<button type="button" class="ide-tree-up" data-up title="${currentRel ? "Go to parent folder" : "Already at workspace root"}">.. (parent)</button>`
    );
    const dirs = entries.filter((e) => e.type === "dir").sort((a, b) => a.name.localeCompare(b.name));
    const files = entries.filter((e) => e.type !== "dir").sort((a, b) => a.name.localeCompare(b.name));
    for (const ent of dirs) {
      const rel = currentRel ? `${currentRel}/${ent.name}` : ent.name;
      lines.push(
        `<button type="button" class="ide-tree-dir" data-rel="${esc(rel)}">▸ ${esc(ent.name)}</button>`
      );
    }
    for (const ent of files) {
      const rel = currentRel ? `${currentRel}/${ent.name}` : ent.name;
      lines.push(
        `<button type="button" class="ide-tree-file" data-file="${esc(rel)}">${esc(ent.name)}</button>`
      );
    }
    treeEl.innerHTML = lines.length > 1 ? lines.join("") : `${lines[0]}<p class="muted">Empty folder</p>`;
  }

  function renderOpenTabs() {
    const tabs = allOpenTabs(ctx.layout);
    openList.innerHTML = tabs
      .map(
        ({ paneId, tab }) =>
          `<li><button type="button" class="ide-open-tab" data-pane="${paneId}" data-tab="${esc(tab.id)}">${esc(tab.label)} <span class="muted">(${tab.type === "logshell" ? "log" : "file"})</span></button></li>`
      )
      .join("");
  }

  function browseModal() {
    openFileBrowser({
      title: "Open file",
      initialRoot: rootSelect.value,
      initialPath: currentRel,
      onPick: (rootId, path, label) => {
        ctx.onOpenFile(rootId, path, label);
        // Keep explorer in sync with the folder we picked from
        const parts = path.replace(/\\/g, "/").split("/").filter(Boolean);
        parts.pop();
        loadTree(parts.join("/"));
        if (rootSelect.querySelector(`option[value="${CSS.escape(rootId)}"]`)) {
          rootSelect.value = rootId;
        }
      },
    });
  }

  treeEl.addEventListener("click", (e) => {
    const up = e.target.closest("[data-up]");
    if (up) {
      if (currentRel) loadTree(parentRel(currentRel));
      return;
    }
    const dir = e.target.closest(".ide-tree-dir");
    if (dir) {
      const rel = dir.getAttribute("data-rel") || "";
      loadTree(rel);
      return;
    }
    const file = e.target.closest(".ide-tree-file");
    if (file) {
      const path = file.getAttribute("data-file");
      const rootId = rootSelect.value;
      ctx.onOpenFile(rootId, path, path.split("/").pop() || path);
    }
  });

  rootSelect.addEventListener("change", () => loadTree(""));
  container.querySelector("#ideBrowseBtn")?.addEventListener("click", browseModal);

  openList.addEventListener("click", (e) => {
    const btn = e.target.closest(".ide-open-tab");
    if (!btn) return;
    ctx.onFocusTab(Number(btn.getAttribute("data-pane")), btn.getAttribute("data-tab"));
  });

  loadRoots().catch((err) => {
    treeEl.innerHTML = `<p class="bad">${esc(err.message)}</p>`;
  });

  return {
    refresh() {
      renderOpenTabs();
      ctx.onRefresh?.();
    },
    syncOpenTabs: renderOpenTabs,
    /** Open the modal file browser (used by empty-tab Open file CTA). */
    openBrowser: browseModal,
    navigate(rel) {
      return loadTree(rel || "");
    },
  };
}
