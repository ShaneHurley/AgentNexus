/** File editor — textarea + PUT save + dirty state. */

import { api, esc } from "../api.js";

/**
 * @param {HTMLElement} host
 * @param {{ tab: object, onDirty: (dirty: boolean) => void, onSaved: (mtime: string | null) => void }} ctx
 */
export function mountEditorPane(host, ctx) {
  host.innerHTML = `
    <div class="ide-editor">
      <div class="ide-editor-meta muted small" id="ideEditorMeta"></div>
      <textarea class="ide-editor-area" spellcheck="false" aria-label="File editor"></textarea>
      <div class="ide-editor-actions">
        <button type="button" class="primary" id="ideSaveBtn">Save</button>
        <span id="ideEditorStatus" class="muted small"></span>
      </div>
    </div>
  `;

  const area = host.querySelector(".ide-editor-area");
  const meta = host.querySelector("#ideEditorMeta");
  const status = host.querySelector("#ideEditorStatus");
  const saveBtn = host.querySelector("#ideSaveBtn");
  let loadedPath = "";
  let loadedRoot = "";
  let baseline = "";

  async function loadFile() {
    const { tab } = ctx;
    loadedRoot = tab.root;
    loadedPath = tab.path;
    meta.textContent = `${tab.root}:${tab.path}`;
    status.textContent = "Loading…";
    try {
      const q = new URLSearchParams({ root: tab.root, path: tab.path });
      const data = await api(`/api/workspace/file?${q}`);
      baseline = data.content ?? "";
      area.value = baseline;
      tab.mtime = data.mtime || tab.mtime;
      tab.dirty = false;
      ctx.onDirty(false);
      status.textContent = tab.mtime ? `mtime ${tab.mtime}` : "";
    } catch (err) {
      area.value = "";
      status.textContent = err.message;
      status.className = "bad small";
    }
  }

  area.addEventListener("input", () => {
    const dirty = area.value !== baseline;
    ctx.tab.dirty = dirty;
    ctx.onDirty(dirty);
    status.textContent = dirty ? "Unsaved changes" : tabMtimeLabel();
  });

  function tabMtimeLabel() {
    return ctx.tab.mtime ? `mtime ${ctx.tab.mtime}` : "";
  }

  saveBtn.addEventListener("click", async () => {
    if (!loadedRoot || !loadedPath) return;
    saveBtn.disabled = true;
    status.textContent = "Saving…";
    try {
      const q = new URLSearchParams({ root: loadedRoot, path: loadedPath });
      const data = await api(`/api/workspace/file?${q}`, {
        method: "PUT",
        body: JSON.stringify({ content: area.value }),
      });
      baseline = area.value;
      ctx.tab.dirty = false;
      ctx.tab.mtime = data.mtime || ctx.tab.mtime;
      ctx.onDirty(false);
      ctx.onSaved(ctx.tab.mtime);
      status.textContent = tabMtimeLabel() || "Saved";
      status.className = "muted small";
    } catch (err) {
      status.textContent = err.message;
      status.className = "bad small";
    } finally {
      saveBtn.disabled = false;
    }
  });

  loadFile();

  return {
    confirmClose() {
      if (!ctx.tab.dirty) return true;
      return window.confirm(`Discard unsaved changes in ${ctx.tab.label}?`);
    },
    reload: loadFile,
  };
}
