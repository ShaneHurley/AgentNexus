/** IDE pane presets + round-robin redistribution (G12). */

export const PRESETS = [
  { id: "single", label: "Single", panes: 1 },
  { id: "split-h", label: "Split horizontal", panes: 2 },
  { id: "split-v", label: "Split vertical", panes: 2 },
  { id: "halves-h", label: "Halves horizontal", panes: 2 },
  { id: "halves-v", label: "Halves vertical", panes: 2 },
  { id: "quarters", label: "Quarters", panes: 4 },
];

/** @param {string} presetId */
export function paneCount(presetId) {
  const p = PRESETS.find((x) => x.id === presetId);
  return p ? p.panes : 1;
}

/** @param {string} presetId */
export function presetClass(presetId) {
  return `ide-preset-${presetId || "single"}`;
}

/**
 * Flatten tabs in pane order, assign round-robin to N new panes.
 * @param {Array<{ id: number, tabs: object[], activeTabId?: string | null }>} oldPanes
 * @param {string} newPreset
 * @param {number} oldActivePaneId
 */
export function redistribute(oldPanes, newPreset, oldActivePaneId = 0) {
  const N = paneCount(newPreset);
  const flat = [];
  for (const pane of oldPanes || []) {
    for (const tab of pane.tabs || []) {
      flat.push(tab);
    }
  }

  const newPanes = [];
  for (let i = 0; i < N; i += 1) {
    newPanes.push({ id: i, tabs: [], activeTabId: null });
  }
  flat.forEach((tab, i) => {
    newPanes[i % N].tabs.push(tab);
  });

  let activePaneId = oldActivePaneId;
  if (activePaneId >= N) activePaneId = 0;

  for (const pane of newPanes) {
    const still = pane.tabs.some((t) => t.id === pane.activeTabId);
    if (!still) {
      pane.activeTabId = pane.tabs.length ? pane.tabs[0].id : null;
    }
  }

  const activePane = newPanes[activePaneId];
  if (activePane && !activePane.tabs.length) {
    activePaneId = newPanes.findIndex((p) => p.tabs.length > 0);
    if (activePaneId < 0) activePaneId = 0;
  }

  return { panes: newPanes, activePaneId, preset: newPreset };
}
