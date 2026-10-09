/**
 * chat-panel.js — Renders the chat panel for one workspace session.
 *
 * Handles:
 *   - Message bubbles (user on right, agent on left)
 *   - Markdown rendering inside agent bubbles
 *   - Streaming text animation (word-by-word append)
 *   - Thinking / activity indicator with animated dots
 *   - Reference chips that open panel dock tabs
 *   - Composer textarea + send button + action pills
 *   - Slash-command hint
 */

import { renderMarkdown } from "./markdown.js";

const _esc = (s) =>
  String(s == null ? "" : s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );

/**
 * Format an ISO timestamp to a short readable time.
 * @param {string} iso
 */
function fmtTime(iso) {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

/**
 * Build the HTML for one message bubble.
 * @param {{ role: string, text: string, created_at?: string, status?: string, refs?: object[] }} msg
 */
function buildBubbleHTML(msg) {
  const isUser = msg.role === "user";
  const avatarIcon = isUser ? "👤" : "🤖";
  const bodyHtml = isUser
    ? `<div class="ws-msg-bubble">${_esc(msg.text)}</div>`
    : `<div class="ws-msg-bubble">${renderMarkdown(msg.text)}</div>`;

  const refsHtml = buildRefChipsHTML(msg.refs || []);
  const metaHtml = `<span class="ws-msg-meta">${_esc(fmtTime(msg.created_at))}${msg.status ? ` · ${_esc(msg.status)}` : ""}</span>`;

  return `
    <div class="ws-msg ${isUser ? "user" : "agent"}" data-msg-id="${_esc(msg.id || "")}">
      <div class="ws-msg-avatar" aria-hidden="true">${avatarIcon}</div>
      <div class="ws-msg-content">
        ${bodyHtml}
        ${refsHtml}
        ${metaHtml}
      </div>
    </div>
  `;
}

/**
 * Build ref-chip HTML for file/plan/url references attached to a message.
 */
function buildRefChipsHTML(refs) {
  if (!refs || !refs.length) return "";
  return `<div class="ws-msg-refs">${refs
    .map(
      (r) =>
        `<button class="ws-ref-chip" type="button"
           data-ref-type="${_esc(r.type || "code")}"
           data-ref-label="${_esc(r.label || r.path || r.url || "")}"
           data-ref-content="${_esc(r.content || "")}"
           data-ref-url="${_esc(r.url || "")}"
           data-ref-path="${_esc(r.path || "")}">
          ${r.type === "browser" ? "🌐" : r.type === "plan" ? "📋" : "📄"}
          ${_esc(r.label || r.path || r.url || "Open")}
        </button>`
    )
    .join("")}</div>`;
}

/**
 * Render the full chat panel into `container` for a given session.
 *
 * @param {HTMLElement} container
 * @param {{
 *   sessionId: string,
 *   agentId: string,
 *   agentName: string,
 *   messages: object[],
 *   thinking: boolean,
 *   thinkingLabel: string,
 * }} sessionData
 * @param {{
 *   onSend: (sessionId: string, text: string) => Promise<void>,
 *   onRefChipClick: (ref: object) => void,
 * }} handlers
 */
export function renderChatPanel(container, sessionData, handlers) {
  const { sessionId, agentName, messages, thinking, thinkingLabel } = sessionData;

  container.innerHTML = `
    <div class="ws-messages" id="wsMessages-${_esc(sessionId)}" role="log" aria-live="polite" aria-label="Chat with ${_esc(agentName)}">
      ${messages.map((m) => buildBubbleHTML(m)).join("")}
      ${thinking ? buildThinkingHTML(thinkingLabel) : ""}
    </div>
    <div class="ws-composer" id="wsComposer-${_esc(sessionId)}">
      <div class="ws-composer-row">
        <textarea
          class="ws-composer-input"
          id="wsInput-${_esc(sessionId)}"
          placeholder="Message ${_esc(agentName)}… (Ctrl+Enter to send, / for commands)"
          rows="2"
          aria-label="Message input"
        ></textarea>
        <button type="button" class="ws-send-btn" id="wsSend-${_esc(sessionId)}" title="Send (Ctrl+Enter)" aria-label="Send message">
          ➤
        </button>
      </div>
      <div class="ws-composer-actions">
        <button type="button" class="ws-composer-pill" data-action="approve" title="Approve waiting run">
          ✓ Approve
        </button>
        <button type="button" class="ws-composer-pill" data-action="open-code" title="Open code panel">
          📄 Code
        </button>
        <button type="button" class="ws-composer-pill" data-action="open-plan" title="Open plan panel">
          📋 Plan
        </button>
        <button type="button" class="ws-composer-pill" data-action="open-browser" title="Open browser panel">
          🌐 Browser
        </button>
        <span class="ws-composer-hint">Ctrl+Enter · /commands</span>
      </div>
    </div>
  `;

  scrollToBottom(container, sessionId);
  wireComposer(container, sessionId, handlers);
  wireRefChips(container, handlers.onRefChipClick);
}

/**
 * Build the HTML for the animated thinking indicator row.
 */
function buildThinkingHTML(label) {
  return `
    <div class="ws-thinking-row" id="wsThinking">
      <div class="ws-msg-avatar" aria-hidden="true">🤖</div>
      <div class="ws-thinking-dots" aria-label="${_esc(label || "Thinking…")}">
        <span></span><span></span><span></span>
      </div>
      <span class="ws-thinking-label">${_esc(label || "Thinking…")}</span>
    </div>
  `;
}

/**
 * Update just the thinking indicator without re-rendering everything.
 * @param {HTMLElement} container The .ws-chat-panel element.
 * @param {boolean} thinking
 * @param {string} label
 */
export function setThinkingState(container, thinking, label) {
  const msgEl = container.querySelector(".ws-messages");
  if (!msgEl) return;
  const existing = msgEl.querySelector("#wsThinking");
  if (thinking) {
    if (existing) {
      existing.querySelector(".ws-thinking-label").textContent = label || "Thinking…";
    } else {
      msgEl.insertAdjacentHTML("beforeend", buildThinkingHTML(label));
    }
    scrollToBottomEl(msgEl);
  } else {
    existing?.remove();
  }
}

/**
 * Append a single message bubble to an already-rendered chat panel.
 * @param {HTMLElement} container The .ws-chat-panel element.
 * @param {object} msg
 * @param {() => void} onRefChipClick
 */
export function appendMessageBubble(container, msg, onRefChipClick) {
  const msgEl = container.querySelector(".ws-messages");
  if (!msgEl) return;
  // Remove thinking indicator before appending agent reply
  if (msg.role !== "user") {
    msgEl.querySelector("#wsThinking")?.remove();
  }
  msgEl.insertAdjacentHTML("beforeend", buildBubbleHTML(msg));
  scrollToBottomEl(msgEl);
  // Wire any ref chips in the new bubble
  const newBubble = msgEl.lastElementChild;
  newBubble?.querySelectorAll(".ws-ref-chip").forEach((chip) => {
    chip.addEventListener("click", () => onRefChipClick(chipToRef(chip)));
  });
}

/**
 * Stream text word-by-word into the last agent bubble.
 * Call repeatedly as chunks arrive; creates the bubble on first call.
 * @param {HTMLElement} container The .ws-chat-panel element.
 * @param {string} chunk
 */
export function streamTextToLastBubble(container, chunk) {
  const msgEl = container.querySelector(".ws-messages");
  if (!msgEl) return;
  let streamBubble = msgEl.querySelector(".ws-streaming-bubble");
  if (!streamBubble) {
    // Create a new agent bubble for streaming
    const wrapper = document.createElement("div");
    wrapper.className = "ws-msg agent ws-streaming-msg";
    wrapper.innerHTML = `
      <div class="ws-msg-avatar" aria-hidden="true">🤖</div>
      <div class="ws-msg-content">
        <div class="ws-msg-bubble ws-streaming-bubble"></div>
        <span class="ws-msg-meta"></span>
      </div>`;
    msgEl.querySelector("#wsThinking")?.remove();
    msgEl.appendChild(wrapper);
    streamBubble = wrapper.querySelector(".ws-streaming-bubble");
  }
  // Append chunk as plain text (no markdown mid-stream)
  streamBubble.textContent += chunk;
  scrollToBottomEl(msgEl);
}

/**
 * Finalize a streaming bubble: convert its text content to rendered markdown.
 * @param {HTMLElement} container
 */
export function finalizeStreamBubble(container) {
  const streamBubble = container.querySelector(".ws-streaming-bubble");
  if (!streamBubble) return;
  const raw = streamBubble.textContent;
  streamBubble.innerHTML = renderMarkdown(raw);
  streamBubble.classList.remove("ws-streaming-bubble");
  const wrapper = streamBubble.closest(".ws-streaming-msg");
  if (wrapper) wrapper.classList.remove("ws-streaming-msg");
}

/** Render the home/empty screen shown when no session is active. */
export function renderHomeScreen(container, agents, onLaunch) {
  container.innerHTML = `
    <div class="ws-home-screen">
      <p class="ws-home-headline">Your Coding Workshop</p>
      <p class="ws-home-sub">Launch an agent to start a session, or click Launch All to spin them all up at once.</p>
      <div class="ws-home-grid" id="homeAgentGrid"></div>
    </div>
  `;
  const grid = container.querySelector("#homeAgentGrid");
  if (!grid) return;

  const icons = { "daily-coder": "⚙️", "research-forge": "🔬", "daily-task": "📋" };
  agents.forEach((a) => {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "ws-agent-card";
    card.innerHTML = `
      <div class="ws-agent-card-icon">${icons[a.id] || "🤖"}</div>
      <div class="ws-agent-card-name">${_esc(a.name)}</div>
      <div class="ws-agent-card-desc">${_esc(a.description || "")}</div>
    `;
    card.addEventListener("click", () => onLaunch(a.id));
    grid.appendChild(card);
  });
}

// ── Private helpers ───────────────────────────────────────────────────────────

function scrollToBottom(container, sessionId) {
  const el = container.querySelector(`#wsMessages-${CSS.escape(sessionId)}`);
  if (el) scrollToBottomEl(el);
}

function scrollToBottomEl(el) {
  el.scrollTop = el.scrollHeight;
}

function wireComposer(container, sessionId, handlers) {
  const input = container.querySelector(`#wsInput-${CSS.escape(sessionId)}`);
  const sendBtn = container.querySelector(`#wsSend-${CSS.escape(sessionId)}`);
  if (!input || !sendBtn) return;

  async function doSend() {
    const text = input.value.trim();
    if (!text) return;
    input.value = "";
    input.style.height = "";
    await handlers.onSend(sessionId, text);
  }

  sendBtn.addEventListener("click", doSend);

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      doSend();
    }
    // Auto-grow textarea
    setTimeout(() => {
      input.style.height = "auto";
      input.style.height = `${Math.min(160, input.scrollHeight)}px`;
    }, 0);
  });

  input.addEventListener("input", () => {
    input.style.height = "auto";
    input.style.height = `${Math.min(160, input.scrollHeight)}px`;
  });

  // Action pill buttons
  container.querySelectorAll("[data-action]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const action = btn.getAttribute("data-action");
      handlers.onAction?.(sessionId, action);
    });
  });
}

function wireRefChips(container, onRefChipClick) {
  container.querySelectorAll(".ws-ref-chip").forEach((chip) => {
    chip.addEventListener("click", () => onRefChipClick(chipToRef(chip)));
  });
}

function chipToRef(chip) {
  return {
    type: chip.dataset.refType || "code",
    label: chip.dataset.refLabel || "",
    content: chip.dataset.refContent || "",
    url: chip.dataset.refUrl || "",
    path: chip.dataset.refPath || "",
  };
}
