/** Pure SVG time-series / bar charts for usage tab. */

import { esc } from "../api.js";

const PAD = { top: 16, right: 12, bottom: 28, left: 40 };

/**
 * @param {{ width?: number, height?: number, title?: string, points: { x: string, y: number }[] }} opts
 */
export function lineChart(opts) {
  const width = opts.width || 480;
  const height = opts.height || 160;
  const points = opts.points || [];
  const innerW = width - PAD.left - PAD.right;
  const innerH = height - PAD.top - PAD.bottom;

  if (!points.length) {
    return `<svg class="usage-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(opts.title || "chart")}"><text x="${PAD.left}" y="${PAD.top + 12}" class="chart-empty">No data</text></svg>`;
  }

  const ys = points.map((p) => p.y);
  const maxY = Math.max(1, ...ys);
  const stepX = points.length > 1 ? innerW / (points.length - 1) : 0;

  const coords = points.map((p, i) => {
    const x = PAD.left + i * stepX;
    const y = PAD.top + innerH - (p.y / maxY) * innerH;
    return { x, y, label: p.x };
  });

  const poly = coords.map((c) => `${c.x},${c.y}`).join(" ");
  const title = opts.title ? `<text x="${PAD.left}" y="12" class="chart-title">${esc(opts.title)}</text>` : "";

  const xLabels = coords
    .filter((_, i) => i === 0 || i === coords.length - 1 || coords.length <= 6)
    .map(
      (c) =>
        `<text x="${c.x}" y="${height - 6}" text-anchor="middle" class="chart-axis">${esc(String(c.label).slice(0, 10))}</text>`
    )
    .join("");

  return `<svg class="usage-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(opts.title || "chart")}">
    ${title}
    <line x1="${PAD.left}" y1="${PAD.top + innerH}" x2="${width - PAD.right}" y2="${PAD.top + innerH}" class="chart-axis-line"/>
    <line x1="${PAD.left}" y1="${PAD.top}" x2="${PAD.left}" y2="${PAD.top + innerH}" class="chart-axis-line"/>
    <polyline points="${poly}" fill="none" class="chart-line"/>
    ${xLabels}
  </svg>`;
}

/**
 * @param {{ width?: number, height?: number, title?: string, bars: { label: string, value: number }[] }} opts
 */
export function barChart(opts) {
  const width = opts.width || 480;
  const height = opts.height || 160;
  const bars = opts.bars || [];
  const innerW = width - PAD.left - PAD.right;
  const innerH = height - PAD.top - PAD.bottom;
  const title = opts.title ? `<text x="${PAD.left}" y="12" class="chart-title">${esc(opts.title)}</text>` : "";

  if (!bars.length) {
    return `<svg class="usage-chart" viewBox="0 0 ${width} ${height}" role="img">${title}<text x="${PAD.left}" y="${PAD.top + 20}" class="chart-empty">No data</text></svg>`;
  }

  const maxV = Math.max(1, ...bars.map((b) => b.value));
  const gap = 4;
  const barW = Math.max(8, (innerW - gap * (bars.length - 1)) / bars.length);

  const rects = bars
    .map((b, i) => {
      const h = (b.value / maxV) * innerH;
      const x = PAD.left + i * (barW + gap);
      const y = PAD.top + innerH - h;
      return `<rect x="${x}" y="${y}" width="${barW}" height="${h}" class="chart-bar" rx="2">
        <title>${esc(b.label)}: ${b.value}</title>
      </rect>`;
    })
    .join("");

  return `<svg class="usage-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(opts.title || "chart")}">
    ${title}
    <line x1="${PAD.left}" y1="${PAD.top + innerH}" x2="${width - PAD.right}" y2="${PAD.top + innerH}" class="chart-axis-line"/>
    ${rects}
  </svg>`;
}
