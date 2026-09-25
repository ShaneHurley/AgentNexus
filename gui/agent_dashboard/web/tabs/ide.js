/** IDE workbench — panes, explorer, editor, log shells (no layout presets menu). */

import { api, esc } from "../api.js";
import {
  loadLayout,
  saveLayout,
  newTabId,
  findTab,
  makeEmptyTab,
  addPane,
  reorderPanes,
  moveTabToPane,
  gridClassFor,
} from "../ide/panes.js";
import { mountSideRail } from "../ide/side-rail.js";
import { mountExplorer } from "../ide/explorer.js";
import { mountEditorPane } from "../ide/editor-pane.js";
import { mountTerminalPane } from "../ide/terminal-pane.js";

let layout = loadLayout();
let mounted = false;
let rootEl = null;
let paneControllers = new Map();
let explorerApi = null;
let sideRailApi = null;
let dismissMenusBound = null;
let dismissMenusKeyBound = null;

function persist() {
  saveLayout(layout);
}

function patchLayout(patch) {
  Object.assign(layout, patch);
  persist();
  renderAll();
}

function activePane() {
  return layout.panes[layout.activePaneId] || layout.panes[0];
}

function destroyPaneControllers() {
  for (const ctrl of paneControllers.values()) {
    ctrl?.destroy?.();
  }
  paneControllers.clear();
}

function isLogTabVisible(tabId) {
  const pane = layout.panes.find((p) => p.id === layout.activePaneId);
  if (!pane || pane.activeTabId !== tabId) return false;
  const hit = findTab(layout, tabId);
  return Boolean(hit && hit.tab.type === "logshell");
}

function hideIdeMenus() {
  if (!rootEl) return;
  rootEl.querySelectorAll(".ide-pane-menu, #ideLogMenu").forEach((m) => {
    m.hidden = true;
  });
}

function focusExplorer() {
  patchLayout({ sideCollapsed: false, sideTab: "explorer" });
  sideRailApi?.sync?.();
}

function renderEmptyPrompt(body, paneId) {
  body.innerHTML = `
    <div class="ide-empty-prompt">
      <p class="ide-empty-prompt-title">Open a file to get started</p>
      <p class="muted small">Browse the workspace, or use Explorer on the left.</p>
      <button type="button" class="primary" data-open-file-cta data-pane="${paneId}">Open file</button>
    </div>`;
  body.querySelector("[data-open-file-cta]")?.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    layout.activePaneId = paneId;
    persist();
    focusExplorer();
    // Prefer modal browser so Open file always shows a pick UI
    if (typeof explorerApi?.openBrowser === "function") {
      explorerApi.openBrowser();
    }
  });
}

function renderPaneBody(paneEl, pane) {
  const body = paneEl.querySelector(".ide-pane-body");
  const prevKey = body.getAttribute("data-render-key");
  const tab = pane.tabs.find((t) => t.id === pane.activeTabId);
  const key = tab ? `${pane.id}:${tab.id}:${tab.type}` : `${pane.id}:empty`;
  if (prevKey === key) return;
  body.setAttribute("data-render-key", key);
  const old = paneControllers.get(pane.id);
  old?.destroy?.();
  paneControllers.delete(pane.id);
  body.innerHTML = "";

  if (!tab || tab.type === "empty") {
    renderEmptyPrompt(body, pane.id);
    return;
  }

  if (tab.type === "file") {
    if (!tab.root || !tab.path) {
      renderEmptyPrompt(body, pane.id);
      return;
    }
    const ctrl = mountEditorPane(body, {
      tab,
      onDirty(d) {
        tab.dirty = d;
        persist();
        renderTabBars();
      },
      onSaved(mtime) {
        tab.mtime = mtime;
        persist();
      },
    });
    paneControllers.set(pane.id, ctrl);
  } else if (tab.type === "logshell") {
    const ctrl = mountTerminalPane(body, {
      tab,
      visible: () => mounted && layout.activePaneId === pane.id && isLogTabVisible(tab.id),
    });
    paneControllers.set(pane.id, ctrl);
  }
}

function kindLabel(t) {
  if (t.type === "logshell") return "term";
  if (t.type === "empty") return "new";
  return "file";
}

function renderTabBars() {
  if (!rootEl) return;
  const grid = rootEl.querySelector(".ide-pane-grid");
  grid.querySelectorAll(".ide-pane").forEach((paneEl) => {
    const paneId = Number(paneEl.getAttribute("data-pane-id"));
    const pane = layout.panes.find((p) => p.id === paneId);
    if (!pane) return;
    const bar = paneEl.querySelector(".ide-pane-tabbar");
    const tabsHtml = pane.tabs
      .map((t) => {
        const active = t.id === pane.activeTabId;
        const dirty = t.dirty ? " •" : "";
        return `<span class="ide-doc-tab${active ? " active" : ""}" data-tab-id="${esc(t.id)}" draggable="true" title="${esc(t.label)}">
          <button type="button" class="ide-doc-tab-label" data-select-tab="${esc(t.id)}">${esc(t.label)}${dirty} <span class="muted">(${kindLabel(t)})</span></button>
          <button type="button" class="ide-doc-tab-close" data-close-tab-id="${esc(t.id)}" title="Close tab" aria-label="Close ${esc(t.label)}">×</button>
        </span>`;
      })
      .join("");
    bar.innerHTML = `
      <div class="ide-doc-tabs">${tabsHtml || '<span class="muted small">No tabs</span>'}</div>
      <div class="ide-tab-actions">
        <button type="button" class="ide-tab-plus" data-plus-tab title="New blank tab">+</button>
        <div class="ide-menu-wrap ide-pane-menu-wrap">
          <button type="button" class="ide-tab-arrow" data-pane-menu title="More">▾</button>
          <div class="ide-dropdown ide-pane-menu" hidden>
            <button type="button" data-menu-action="new-file">New file</button>
            <button type="button" data-menu-action="new-term">New terminal</button>
            <button type="button" data-menu-action="split">Split pane</button>
          </div>
        </div>
      </div>`;
    paneEl.classList.toggle("ide-pane-active", layout.activePaneId === paneId);
    // Drag handle: whole tabbar for pane reposition
    bar.setAttribute("draggable", "true");
    bar.classList.add("ide-pane-drag-handle");
    renderPaneBody(paneEl, pane);
  });
  explorerApi?.syncOpenTabs?.();
}

function renderGrid() {
  const grid = rootEl.querySelector(".ide-pane-grid");
  grid.className = `ide-pane-grid ${gridClassFor(layout)}`;
  grid.setAttribute("data-pane-count", String(layout.panes.length));

  destroyPaneControllers();
  grid.innerHTML = layout.panes
    .map(
      (pane) => `
    <div class="ide-pane" data-pane-id="${pane.id}" data-pane-drop>
      <div class="ide-pane-tabbar"></div>
      <div class="ide-pane-body muted"></div>
    </div>`
    )
    .join("");

  grid.querySelectorAll(".ide-pane").forEach((paneEl) => {
    const paneId = Number(paneEl.getAttribute("data-pane-id"));

    paneEl.addEventListener("click", (e) => {
      const selectBtn = e.target.closest("[data-select-tab]");
      if (selectBtn) {
        const id = selectBtn.getAttribute("data-select-tab");
        const pane = layout.panes.find((p) => p.id === paneId);
        if (pane) {
          pane.activeTabId = id;
          layout.activePaneId = paneId;
          persist();
          renderTabBars();
        }
        return;
      }
      const closeBtn = e.target.closest("[data-close-tab-id]");
      if (closeBtn) {
        e.stopPropagation();
        closeTab(paneId, closeBtn.getAttribute("data-close-tab-id"));
        return;
      }
      if (e.target.closest("[data-plus-tab]")) {
        e.stopPropagation();
        addBlankTab(paneId);
        return;
      }
      if (e.target.closest("[data-pane-menu]")) {
        e.preventDefault();
        e.stopPropagation();
        const menu = paneEl.querySelector(".ide-pane-menu");
        if (!menu) return;
        const willOpen = menu.hidden;
        hideIdeMenus();
        menu.hidden = !willOpen;
        return;
      }
      const menuAction = e.target.closest("[data-menu-action]");
      if (menuAction) {
        e.preventDefault();
        e.stopPropagation();
        hideIdeMenus();
        const action = menuAction.getAttribute("data-menu-action");
        layout.activePaneId = paneId;
        if (action === "new-file") addNewFile(paneId);
        else if (action === "new-term") newLogShellDefault(paneId);
        else if (action === "split") {
          const nid = addPane(layout);
          if (nid != null) {
            persist();
            renderGrid();
          } else {
            alert("Maximum of 4 panes.");
          }
        }
        return;
      }
      layout.activePaneId = paneId;
      persist();
      renderTabBars();
    });

    // Pane chrome drag → reorder panes
    const tabbar = paneEl.querySelector(".ide-pane-tabbar");
    tabbar.addEventListener("dragstart", (e) => {
      // If dragging a tab chip, handle tab move instead
      const tabChip = e.target.closest("[data-tab-id]");
      if (tabChip && e.target.closest(".ide-doc-tab-close") == null) {
        const tabId = tabChip.getAttribute("data-tab-id");
        e.dataTransfer.setData("text/ide-tab", tabId);
        e.dataTransfer.effectAllowed = "move";
        paneEl.classList.add("ide-dragging-tab");
        return;
      }
      const idx = layout.panes.findIndex((p) => p.id === paneId);
      e.dataTransfer.setData("text/ide-pane", String(idx));
      e.dataTransfer.effectAllowed = "move";
      paneEl.classList.add("ide-dragging-pane");
    });
    tabbar.addEventListener("dragend", () => {
      grid.querySelectorAll(".ide-pane").forEach((el) => {
        el.classList.remove("ide-dragging-pane", "ide-dragging-tab", "ide-drop-target");
      });
    });

    paneEl.addEventListener("dragover", (e) => {
      e.preventDefault();
      paneEl.classList.add("ide-drop-target");
    });
    paneEl.addEventListener("dragleave", () => {
      paneEl.classList.remove("ide-drop-target");
    });
    paneEl.addEventListener("drop", (e) => {
      e.preventDefault();
      paneEl.classList.remove("ide-drop-target");
      const tabId = e.dataTransfer.getData("text/ide-tab");
      if (tabId) {
        if (moveTabToPane(layout, tabId, paneId)) {
          persist();
          renderGrid();
        }
        return;
      }
      const fromRaw = e.dataTransfer.getData("text/ide-pane");
      if (fromRaw === "") return;
      const fromIdx = Number(fromRaw);
      const toIdx = layout.panes.findIndex((p) => p.id === paneId);
      if (Number.isFinite(fromIdx) && toIdx >= 0 && fromIdx !== toIdx) {
        reorderPanes(layout, fromIdx, toIdx);
        persist();
        renderGrid();
      }
    });
  });

  renderTabBars();
}

function closeTab(paneId, tabId) {
  const pane = layout.panes.find((p) => p.id === paneId);
  if (!pane || !tabId) return;
  const tab = pane.tabs.find((t) => t.id === tabId);
  if (!tab) return;

  const wasActive = pane.activeTabId === tabId;
  const ctrl = wasActive ? paneControllers.get(paneId) : null;

  if (tab.type === "file") {
    if (ctrl?.confirmClose) {
      if (!ctrl.confirmClose()) return;
    } else if (tab.dirty) {
      if (!window.confirm(`Discard unsaved changes in ${tab.label}?`)) return;
    }
  } else if (tab.type === "logshell" && wasActive) {
    ctrl?.destroy?.();
  }

  const idx = pane.tabs.findIndex((t) => t.id === tabId);
  pane.tabs = pane.tabs.filter((t) => t.id !== tabId);

  if (wasActive) {
    paneControllers.delete(paneId);
    if (pane.tabs.length) {
      const next = pane.tabs[Math.min(idx, pane.tabs.length - 1)];
      pane.activeTabId = next.id;
    } else {
      pane.activeTabId = null;
    }
  } else if (pane.activeTabId && !pane.tabs.some((t) => t.id === pane.activeTabId)) {
    pane.activeTabId = pane.tabs.length ? pane.tabs[0].id : null;
  }

  persist();
  renderGrid();
}

function addBlankTab(paneId) {
  const pane = layout.panes.find((p) => p.id === paneId) || activePane();
  const tab = makeEmptyTab();
  pane.tabs.push(tab);
  pane.activeTabId = tab.id;
  layout.activePaneId = pane.id;
  persist();
  renderGrid();
}

function addNewFile(paneId) {
  const pane = layout.panes.find((p) => p.id === paneId) || activePane();
  const tab = {
    id: newTabId(),
    type: "file",
    label: "untitled.txt",
    root: "",
    path: "",
    dirty: false,
  };
  pane.tabs.push(tab);
  pane.activeTabId = tab.id;
  layout.activePaneId = pane.id;
  persist();
  renderGrid();
}

function openFile(root, path, label) {
  const pane = activePane();
  // Prefer filling an empty/active blank tab
  let tab = pane.tabs.find((t) => t.id === pane.activeTabId && (t.type === "empty" || (t.type === "file" && !t.path)));
  if (tab) {
    tab.type = "file";
    tab.root = root;
    tab.path = path;
    tab.label = label || path;
    tab.dirty = false;
  } else {
    tab = pane.tabs.find((t) => t.type === "file" && t.root === root && t.path === path);
    if (!tab) {
      tab = {
        id: newTabId(),
        type: "file",
        label: label || path,
        root,
        path,
        dirty: false,
        mtime: null,
      };
      pane.tabs.push(tab);
    }
  }
  pane.activeTabId = tab.id;
  layout.activePaneId = pane.id;
  persist();
  renderGrid();
}

function focusTab(paneId, tabId) {
  const pane = layout.panes.find((p) => p.id === paneId);
  if (!pane) return;
  pane.activeTabId = tabId;
  layout.activePaneId = paneId;
  persist();
  renderTabBars();
}

async function newLogShell(profileId, paneId) {
  const pane = (paneId != null ? layout.panes.find((p) => p.id === paneId) : null) || activePane();
  try {
    const sess = await api("/api/terminal/sessions", {
      method: "POST",
      body: JSON.stringify({ profile_id: profileId }),
    });
    const tab = {
      id: newTabId(),
      type: "logshell",
      label: sess.label || profileId,
      sessionId: sess.id,
      root: "",
      path: "",
      dirty: false,
    };
    pane.tabs.push(tab);
    pane.activeTabId = tab.id;
    layout.activePaneId = pane.id;
    persist();
    renderGrid();
  } catch (err) {
    alert(err.message);
  }
}

async function newLogShellDefault(paneId) {
  try {
    const data = await api("/api/terminal/profiles");
    const profiles = (data.profiles || []).filter((p) => p.enabled);
    if (!profiles.length) {
      alert("No enabled terminal profiles.");
      return;
    }
    await newLogShell(profiles[0].id, paneId);
  } catch (err) {
    alert(err.message);
  }
}

function wireToolbar() {
  rootEl.querySelector("#ideNewFileBtn").addEventListener("click", () => {
    addNewFile(activePane().id);
  });

  const logBtn = rootEl.querySelector("#ideLogShellBtn");
  const logMenu = rootEl.querySelector("#ideLogMenu");
  logBtn.addEventListener("click", async (e) => {
    e.preventDefault();
    e.stopPropagation();
    // Toggle closed immediately (no await) so a second click always dismisses.
    if (!logMenu.hidden) {
      hideIdeMenus();
      return;
    }
    try {
      const data = await api("/api/terminal/profiles");
      const profiles = (data.profiles || []).filter((p) => p.enabled);
      logMenu.innerHTML = profiles.length
        ? profiles.map((p) => `<button type="button" data-profile="${esc(p.id)}">${esc(p.label)}</button>`).join("")
        : '<span class="muted small">No enabled profiles</span>';
    } catch (err) {
      logMenu.innerHTML = `<span class="bad small">${esc(err.message)}</span>`;
    }
    hideIdeMenus();
    logMenu.hidden = false;
  });
  logMenu.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-profile]");
    if (!btn) return;
    e.preventDefault();
    e.stopPropagation();
    hideIdeMenus();
    newLogShell(btn.getAttribute("data-profile"));
  });

  rootEl.querySelector("#ideSideToggle").addEventListener("click", () => {
    patchLayout({ sideCollapsed: !layout.sideCollapsed });
    sideRailApi?.sync?.();
  });

  dismissMenusBound = (e) => {
    if (!rootEl) return;
    // Let the trigger's own handler toggle; ignore clicks inside an open menu panel.
    if (e.target.closest?.("[data-pane-menu]") || e.target.closest?.("#ideLogShellBtn")) return;
    if (e.target.closest?.(".ide-pane-menu") || e.target.closest?.("#ideLogMenu")) return;
    hideIdeMenus();
  };
  dismissMenusKeyBound = (e) => {
    if (e.key === "Escape") hideIdeMenus();
  };
  document.addEventListener("click", dismissMenusBound);
  document.addEventListener("keydown", dismissMenusKeyBound);
}

function renderAll() {
  const body = rootEl.querySelector(".ide-body");
  body.classList.toggle("ide-side-hidden", layout.sideCollapsed);
  sideRailApi?.sync?.();
  renderGrid();
}

export function mount(container) {
  mounted = true;
  layout = loadLayout();
  container.innerHTML = `
    <section class="ide-workbench" data-panel="ide">
      <p class="muted small ide-honesty">Workbench: folder browser + plain-text edit + log shells — not a full IDE. Drag a pane tab bar to reposition.</p>
      <div class="ide-toolbar" role="toolbar" aria-label="IDE actions">
        <button type="button" id="ideNewFileBtn" class="ide-toolbar-btn">New file</button>
        <div class="ide-menu-wrap">
          <button type="button" id="ideLogShellBtn" class="ide-toolbar-btn">New log shell ▾</button>
          <div id="ideLogMenu" class="ide-dropdown" hidden></div>
        </div>
        <button type="button" id="ideSideToggle" class="ide-toolbar-btn" title="Collapse or expand side rail">Side —/□</button>
      </div>
      <div class="ide-body">
        <aside class="ide-side-rail" aria-label="Side rail"></aside>
        <div class="ide-pane-grid ${gridClassFor(layout)}" data-pane-count="${layout.panes.length}"></div>
      </div>
    </section>
  `;
  rootEl = container.querySelector(".ide-workbench");

  sideRailApi = mountSideRail(rootEl.querySelector(".ide-side-rail"), {
    layout,
    onLayoutChange: (patch) => patchLayout(patch),
    explorerMount: (el) => {
      explorerApi = mountExplorer(el, {
        layout,
        onOpenFile: openFile,
        onFocusTab: focusTab,
        onRefresh: () => {},
      });
    },
  });

  wireToolbar();
  renderAll();
}

export function unmount() {
  mounted = false;
  if (dismissMenusBound) {
    document.removeEventListener("click", dismissMenusBound);
    dismissMenusBound = null;
  }
  if (dismissMenusKeyBound) {
    document.removeEventListener("keydown", dismissMenusKeyBound);
    dismissMenusKeyBound = null;
  }
  destroyPaneControllers();
  rootEl = null;
  explorerApi = null;
  sideRailApi = null;
}