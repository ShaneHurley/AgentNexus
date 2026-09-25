/** Hash router — #/home|agent|docs|apis|usage|ide (+ optional segments). */

export const APP_TABS = ["home", "agent", "docs", "apis", "usage", "ide"];

/**
 * @returns {{ tab: string, redirect: boolean, agentId: string, runId: string, doc: string }}
 */
export function parseHash(hash = window.location.hash) {
  const stripped = String(hash || "").replace(/^#/, "").replace(/^\/?/, "");
  const parts = stripped.split("/").filter(Boolean);
  const tab = (parts[0] || "home").toLowerCase();

  if (!APP_TABS.includes(tab)) {
    return { tab: "home", redirect: true, agentId: "", runId: "", doc: "" };
  }

  if (tab === "agent") {
    return {
      tab,
      redirect: false,
      agentId: parts[1] ? decodeURIComponent(parts[1]) : "",
      runId: parts[2] ? decodeURIComponent(parts[2]) : "",
      doc: "",
    };
  }

  if (tab === "docs") {
    return {
      tab,
      redirect: false,
      agentId: "",
      runId: "",
      doc: parts[1] ? decodeURIComponent(parts.slice(1).join("/")) : "",
    };
  }

  return { tab, redirect: false, agentId: "", runId: "", doc: "" };
}

export function hashFor(route) {
  const tab = route.tab || "home";
  if (tab === "agent") {
    const segs = ["agent"];
    if (route.agentId) segs.push(encodeURIComponent(route.agentId));
    if (route.runId) segs.push(encodeURIComponent(route.runId));
    return `#/${segs.join("/")}`;
  }
  if (tab === "docs" && route.doc) {
    return `#/docs/${encodeURIComponent(route.doc).replace(/%2F/gi, "/")}`;
  }
  return `#/${tab}`;
}

/**
 * @param {(route: ReturnType<typeof parseHash>) => void} onRoute
 */
export function initRouter(onRoute) {
  function dispatch() {
    const route = parseHash();
    if (route.redirect) {
      window.location.replace(hashFor({ tab: "home" }));
      return;
    }
    onRoute(route);
  }

  window.addEventListener("hashchange", dispatch);
  // Always mount the initial tab. Setting hash alone can miss hashchange when
  // the page loaded with an empty hash (common with start.py / browser open).
  if (!window.location.hash || window.location.hash === "#") {
    window.location.replace(hashFor({ tab: "home" }));
  }
  dispatch();

  return {
    navigate(route) {
      window.location.hash = hashFor(route);
    },
    syncTabButtons() {
      const route = parseHash();
      if (route.redirect) return;
      for (const btn of document.querySelectorAll("[data-tab]")) {
        const id = btn.getAttribute("data-tab");
        const selected = id === route.tab;
        btn.setAttribute("aria-selected", selected ? "true" : "false");
        btn.tabIndex = selected ? 0 : -1;
      }
    },
  };
}
