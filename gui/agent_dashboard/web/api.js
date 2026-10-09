/** Thin API client — swap this file to point at another gateway. */

// Remove credentials persisted by older dashboard versions.
try { sessionStorage.removeItem("ad_token"); } catch { /* Storage may be disabled. */ }
let TOKEN = "";

export function getToken() {
  return TOKEN;
}

export function setToken(value) {
  TOKEN = (value || "").trim();
  // Keep credentials only in memory; never persist them in browser storage.
}

export async function api(path, options = {}) {
  const opts = { ...options };
  opts.headers = {
    "Content-Type": "application/json",
    "X-Api-Token": TOKEN,
    ...(opts.headers || {}),
  };
  const response = await fetch(path, opts);
  const text = await response.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = { raw: text }; }
  if (!response.ok) {
    const err = new Error((data && data.error) || `${response.status} ${response.statusText}`);
    err.status = response.status;
    err.data = data;
    throw err;
  }
  return data;
}

export const esc = (s) =>
  String(s == null ? "" : s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );

export const short = (id) => esc(String(id || "").slice(0, 10));
