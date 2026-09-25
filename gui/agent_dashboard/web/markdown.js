/** Safe markdown subset — all text escaped; no raw HTML passthrough. */

const esc = (s) =>
  String(s == null ? "" : s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );

function safeHref(raw) {
  const href = String(raw || "").trim();
  if (!href) return null;
  if (href.startsWith("#")) return esc(href);
  if (/^https?:\/\//i.test(href)) return esc(href);
  return null;
}

function inlineFormat(text) {
  let s = esc(text);
  s = s.replace(/`([^`]+)`/g, (_, code) => `<code>${esc(code)}</code>`);
  s = s.replace(/\*\*([^*]+)\*\*/g, (_, t) => `<strong>${esc(t)}</strong>`);
  s = s.replace(/\*([^*]+)\*/g, (_, t) => `<em>${esc(t)}</em>`);
  s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_, label, href) => {
    const safe = safeHref(href);
    if (!safe) return esc(`[${label}](${href})`);
    return `<a href="${safe}" rel="noopener noreferrer">${esc(label)}</a>`;
  });
  return s;
}

function isPipeRow(line) {
  const t = String(line || "").trim();
  return t.startsWith("|") && t.includes("|", 1);
}

function isSeparatorRow(line) {
  const t = String(line || "").trim();
  if (!t.includes("|")) return false;
  const cells = splitPipeRow(t);
  if (!cells.length) return false;
  return cells.every((c) => /^:?-{3,}:?$/.test(c.trim()));
}

function splitPipeRow(line) {
  let s = String(line || "").trim();
  if (s.startsWith("|")) s = s.slice(1);
  if (s.endsWith("|")) s = s.slice(0, -1);
  return s.split("|").map((c) => c.trim());
}

function renderTable(headerCells, bodyRows) {
  const thead = `<thead><tr>${headerCells
    .map((c) => `<th>${inlineFormat(c)}</th>`)
    .join("")}</tr></thead>`;
  const tbody = `<tbody>${bodyRows
    .map(
      (row) =>
        `<tr>${row.map((c) => `<td>${inlineFormat(c)}</td>`).join("")}</tr>`
    )
    .join("")}</tbody>`;
  return `<div class="table-wrap"><table class="md-table">${thead}${tbody}</table></div>`;
}

/**
 * @param {string} source
 * @returns {string} HTML string (safe subset only)
 */
export function renderMarkdown(source) {
  const lines = String(source || "").replace(/\r\n/g, "\n").split("\n");
  const out = [];
  let i = 0;
  let inCode = false;
  let codeBuf = [];

  while (i < lines.length) {
    const line = lines[i];

    if (line.trim().startsWith("```")) {
      if (inCode) {
        out.push(`<pre><code>${esc(codeBuf.join("\n"))}</code></pre>`);
        codeBuf = [];
        inCode = false;
      } else {
        inCode = true;
      }
      i += 1;
      continue;
    }
    if (inCode) {
      codeBuf.push(line);
      i += 1;
      continue;
    }

    if (!line.trim()) {
      i += 1;
      continue;
    }

    const hm = line.match(/^(#{1,6})\s+(.+)$/);
    if (hm) {
      const level = hm[1].length;
      out.push(`<h${level}>${inlineFormat(hm[2])}</h${level}>`);
      i += 1;
      continue;
    }

    if (
      isPipeRow(line) &&
      i + 1 < lines.length &&
      isSeparatorRow(lines[i + 1])
    ) {
      const header = splitPipeRow(line);
      i += 2;
      const body = [];
      while (i < lines.length && isPipeRow(lines[i]) && !isSeparatorRow(lines[i])) {
        body.push(splitPipeRow(lines[i]));
        i += 1;
      }
      out.push(renderTable(header, body));
      continue;
    }

    if (/^(-|\*)\s+/.test(line)) {
      const items = [];
      while (i < lines.length && /^(-|\*)\s+/.test(lines[i])) {
        items.push(`<li>${inlineFormat(lines[i].replace(/^(-|\*)\s+/, ""))}</li>`);
        i += 1;
      }
      out.push(`<ul>${items.join("")}</ul>`);
      continue;
    }

    if (/^\d+\.\s+/.test(line)) {
      const items = [];
      while (i < lines.length && /^\d+\.\s+/.test(lines[i])) {
        items.push(`<li>${inlineFormat(lines[i].replace(/^\d+\.\s+/, ""))}</li>`);
        i += 1;
      }
      out.push(`<ol>${items.join("")}</ol>`);
      continue;
    }

    const para = [];
    while (i < lines.length && lines[i].trim() && !lines[i].trim().startsWith("```")) {
      const l = lines[i];
      if (/^(#{1,6})\s+/.test(l) || /^(-|\*)\s+/.test(l) || /^\d+\.\s+/.test(l)) break;
      if (isPipeRow(l) && i + 1 < lines.length && isSeparatorRow(lines[i + 1])) break;
      para.push(l);
      i += 1;
    }
    out.push(`<p>${inlineFormat(para.join(" "))}</p>`);
  }

  if (inCode && codeBuf.length) {
    out.push(`<pre><code>${esc(codeBuf.join("\n"))}</code></pre>`);
  }

  return out.join("\n");
}
