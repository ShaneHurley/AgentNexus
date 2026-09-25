/** Log shell pane — read-only UX, stop, poll hook (G8). */

import { api, esc } from "../api.js";
import { registerPoller, unregisterPoller } from "../poll.js";

/**
 * @param {HTMLElement} host
 * @param {{ tab: object, visible: () => boolean }} ctx
 */
export function mountTerminalPane(host, ctx) {
  const sessionId = ctx.tab.sessionId;
  host.innerHTML = `
    <div class="ide-logshell">
      <div class="ide-logshell-chrome">
        <span class="ide-logshell-label">Log shell (read-only)</span>
        <span class="ide-logshell-state muted small" id="logState">…</span>
        <button type="button" id="logStopBtn">Stop</button>
      </div>
      <pre class="ide-logshell-view" id="logView" aria-readonly="true">Loading log…</pre>
      <p class="muted small">Output only — no stdin. Interactive PTY is on the roadmap.</p>
    </div>
  `;

  const view = host.querySelector("#logView");
  const stateEl = host.querySelector("#logState");
  const stopBtn = host.querySelector("#logStopBtn");
  const pollId = `log-${sessionId}`;

  async function refreshLog() {
    if (!sessionId) return;
    try {
      const [sess, logData] = await Promise.all([
        api(`/api/terminal/sessions/${encodeURIComponent(sessionId)}`),
        api(`/api/terminal/sessions/${encodeURIComponent(sessionId)}/log`),
      ]);
      stateEl.textContent = sess.state || "unknown";
      stopBtn.disabled = sess.state === "stopped";
      view.textContent = logData.log || "";
      view.scrollTop = view.scrollHeight;
    } catch (err) {
      stateEl.textContent = err.message;
    }
  }

  stopBtn.addEventListener("click", async () => {
    stopBtn.disabled = true;
    try {
      await api(`/api/terminal/sessions/${encodeURIComponent(sessionId)}/stop`, { method: "POST", body: "{}" });
      await refreshLog();
    } catch (err) {
      stateEl.textContent = err.message;
      stopBtn.disabled = false;
    }
  });

  registerPoller(pollId, {
    tab: "ide",
    visible: ctx.visible,
    fn: refreshLog,
  });

  refreshLog();

  return {
    destroy() {
      unregisterPoller(pollId);
    },
  };
}
