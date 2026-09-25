/** IDE AI panel — disabled send, banner, zero fetch (G6). */

export function mountAiSkeleton(container) {
  container.innerHTML = `
    <div class="ide-ai-panel">
      <p class="ide-ai-banner">Preview — not connected. No model calls from this panel.</p>
      <p class="muted small">Workbench honesty: this is not Agent steer. Use the Agent tab for live runs.</p>
      <div class="ide-ai-compose">
        <textarea disabled placeholder="AI chat (not connected)" rows="4" aria-label="AI message (disabled)"></textarea>
        <button type="button" disabled title="Not connected">Send</button>
      </div>
    </div>
  `;
}
