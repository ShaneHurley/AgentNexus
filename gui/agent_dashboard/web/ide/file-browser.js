/** In-app folder browser — current path, parent (..), open file. */

import { api, esc } from "../api.js";

/**
 * Open a modal file browser jailed to workspace roots.
 * @param {{
 *   title?: string,
 *   initialRoot?: string,
 *   initialPath?: string,
 *   onPick: (rootId: string, relPath: string, label: string) => void,
 * }} opts
 * @returns {{ close: () => void }}
 */
export function openFileBrowser(opts) {
  const existing = document.getElementById("ideFileBrowser");
  existing?.remove();

  const backdrop = document.createElement("div");
  backdrop.id = "ideFileBrowser";
  backdrop.className = "ide-file-browser-backdrop";
  backdrop.innerHTML = `
    <div class="ide-file-browser" role="dialog" aria-modal="true" aria-labelledby="ideFileBrowserTitle">
      <header class="ide-file-browser-head">
        <h3 id="ideFileBrowserTitle">${esc(opts.title || "Open file")}</h3>
        <button type="button" class="ide-file-browser-close" data-close aria-label="Close">×</button>
      </header>
      <label class="field-label small" for="ideFbRoot">Workspace root</label>
      <select id="ideFbRoot" class="ide-root-select"></select>
      <div class="ide-file-browser-path" id="ideFbPath" title="Current folder"></div>
      <div class="ide-file-browser-list" id="ideFbList" role="listbox"><p class="muted small">Loading…</p></div>
      <footer class="ide-file-browser-foot">
        <button type="button" data-close>Cancel</button>
      </footer>
    </div>`;
  document.body.appendChild(backdrop);

  const rootSelect = backdrop.querySelector("#ideFbRoot");
  const pathEl = backdrop.querySelector("#ideFbPath");
  const listEl = backdrop.querySelector("#ideFbList");
  let currentRel = opts.initialPath || "";
  let roots = [];

  function close() {
    document.removeEventListener("keydown", onKey);
    backdrop.remove();
  }

  function onKey(e) {
    if (e.key === "Escape") {
      e.preventDefault();
      close();
    }
  }
  document.addEventListener("keydown", onKey);

  backdrop.addEventListener("click", (e) => {
    if (e.target === backdrop || e.target.closest?.("[data-close]")) {
      close();
    }
  });

  function parentRel(rel) {
    if (!rel) return "";
    const parts = rel.replace(/\\/g, "/").split("/").filter(Boolean);
    parts.pop();
    return parts.join("/");
  }

  function displayPath(rel) {
    const rootLabel = roots.find((r) => r.id === rootSelect.value)?.label || rootSelect.value || "";
    return rel ? `${rootLabel} / ${rel.replace(/\\/g, "/")}` : `${rootLabel} /`;
  }

  async function loadRoots() {
    const data = await api("/api/workspace/roots");
    roots = data.roots || [];
    rootSelect.innerHTML = roots
      .map((r) => `<option value="${esc(r.id)}">${esc(r.label || r.id)}</option>`)
      .join("");
    if (opts.initialRoot && roots.some((r) => r.id === opts.initialRoot)) {
      rootSelect.value = opts.initialRoot;
    }
    if (!roots.length) {
      listEl.innerHTML = `<p class="bad">No workspace roots. Add them under APIs → Config overlay.</p>`;
      pathEl.textContent = "(no root)";
      return;
    }
    await loadDir(currentRel);
  }

  async function loadDir(rel) {
    currentRel = rel || "";
    pathEl.textContent = displayPath(currentRel);
    const rootId = rootSelect.value;
    if (!rootId) return;
    try {
      const q = new URLSearchParams({ root: rootId, path: currentRel, depth: "1" });
      const data = await api(`/api/workspace/tree?${q}`);
      renderList(data.entries || []);
    } catch (err) {
      listEl.innerHTML = `<p class="bad">${esc(err.message)}</p>`;
    }
  }

  function renderList(entries) {
    const rows = [];
    // Always show parent navigation
    rows.push(
      `<button type="button" class="ide-fb-row ide-fb-up" data-up role="option" ${currentRel ? "" : 'title="Already at workspace root"'}>
        <span class="ide-fb-icon">..</span>
        <span class="ide-fb-name">..</span>
        <span class="muted small">parent folder</span>
      </button>`
    );
    const dirs = entries.filter((e) => e.type === "dir").sort((a, b) => a.name.localeCompare(b.name));
    const files = entries.filter((e) => e.type !== "dir").sort((a, b) => a.name.localeCompare(b.name));
    for (const d of dirs) {
      const rel = currentRel ? `${currentRel}/${d.name}` : d.name;
      rows.push(
        `<button type="button" class="ide-fb-row ide-fb-dir" data-dir="${esc(rel)}" role="option">
          <span class="ide-fb-icon">dir</span>
          <span class="ide-fb-name">${esc(d.name)}</span>
        </button>`
      );
    }
    for (const f of files) {
      const rel = currentRel ? `${currentRel}/${f.name}` : f.name;
      rows.push(
        `<button type="button" class="ide-fb-row ide-fb-file" data-file="${esc(rel)}" role="option">
          <span class="ide-fb-icon">file</span>
          <span class="ide-fb-name">${esc(f.name)}</span>
        </button>`
      );
    }
    if (dirs.length + files.length === 0) {
      rows.push(`<p class="muted small ide-fb-empty">Empty folder</p>`);
    }
    listEl.innerHTML = rows.join("");
  }

  listEl.addEventListener("click", (e) => {
    const up = e.target.closest("[data-up]");
    if (up) {
      if (currentRel) loadDir(parentRel(currentRel));
      return;
    }
    const dir = e.target.closest("[data-dir]");
    if (dir) {
      loadDir(dir.getAttribute("data-dir") || "");
      return;
    }
    const file = e.target.closest("[data-file]");
    if (file) {
      const path = file.getAttribute("data-file") || "";
      const label = path.split("/").pop() || path;
      opts.onPick(rootSelect.value, path, label);
      close();
    }
  });

  rootSelect.addEventListener("change", () => {
    currentRel = "";
    loadDir("");
  });

  loadRoots().catch((err) => {
    listEl.innerHTML = `<p class="bad">${esc(err.message)}</p>`;
  });

  return { close };
}
