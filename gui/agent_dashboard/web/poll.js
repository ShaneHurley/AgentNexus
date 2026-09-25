/** Poll registry — visibility + active app tab (G8). */

const TICK_MS = 6000;
const pollers = new Map();
let activeAppTab = "home";
let timer = null;
let visibilityHooked = false;

function eligible(entry) {
  if (document.hidden) return false;
  if (!navigator.onLine) return false;
  if (entry.tab && entry.tab !== activeAppTab) return false;
  if (entry.visible && !entry.visible()) return false;
  return true;
}

async function tick() {
  for (const entry of pollers.values()) {
    if (!eligible(entry) || entry.inFlight) continue;
    entry.inFlight = true;
    try {
      await entry.fn();
    } catch {
      /* transient */
    } finally {
      entry.inFlight = false;
    }
  }
}

function ensureTimer() {
  if (timer) return;
  timer = setInterval(tick, TICK_MS);
  if (!visibilityHooked) {
    visibilityHooked = true;
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden) tick();
    });
  }
}

function stopTimerIfEmpty() {
  if (pollers.size === 0 && timer) {
    clearInterval(timer);
    timer = null;
  }
}

/** @param {string} tab */
export function setActiveAppTab(tab) {
  activeAppTab = tab || "home";
  if (!document.hidden) tick();
}

/**
 * @param {string} id
 * @param {{ fn: () => void | Promise<void>, tab?: string, visible?: () => boolean }} opts
 */
export function registerPoller(id, opts) {
  pollers.set(id, {
    fn: opts.fn,
    tab: opts.tab || null,
    visible: opts.visible || null,
    inFlight: false,
  });
  ensureTimer();
}

export function unregisterPoller(id) {
  pollers.delete(id);
  stopTimerIfEmpty();
}

export function runPollersNow() {
  return tick();
}
