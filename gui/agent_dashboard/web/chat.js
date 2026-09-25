/** Conversation / steer thread. */

import { api, esc } from "./api.js";

export async function renderThread(agentId, runId) {
  const q = runId ? `?run_id=${encodeURIComponent(runId)}` : "";
  const msgs = await api(`/api/agents/${encodeURIComponent(agentId)}/thread${q}`);
  const el = document.getElementById("thread");
  if (!msgs.length) {
    el.innerHTML = `<p class="muted small">No messages yet. Send a steering note.</p>`;
    return;
  }
  el.innerHTML = msgs
    .map(
      (m) => `<div class="msg ${esc(m.role || "user")}">
      <div class="meta">${esc(m.role)} · ${esc(m.status)} · ${esc((m.created_at || "").slice(0, 19))}</div>
      <div>${esc(m.text)}</div>
    </div>`
    )
    .join("");
  el.scrollTop = el.scrollHeight;
}

export async function sendMessage(agentId, runId, text) {
  return api(`/api/agents/${encodeURIComponent(agentId)}/thread`, {
    method: "POST",
    body: JSON.stringify({ text, run_id: runId || "" }),
  });
}

export async function applyQueued(agentId, runId, { alsoApprove = false, alsoResume = false } = {}) {
  return api(`/api/agents/${encodeURIComponent(agentId)}/thread/apply`, {
    method: "POST",
    body: JSON.stringify({
      run_id: runId || "",
      also_approve: alsoApprove,
      also_resume: alsoResume,
    }),
  });
}
