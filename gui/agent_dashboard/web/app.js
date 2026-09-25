/** App boot — header, hash router, tab viewport. */

import { api, getToken, setToken } from "./api.js";
import { initRouter, hashFor, APP_TABS } from "./router.js";
import * as agentTab from "./tabs/agent.js";
import * as homeTab from "./tabs/home.js";
import * as docsTab from "./tabs/docs.js";
import * as apisTab from "./tabs/apis.js";
import * as usageTab from "./tabs/usage.js";
import * as ideTab from "./tabs/ide.js";
import { setActiveAppTab } from "./poll.js";

const viewport = () => document.getElementById("viewport");

let activeTab = null;
let activeUnmount = null;
let suppressHashSync = false;

const TAB_LOADERS = {
  home: homeTab,
  agent: agentTab,
  docs: docsTab,
  apis: apisTab,
  usage: usageTab,
  ide: ideTab,
};

function setActiveTabButton(tab) {
  for (const btn of document.querySelectorAll(".app-tab")) {
    const id = btn.getAttribute("data-tab");
    const selected = id === tab;
    btn.setAttribute("aria-selected", selected ? "true" : "false");
    btn.tabIndex = selected ? 0 : -1;
  }
}

function unmountCurrent() {
  if (activeUnmount) {
    activeUnmount();
    activeUnmount = null;
  }
  activeTab = null;
  setActiveAppTab("");
  const vp = viewport();
  if (vp) vp.innerHTML = "";
}

function mountTab(route) {
  if (activeTab === route.tab) {
    setActiveAppTab(route.tab);
    setActiveTabButton(route.tab);
    const loader = TAB_LOADERS[route.tab];
    if (typeof loader?.syncRoute === "function") {
      loader.syncRoute(route);
    }
    return;
  }

  const loader = TAB_LOADERS[route.tab];
  if (!loader) return;

  unmountCurrent();

  activeTab = route.tab;
  setActiveAppTab(route.tab);
  setActiveTabButton(route.tab);

  const container = viewport();
  if (!container) return;

  if (route.tab === "agent") {
    if (activeUnmount) activeUnmount();
    agentTab.mount(container, {
      agentId: route.agentId,
      runId: route.runId,
      navigate: (r) => {
        if (suppressHashSync) return;
        suppressHashSync = true;
        window.location.hash = hashFor(r);
        suppressHashSync = false;
      },
    });
    activeUnmount = () => agentTab.unmount();
  } else {
    loader.mount(container, route);
    activeUnmount = loader.unmount || null;
  }
}

async function refreshHealth() {
  try {
    const health = await api("/api/health");
    const el = document.getElementById("health");
    el.textContent = `ok · ${health.agents} agents`;
    el.className = "pill ok";
  } catch {
    const el = document.getElementById("health");
    el.textContent = "offline";
    el.className = "pill bad";
  }
}

async function onGlobalRefresh() {
  await refreshHealth();
  if (activeTab === "agent") {
    await agentTab.refreshAgentTab();
  }
}

function wireHeader() {
  document.getElementById("token").value = getToken();
  document.getElementById("saveToken").addEventListener("click", () => {
    setToken(document.getElementById("token").value);
    onGlobalRefresh();
  });
  document.getElementById("refreshBtn").addEventListener("click", () => onGlobalRefresh());
}

function wireTabList() {
  const tablist = document.getElementById("appTablist");
  tablist.addEventListener("click", (e) => {
    const btn = e.target.closest(".app-tab");
    if (!btn) return;
    const tab = btn.getAttribute("data-tab");
    if (!APP_TABS.includes(tab)) return;
    window.location.hash = hashFor({ tab });
  });

  tablist.addEventListener("keydown", (e) => {
    const tabs = [...tablist.querySelectorAll(".app-tab")].filter(
      (el) => !el.hidden && el.offsetParent !== null
    );
    const idx = tabs.indexOf(document.activeElement);
    if (idx < 0) return;
    let next = idx;
    if (e.key === "ArrowRight") next = (idx + 1) % tabs.length;
    else if (e.key === "ArrowLeft") next = (idx - 1 + tabs.length) % tabs.length;
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = tabs.length - 1;
    else return;
    e.preventDefault();
    tabs[next].focus();
    tabs[next].click();
  });
}

function onRoute(route) {
  if (suppressHashSync) return;
  mountTab(route);
}

wireHeader();
wireTabList();
initRouter(onRoute);
refreshHealth();
