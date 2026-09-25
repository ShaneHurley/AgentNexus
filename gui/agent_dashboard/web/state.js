/** Session persistence — metadata only (no file bodies or log text). */

export const SESSION_KEYS = {
  agent: "ad_agent",
  run: "ad_run",
  runByAgent: "ad_run_by_agent",
  token: "ad_token",
  provider: "ad_provider",
  ideLayout: "ad_ide_layout",
  archivedRuns: "ad_archived_runs",
  railCollapsed: "ad_rail_collapsed",
  railAgentOpen: "ad_rail_agent_open",
  composerContext: "ad_composer_context",
  composerThinking: "ad_composer_thinking",
  showArchived: "ad_show_archived",
  agentSections: "ad_agent_sections",
  forcedSubagents: "ad_forced_subagents",
};

export function getItem(key) {
  return sessionStorage.getItem(key);
}

export function setItem(key, value) {
  try {
    sessionStorage.setItem(key, value);
    return true;
  } catch (err) {
    if (err && err.name === "QuotaExceededError") {
      try {
        sessionStorage.removeItem(SESSION_KEYS.ideLayout);
        sessionStorage.setItem(key, value);
        return true;
      } catch {
        return false;
      }
    }
    throw err;
  }
}

export function removeItem(key) {
  sessionStorage.removeItem(key);
}

export function getAgentId() {
  return getItem(SESSION_KEYS.agent) || "";
}

export function setAgentId(id) {
  if (id) setItem(SESSION_KEYS.agent, id);
  else removeItem(SESSION_KEYS.agent);
}

function loadRunByAgent() {
  try {
    const raw = getItem(SESSION_KEYS.runByAgent);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function saveRunByAgent(map) {
  setItem(SESSION_KEYS.runByAgent, JSON.stringify(map));
}

/** Active (one) session for an agent — the session the user Opened / set. */
export function getRunIdForAgent(agentId) {
  if (!agentId) return getItem(SESSION_KEYS.run) || "";
  const map = loadRunByAgent();
  if (map[agentId]) return map[agentId];
  // Legacy single-key fallback when agent matches current.
  const legacy = getItem(SESSION_KEYS.run) || "";
  if (legacy && getAgentId() === agentId) return legacy;
  return "";
}

export function setRunIdForAgent(agentId, runId) {
  if (!agentId) return;
  const map = loadRunByAgent();
  if (runId) map[agentId] = runId;
  else delete map[agentId];
  saveRunByAgent(map);
  // Keep legacy key in sync for the active agent.
  if (getAgentId() === agentId || !getAgentId()) {
    if (runId) setItem(SESSION_KEYS.run, runId);
    else removeItem(SESSION_KEYS.run);
  }
}

export function getRunId() {
  const agent = getAgentId();
  if (agent) return getRunIdForAgent(agent);
  return getItem(SESSION_KEYS.run) || "";
}

export function setRunId(id) {
  const agent = getAgentId();
  if (agent) {
    setRunIdForAgent(agent, id);
    return;
  }
  if (id) setItem(SESSION_KEYS.run, id);
  else removeItem(SESSION_KEYS.run);
}

export function getProvider() {
  return getItem(SESSION_KEYS.provider) || "mock";
}

export function setProvider(provider) {
  setItem(SESSION_KEYS.provider, provider || "mock");
}

const IDE_LAYOUT_DEFAULT = { version: 1 };

export function getIdeLayout() {
  const raw = getItem(SESSION_KEYS.ideLayout);
  if (!raw) return { ...IDE_LAYOUT_DEFAULT };
  try {
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === "object" && parsed.version === 1) {
      return parsed;
    }
  } catch {
    /* ignore corrupt layout */
  }
  return { ...IDE_LAYOUT_DEFAULT };
}

/** @param {Record<string, unknown>} layout metadata-only */
export function setIdeLayout(layout) {
  const payload = { version: 1, ...layout };
  const json = JSON.stringify(payload);
  if (json.length > 200_000) {
    return false;
  }
  return setItem(SESSION_KEYS.ideLayout, json);
}

/** localStorage map: `${agentId}:${runId}` → true */
function loadArchivedMap() {
  try {
    const raw = localStorage.getItem(SESSION_KEYS.archivedRuns);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function saveArchivedMap(map) {
  try {
    localStorage.setItem(SESSION_KEYS.archivedRuns, JSON.stringify(map));
    return true;
  } catch {
    return false;
  }
}

function archiveKey(agentId, runId) {
  return `${agentId}:${runId}`;
}

export function isRunArchived(agentId, runId) {
  if (!agentId || !runId) return false;
  return Boolean(loadArchivedMap()[archiveKey(agentId, runId)]);
}

export function archiveRun(agentId, runId) {
  if (!agentId || !runId) return;
  const map = loadArchivedMap();
  map[archiveKey(agentId, runId)] = true;
  saveArchivedMap(map);
}

export function unarchiveRun(agentId, runId) {
  if (!agentId || !runId) return;
  const map = loadArchivedMap();
  delete map[archiveKey(agentId, runId)];
  saveArchivedMap(map);
}

export function getShowArchived() {
  return getItem(SESSION_KEYS.showArchived) === "1";
}

export function setShowArchived(on) {
  setItem(SESSION_KEYS.showArchived, on ? "1" : "0");
}

export function getRailCollapsed() {
  return getItem(SESSION_KEYS.railCollapsed) === "1";
}

export function setRailCollapsed(on) {
  setItem(SESSION_KEYS.railCollapsed, on ? "1" : "0");
}

/** @returns {Record<string, boolean>} */
export function getRailAgentOpen() {
  try {
    const raw = getItem(SESSION_KEYS.railAgentOpen);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

export function setRailAgentOpen(agentId, open) {
  const map = getRailAgentOpen();
  map[agentId] = Boolean(open);
  setItem(SESSION_KEYS.railAgentOpen, JSON.stringify(map));
}

export function getComposerContext() {
  return getItem(SESSION_KEYS.composerContext) || "default";
}

export function setComposerContext(value) {
  setItem(SESSION_KEYS.composerContext, value || "default");
}

export function getComposerThinking() {
  return getItem(SESSION_KEYS.composerThinking) || "standard";
}

export function setComposerThinking(value) {
  setItem(SESSION_KEYS.composerThinking, value || "standard");
}

/** Agent-tab disclosure defaults: Runs + Waiting start collapsed. */
const SECTION_DEFAULTS = {
  runs: false,
  waiting: false,
  activity: true,
  steer: true,
};

/** @returns {Record<string, boolean>} */
export function getAgentSections() {
  try {
    const raw = getItem(SESSION_KEYS.agentSections);
    if (!raw) return { ...SECTION_DEFAULTS };
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return { ...SECTION_DEFAULTS };
    return { ...SECTION_DEFAULTS, ...parsed };
  } catch {
    return { ...SECTION_DEFAULTS };
  }
}

export function setAgentSection(id, open) {
  const map = getAgentSections();
  map[id] = Boolean(open);
  setItem(SESSION_KEYS.agentSections, JSON.stringify(map));
}

/** @returns {Record<string, string[]>} */
function loadForcedMap() {
  try {
    const raw = getItem(SESSION_KEYS.forcedSubagents);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

/** @param {string} agentId */
export function getForcedSubagents(agentId) {
  if (!agentId) return [];
  const map = loadForcedMap();
  const list = map[agentId];
  return Array.isArray(list) ? list.map(String) : [];
}

/** @param {string} agentId @param {string[]} ids */
export function setForcedSubagents(agentId, ids) {
  if (!agentId) return;
  const map = loadForcedMap();
  map[agentId] = Array.isArray(ids) ? ids.map(String) : [];
  setItem(SESSION_KEYS.forcedSubagents, JSON.stringify(map));
}