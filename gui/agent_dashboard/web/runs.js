/** Runs + approvals + activity panels. */

import { api, esc, short } from "./api.js";

function resumeErrorMessage(err) {
  const data = err && err.data;
  const payload = data && data.error;
  if (payload && typeof payload === "object") {
    const code = payload.code || "";
    const msg = payload.message || err.message || "Resume failed";
    const failures = payload.details && payload.details.failures;
    if (Array.isArray(failures) && failures.length) {
      return `${code}: ${msg} — ${failures.join("; ")}`;
    }
    return code ? `${code}: ${msg}` : msg;
  }
  if (data && typeof data.error === "string") {
    return data.error;
  }
  return err.message || String(err);
}

export async function renderRuns(agentId, onSelectRun, selectedRunId, capabilities = []) {
  const canResume = capabilities.includes("resume");
  const runs = await api(`/api/agents/${encodeURIComponent(agentId)}/runs?limit=40`);
  const el = document.getElementById("runs");
  if (!runs.length) {
    el.innerHTML = `<p class="muted">No runs yet.</p>`;
    return runs;
  }
  el.innerHTML = `<table><thead><tr><th>Run</th><th>Status</th><th>Phase</th><th></th></tr></thead><tbody>
    ${runs
      .map((r) => {
        const klass =
          r.status === "FAILED" || r.status === "CANCELLED"
            ? "bad"
            : r.status === "COMPLETE" || r.status === "APPROVED"
              ? "ok"
              : "warn";
        const rowActive = r.run_id === selectedRunId ? "active" : "";
        const repoMeta = [];
        if (r.repo_path) repoMeta.push(esc(String(r.repo_path).slice(-48)));
        if (r.git_head) repoMeta.push(`<code>${esc(r.git_head)}</code>`);
        if (r.git_dirty === true) repoMeta.push('<span class="warn">dirty</span>');
        const repoLine = repoMeta.length
          ? `<div class="repo-meta muted">${repoMeta.join(" · ")}</div>`
          : "";
        return `<tr class="${rowActive}">
        <td><code>${short(r.run_id)}</code><br><span class="muted">${esc((r.request || "").slice(0, 70))}</span>${repoLine}</td>
        <td class="${klass}">${esc(r.status)}</td>
        <td>${esc(r.phase || "")}</td>
        <td>
          <button type="button" data-act="select" data-run="${esc(r.run_id)}">Open</button>
          ${canResume ? `<button type="button" data-act="resume" data-run="${esc(r.run_id)}">Resume</button>` : ""}
          <button type="button" data-act="cancel" data-run="${esc(r.run_id)}">Cancel</button>
        </td>
      </tr>`;
      })
      .join("")}
  </tbody></table>`;
  el.querySelectorAll("button").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const runId = btn.dataset.run;
      const act = btn.dataset.act;
      try {
        if (act === "select") onSelectRun(runId);
        if (act === "resume") {
          await api(`/api/agents/${encodeURIComponent(agentId)}/runs/${encodeURIComponent(runId)}/resume`, {
            method: "POST",
            body: "{}",
          });
          onSelectRun(runId);
        }
        if (act === "cancel") {
          await api(`/api/agents/${encodeURIComponent(agentId)}/runs/${encodeURIComponent(runId)}/cancel`, {
            method: "POST",
            body: "{}",
          });
          onSelectRun(runId);
        }
      } catch (err) {
        const msg =
          act === "resume" && (err.status === 403 || err.status === 404)
            ? resumeErrorMessage(err)
            : err.message || String(err);
        el.insertAdjacentHTML("afterbegin", `<p class="bad">${esc(msg)}</p>`);
      }
    });
  });
  return runs;
}

export async function renderApprovals(agentId, refresh) {
  const items = await api(`/api/agents/${encodeURIComponent(agentId)}/approvals`);
  const el = document.getElementById("approvals");
  if (!items.length) {
    el.innerHTML = `<p class="muted">Nothing waiting.</p>`;
    return;
  }
  el.innerHTML = `<table><thead><tr><th>Run</th><th>Kind</th><th></th></tr></thead><tbody>
    ${items
      .map(
        (a) => `<tr>
      <td><code>${short(a.run_id)}</code><br><span class="muted">${esc((a.summary || "").slice(0, 60))}</span></td>
      <td>${esc(a.kind || "")}</td>
      <td>
        <button type="button" data-rej="0" data-run="${esc(a.run_id)}">Approve</button>
        <button type="button" data-rej="1" data-run="${esc(a.run_id)}">Reject</button>
      </td>
    </tr>`
      )
      .join("")}
  </tbody></table>`;
  el.querySelectorAll("button").forEach((btn) => {
    btn.addEventListener("click", async () => {
      try {
        await api(
          `/api/agents/${encodeURIComponent(agentId)}/runs/${encodeURIComponent(btn.dataset.run)}/approve`,
          {
            method: "POST",
            body: JSON.stringify({ reject: btn.dataset.rej === "1", actor: "agent-dashboard" }),
          }
        );
        refresh();
      } catch (err) {
        el.insertAdjacentHTML(
          "afterbegin",
          `<p class="bad">${esc(err.message || String(err))}</p>`
        );
      }
    });
  });
}

export async function renderActivity(agentId, runId) {
  const q = runId ? `?run_id=${encodeURIComponent(runId)}&limit=40` : "?limit=40";
  const items = await api(`/api/agents/${encodeURIComponent(agentId)}/activity${q}`);
  const el = document.getElementById("activity");
  if (!items.length) {
    el.innerHTML = `<p class="muted">No activity.</p>`;
    return;
  }
  el.innerHTML = `<table><thead><tr><th>When</th><th>Role</th><th>Kind</th><th>Summary</th></tr></thead><tbody>
    ${items
      .slice()
      .reverse()
      .map(
        (i) => `<tr>
      <td class="muted">${esc((i.ts || "").slice(0, 19))}</td>
      <td>${esc(i.role || "")}</td>
      <td>${esc(i.kind || "")}</td>
      <td>${esc((i.summary || "").slice(0, 120))}</td>
    </tr>`
      )
      .join("")}
  </tbody></table>`;
}
