/** Document tabs (file | logshell | empty) + metadata persist ad_ide_layout v1. */

import * as session from "../state.js";
import { redistribute, paneCount } from "./layout.js";

let nextTabId = 1;

export function newTabId() {
  const id = `tab-${nextTabId}`;
  nextTabId += 1;
  return id;
}

export function defaultLayout() {
  return {
    version: 1,
    preset: "single",
    sideCollapsed: false,
    sideTab: "explorer",
    activePaneId: 0,
    panes: [{ id: 0, tabs: [], activeTabId: null }],
  };
}

function normalizeTabType(type) {
  if (type === "logshell") return "logshell";
  if (type === "empty") return "empty";
  return "file";
}

/** @returns {object} */
export function loadLayout() {
  const raw = session.getIdeLayout();
  const layout = defaultLayout();
  if (raw.preset) layout.preset = raw.preset;
  if (typeof raw.sideCollapsed === "boolean") layout.sideCollapsed = raw.sideCollapsed;
  if (raw.sideTab === "ai" || raw.sideTab === "explorer") layout.sideTab = raw.sideTab;
  if (typeof raw.activePaneId === "number") layout.activePaneId = raw.activePaneId;
  if (Array.isArray(raw.panes) && raw.panes.length) {
    layout.panes = raw.panes.map((p, i) => ({
      id: typeof p.id === "number" ? p.id : i,
      activeTabId: p.activeTabId || null,
      tabs: Array.isArray(p.tabs)
        ? p.tabs.map((t) => ({
            id: t.id || newTabId(),
            type: normalizeTabType(t.type),
            label: t.label || (t.type === "empty" ? "New" : "untitled"),
            root: t.root || "",
            path: t.path || "",
            dirty: Boolean(t.dirty),
            mtime: t.mtime || null,
            sessionId: t.sessionId || null,
          }))
        : [],
    }));
    for (const t of layout.panes.flatMap((p) => p.tabs)) {
      const m = /^tab-(\d+)$/.exec(t.id);
      if (m) nextTabId = Math.max(nextTabId, Number(m[1]) + 1);
    }
  }
  // Prefer explicit pane list length; fall back to preset count for older layouts.
  const n = Math.max(layout.panes.length, paneCount(layout.preset) || 1);
  while (layout.panes.length < n && layout.panes.length < 4) {
    layout.panes.push({ id: layout.panes.length, tabs: [], activeTabId: null });
  }
  // Normalize orphaned activeTabId (stale id after close / corrupt layout).
  for (const pane of layout.panes) {
    if (
      pane.activeTabId &&
      !pane.tabs.some((t) => t.id === pane.activeTabId)
    ) {
      pane.activeTabId = pane.tabs.length ? pane.tabs[0].id : null;
    }
  }
  if (
    typeof layout.activePaneId === "number" &&
    !layout.panes.some((p) => p.id === layout.activePaneId)
  ) {
    layout.activePaneId = layout.panes[0]?.id ?? 0;
  }
  return layout;
}

/** @param {object} layout */
export function saveLayout(layout) {
  const meta = {
    version: 1,
    preset: layout.preset || "single",
    sideCollapsed: layout.sideCollapsed,
    sideTab: layout.sideTab,
    activePaneId: layout.activePaneId,
    panes: layout.panes.map((p) => ({
      id: p.id,
      activeTabId: p.activeTabId,
      tabs: p.tabs.map((t) => ({
        id: t.id,
        type: t.type,
        label: t.label,
        root: t.root,
        path: t.path,
        dirty: t.dirty,
        mtime: t.mtime,
        sessionId: t.sessionId,
      })),
    })),
  };
  session.setIdeLayout(meta);
  return meta;
}

/** @param {object} layout @param {string} preset */
export function applyPreset(layout, preset) {
  const red = redistribute(layout.panes, preset, layout.activePaneId);
  layout.preset = preset;
  layout.panes = red.panes;
  layout.activePaneId = red.activePaneId;
  return layout;
}

/** Reorder panes by moving fromIdx to toIdx (for drag reposition). */
export function reorderPanes(layout, fromIdx, toIdx) {
  if (fromIdx === toIdx || fromIdx < 0 || toIdx < 0) return layout;
  if (fromIdx >= layout.panes.length || toIdx >= layout.panes.length) return layout;
  const activeTabs = (layout.panes.find((p) => p.id === layout.activePaneId) || {}).tabs;
  const copy = layout.panes.slice();
  const [moved] = copy.splice(fromIdx, 1);
  copy.splice(toIdx, 0, moved);
  layout.panes = copy.map((p, i) => ({ ...p, id: i }));
  let found = layout.panes.findIndex((p) => p.tabs === activeTabs);
  if (found < 0) found = toIdx;
  layout.activePaneId = found;
  return layout;
}

export function moveTabToPane(layout, tabId, targetPaneId) {
  const hit = findTab(layout, tabId);
  if (!hit) return false;
  const target = layout.panes.find((p) => p.id === targetPaneId);
  if (!target || hit.pane.id === target.id) return false;
  hit.pane.tabs = hit.pane.tabs.filter((t) => t.id !== tabId);
  if (hit.pane.activeTabId === tabId) {
    hit.pane.activeTabId = hit.pane.tabs.length ? hit.pane.tabs[0].id : null;
  }
  target.tabs.push(hit.tab);
  target.activeTabId = tabId;
  layout.activePaneId = target.id;
  return true;
}

/** Add a new empty pane (split) up to 4. */
export function addPane(layout) {
  if (layout.panes.length >= 4) return null;
  const id = layout.panes.length;
  layout.panes.push({ id, tabs: [], activeTabId: null });
  layout.preset = layout.panes.length === 1 ? "single" : layout.panes.length === 2 ? "split-h" : "quarters";
  layout.activePaneId = id;
  return id;
}

/** CSS class for current pane count (no layout menu). */
export function gridClassFor(layout) {
  const n = layout.panes?.length || 1;
  if (n <= 1) return "ide-preset-single";
  if (n === 2) return "ide-preset-split-h";
  if (n === 3) return "ide-preset-thirds";
  return "ide-preset-quarters";
}

/** @param {object} pane @param {string} tabId @param {number} dir -1 | 1 */
export function moveTab(pane, tabId, dir) {
  const idx = pane.tabs.findIndex((t) => t.id === tabId);
  if (idx < 0) return;
  const next = idx + dir;
  if (next < 0 || next >= pane.tabs.length) return;
  const copy = pane.tabs.slice();
  const tmp = copy[idx];
  copy[idx] = copy[next];
  copy[next] = tmp;
  pane.tabs = copy;
}

export function findTab(layout, tabId) {
  for (const pane of layout.panes) {
    const tab = pane.tabs.find((t) => t.id === tabId);
    if (tab) return { pane, tab };
  }
  return null;
}

export function allOpenTabs(layout) {
  const out = [];
  for (const pane of layout.panes) {
    for (const tab of pane.tabs) {
      out.push({ paneId: pane.id, tab });
    }
  }
  return out;
}

export function makeEmptyTab() {
  return {
    id: newTabId(),
    type: "empty",
    label: "New",
    root: "",
    path: "",
    dirty: false,
    mtime: null,
    sessionId: null,
  };
}