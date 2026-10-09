/**
 * resize.js — Pointer-drag resize utility for sidebar and panel dock.
 *
 * Uses pointer capture so dragging never gets stuck when cursor
 * moves outside the handle. Updates a CSS variable AND the element's
 * inline style so the rest of the layout responds immediately.
 */

/**
 * @param {HTMLElement} handle        The drag handle element.
 * @param {HTMLElement} target        The element being resized.
 * @param {"width"|"height"} dim      Which dimension to resize.
 * @param {{
 *   min: number,
 *   max: number,
 *   cssVar?: string,
 *   onDone?: (size: number) => void,
 *   reverse?: boolean
 * }} opts
 *   reverse=true means dragging right shrinks the target (for the dock, which
 *   is on the right side — dragging left grows it, dragging right shrinks it).
 */
export function setupResize(handle, target, dim, opts) {
  const { min, max, cssVar, onDone, reverse = false } = opts;

  let startPos = 0;
  let startSize = 0;

  handle.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    startPos = dim === "width" ? e.clientX : e.clientY;
    startSize = target.getBoundingClientRect()[dim];
    handle.classList.add("dragging");
    handle.setPointerCapture(e.pointerId);
  });

  handle.addEventListener("pointermove", (e) => {
    if (!handle.hasPointerCapture(e.pointerId)) return;
    const current = dim === "width" ? e.clientX : e.clientY;
    const delta = reverse ? startPos - current : current - startPos;
    const newSize = Math.min(max, Math.max(min, startSize + delta));
    target.style[dim] = `${newSize}px`;
    if (cssVar) {
      document.documentElement.style.setProperty(cssVar, `${newSize}px`);
    }
  });

  handle.addEventListener("pointerup", (e) => {
    if (!handle.hasPointerCapture(e.pointerId)) return;
    handle.classList.remove("dragging");
    const finalSize = parseFloat(target.style[dim]) || startSize;
    onDone?.(finalSize);
  });

  handle.addEventListener("lostpointercapture", () => {
    handle.classList.remove("dragging");
  });
}
