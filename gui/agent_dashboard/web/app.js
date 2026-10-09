/**
 * app.js — AgentNexus workspace bootstrap.
 *
 * Delegates everything to workspace.js.
 * Kept minimal so the original poll.js / api.js / state.js plumbing
 * that the existing adapters depend on remains intact.
 */

import { setToken, getToken } from "./api.js";
import { init as initWorkspace } from "./workspace.js";

// Restore any saved API token into the hidden compatibility input.
const hiddenToken = document.getElementById("token");
if (hiddenToken) hiddenToken.value = getToken();

// Boot the workspace.
initWorkspace().catch((err) => {
  // Surface boot errors visibly so they're not silently swallowed.
  const health = document.getElementById("health");
  if (health) {
    health.textContent = `boot error: ${err.message}`;
    health.className = "pill bad";
  }
  console.error("[AgentNexus] Boot error:", err);
});
