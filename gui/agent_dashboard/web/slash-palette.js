/** Slash palette — type `/` to search skills and subagents. */

import { api, esc } from "./api.js";

/**
 * Attach slash palette to a textarea.
 * @param {HTMLTextAreaElement} textarea
 * @param {{ getAgentId: () => string }} opts
 * @returns {{ destroy: () => void, refresh: () => Promise<void> }}
 */
export function attachSlashPalette(textarea, opts) {
  if (!textarea) return { destroy() {}, refresh: async () => {} };

  const wrap = textarea.closest(".composer-prompt-wrap") || textarea.parentElement;
  if (wrap && getComputedStyle(wrap).position === "static") {
    wrap.style.position = "relative";
  }

  let palette = wrap?.querySelector(".slash-palette");
  if (!palette && wrap) {
    palette = document.createElement("div");
    palette.className = "slash-palette";
    palette.hidden = true;
    palette.setAttribute("role", "listbox");
    wrap.appendChild(palette);
  }

  let items = [];
  let filtered = [];
  let active = 0;
  let open = false;
  let query = "";

  async function load() {
    const agentId = opts.getAgentId?.() || "";
    try {
      const data = await api(
        `/api/setup/palette?agent_id=${encodeURIComponent(agentId || "daily-coder")}`
      );
      items = Array.isArray(data.items) ? data.items : [];
    } catch {
      items = [];
    }
  }

  function close() {
    open = false;
    query = "";
    if (palette) palette.hidden = true;
  }

  function renderList() {
    if (!palette) return;
    if (!filtered.length) {
      palette.innerHTML = `<div class="muted small" style="padding:8px 10px">No matches</div>`;
      palette.hidden = false;
      return;
    }
    palette.innerHTML = filtered
      .map(
        (it, i) =>
          `<button type="button" class="slash-palette-item${i === active ? " active" : ""}" data-idx="${i}" role="option" aria-selected="${i === active}">
            <span class="slash-palette-kind">${esc(it.kind || "")}</span>
            <span>${esc(it.label || it.id)}</span>
            <span class="muted small">${esc(it.token || "")}</span>
          </button>`
      )
      .join("");
    palette.hidden = false;
    palette.querySelectorAll("[data-idx]").forEach((btn) => {
      btn.addEventListener("mousedown", (e) => {
        e.preventDefault();
        insert(filtered[Number(btn.getAttribute("data-idx"))]);
      });
    });
  }

  function filterFromCaret() {
    const val = textarea.value;
    const pos = textarea.selectionStart || 0;
    const before = val.slice(0, pos);
    const m = before.match(/(?:^|\s)\/([^\s]*)$/);
    if (!m) {
      close();
      return false;
    }
    query = (m[1] || "").toLowerCase();
    open = true;
    filtered = items.filter((it) => {
      const hay = `${it.id} ${it.label} ${it.kind} ${it.token}`.toLowerCase();
      return !query || hay.includes(query);
    });
    active = 0;
    renderList();
    return true;
  }

  function insert(item) {
    if (!item) return;
    const val = textarea.value;
    const pos = textarea.selectionStart || 0;
    const before = val.slice(0, pos);
    const after = val.slice(pos);
    const m = before.match(/(?:^|\s)\/([^\s]*)$/);
    if (!m) {
      close();
      return;
    }
    const start = before.length - m[0].length + (m[0].startsWith(" ") || m[0].startsWith("\n") ? 1 : 0);
    // Keep leading whitespace from match
    const lead = m[0].match(/^(\s)/)?.[1] || "";
    const tokenStart = before.lastIndexOf("/");
    const newBefore = val.slice(0, tokenStart) + (item.token || `@${item.kind}:${item.id}`) + " ";
    textarea.value = newBefore + after;
    const caret = newBefore.length;
    textarea.setSelectionRange(caret, caret);
    textarea.focus();
    close();
    textarea.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function onInput() {
    filterFromCaret();
  }

  function onKeyDown(e) {
    if (!open) {
      if (e.key === "/") {
        // defer to input
        setTimeout(filterFromCaret, 0);
      }
      return;
    }
    if (e.key === "Escape") {
      e.preventDefault();
      close();
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      active = Math.min(filtered.length - 1, active + 1);
      renderList();
      return;
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      active = Math.max(0, active - 1);
      renderList();
      return;
    }
    if (e.key === "Enter" && filtered[active]) {
      e.preventDefault();
      insert(filtered[active]);
    }
  }

  function onBlur() {
    setTimeout(close, 150);
  }

  textarea.addEventListener("input", onInput);
  textarea.addEventListener("keydown", onKeyDown);
  textarea.addEventListener("blur", onBlur);

  load();

  return {
    destroy() {
      textarea.removeEventListener("input", onInput);
      textarea.removeEventListener("keydown", onKeyDown);
      textarea.removeEventListener("blur", onBlur);
      palette?.remove();
    },
    async refresh() {
      await load();
      if (open) filterFromCaret();
    },
  };
}
