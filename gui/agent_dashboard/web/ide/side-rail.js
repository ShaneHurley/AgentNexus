/** Side rail — collapse + AI | Explorer sub-tabs. */

import { mountAiSkeleton } from "./ai-skeleton.js";

/**
 * @param {HTMLElement} root
 * @param {{ layout: object, onLayoutChange: (patch: object) => void, explorerMount: (el: HTMLElement) => void }} ctx
 */
export function mountSideRail(root, ctx) {
  root.innerHTML = `
    <div class="ide-side-tabs" role="tablist" aria-label="Side panel">
      <button type="button" class="ide-side-tab" role="tab" data-side="ai">AI</button>
      <button type="button" class="ide-side-tab" role="tab" data-side="explorer">Explorer</button>
    </div>
    <div class="ide-side-panels">
      <div class="ide-side-panel" data-side-panel="ai" hidden></div>
      <div class="ide-side-panel" data-side-panel="explorer" hidden></div>
    </div>
  `;

  const aiPanel = root.querySelector('[data-side-panel="ai"]');
  const explorerPanel = root.querySelector('[data-side-panel="explorer"]');
  mountAiSkeleton(aiPanel);
  ctx.explorerMount(explorerPanel);

  function sync() {
    const collapsed = ctx.layout.sideCollapsed;
    root.classList.toggle("ide-side-collapsed", collapsed);
    const tab = ctx.layout.sideTab || "explorer";
    for (const btn of root.querySelectorAll(".ide-side-tab")) {
      const on = btn.getAttribute("data-side") === tab;
      btn.setAttribute("aria-selected", on ? "true" : "false");
    }
    aiPanel.hidden = collapsed || tab !== "ai";
    explorerPanel.hidden = collapsed || tab !== "explorer";
  }

  root.querySelector(".ide-side-tabs").addEventListener("click", (e) => {
    const btn = e.target.closest(".ide-side-tab");
    if (!btn) return;
    ctx.onLayoutChange({ sideTab: btn.getAttribute("data-side"), sideCollapsed: false });
    sync();
  });

  sync();
  return { sync };
}
