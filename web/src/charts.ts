import { el, svg } from "./format";

export interface BarRow {
  label: string;
  value: number;
  display: string;
  color?: string;
  tip?: string;
  note?: string;
}

/** Horizontal bars: label, thin bar from a shared baseline, value at the tip. */
export function bars(rows: BarRow[], options: { max?: number; label: string }): HTMLElement {
  const max = options.max ?? Math.max(...rows.map((row) => row.value), 1e-9);
  const list = el("div", { class: "bars", role: "table", "aria-label": options.label });
  for (const row of rows) {
    const bar = el("span", { class: "bar", style: `width:${Math.max(row.value > 0 ? 0.6 : 0, (row.value / max) * 100)}%;${row.color ? `background:${row.color}` : ""}` });
    const track = el("div", { class: "bar-track", role: "cell", tabindex: "0", "data-tip": row.tip ?? `${row.display}\n${row.label}` }, [
      bar,
      el("span", { class: "bar-value num" }, [row.display]),
    ]);
    list.append(
      el("div", { class: "bar-row", role: "row" }, [
        el("div", { class: "bar-label", role: "rowheader" }, [row.label, row.note ? el("span", { class: "muted" }, [row.note]) : null]),
        track,
      ]),
    );
  }
  return list;
}

export interface Segment {
  label: string;
  share: number;
  color: string;
  hatch?: boolean;
}

/** One stacked bar with a legend that carries the values. */
export function stack(segments: Segment[], label: string, format: (share: number) => string): HTMLElement {
  const bar = el("div", { class: "stack", role: "img", "aria-label": label });
  const legend = el("ul", { class: "stack-legend" });
  for (const segment of segments) {
    if (segment.share > 0) {
      bar.append(
        el("span", {
          class: segment.hatch ? "hatch" : "",
          style: `flex:${segment.share};background-color:${segment.color}`,
          tabindex: "0",
          "data-tip": `${format(segment.share)}\n${segment.label}`,
        }),
      );
    }
    legend.append(
      el("li", {}, [
        el("i", { class: segment.hatch ? "hatch" : "", style: `background-color:${segment.color}` }),
        el("span", { class: "num" }, [format(segment.share)]),
        ` ${segment.label}`,
      ]),
    );
  }
  return el("div", { class: "stack-wrap" }, [bar, legend]);
}

function niceMax(value: number): number {
  if (value <= 0) return 1;
  const power = 10 ** Math.floor(Math.log10(value));
  for (const step of [1, 2, 2.5, 5, 10]) if (value <= step * power) return step * power;
  return 10 * power;
}

export interface ColumnSeries {
  label: string;
  color: string;
  values: number[];
}

/**
 * Columns over the 24 hours of the day. The second series is drawn inside
 * the first, which works because it is always a subset of it.
 */
export function hourColumns(outer: ColumnSeries, inner: ColumnSeries, unit: string, format: (v: number) => string): HTMLElement {
  const width = 640;
  const height = 230;
  const left = 34;
  const bottom = 26;
  const top = 10;
  const plotH = height - bottom - top;
  const slot = (width - left) / 24;
  const max = niceMax(Math.max(...outer.values));
  const chart = svg("svg", { viewBox: `0 0 ${width} ${height}`, class: "columns", role: "img", "aria-label": `${outer.label} and ${inner.label} by hour of day, ${unit}` });
  for (let i = 0; i <= 4; i += 1) {
    const value = (max * i) / 4;
    const y = top + plotH - (value / max) * plotH;
    chart.append(svg("line", { x1: left, x2: width, y1: y, y2: y, class: i === 0 ? "axis" : "grid" }));
    const tick = svg("text", { x: left - 6, y: y + 4, "text-anchor": "end" });
    tick.textContent = format(value);
    chart.append(tick);
  }
  const column = (x: number, w: number, value: number, color: string) => {
    const h = (value / max) * plotH;
    const r = Math.min(3, h);
    const y = top + plotH - h;
    return svg("path", { d: `M${x},${top + plotH}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${top + plotH}Z`, fill: color });
  };
  outer.values.forEach((value, hour) => {
    const x = left + hour * slot;
    chart.append(column(x + 3, slot - 6, value, outer.color));
    chart.append(column(x + 3 + (slot - 6) * 0.25, (slot - 6) * 0.5, inner.values[hour], inner.color));
    chart.append(
      svg("rect", {
        x,
        y: top,
        width: slot,
        height: plotH,
        fill: "transparent",
        tabindex: 0,
        "data-tip": `${format(value)} ${outer.label.toLowerCase()}\n${format(inner.values[hour])} ${inner.label.toLowerCase()}\n${labelFor(hour)}–${labelFor(hour + 1)}`,
      }),
    );
  });
  for (const hour of [0, 3, 6, 9, 12, 15, 18, 21]) {
    const text = svg("text", { x: left + hour * slot + slot / 2, y: height - 8, "text-anchor": "middle" });
    text.textContent = labelFor(hour);
    chart.append(text);
  }
  const legend = el("ul", { class: "legend-row" }, [
    el("li", {}, [el("i", { style: `background:${outer.color}` }), outer.label]),
    el("li", {}, [el("i", { style: `background:${inner.color}` }), inner.label]),
  ]);
  return el("div", { class: "chart" }, [legend, chart]);
}

function labelFor(hour: number): string {
  const h = hour % 24;
  if (h === 0) return "12 am";
  if (h === 12) return "noon";
  return h < 12 ? `${h} am` : `${h - 12} pm`;
}

export interface Dot {
  x: number;
  y: number;
  size: number;
  label: string;
  tip: string;
  named: boolean;
}

/** Dots with a surface ring; the few named ones are labelled directly. */
export function dotPlot(dots: Dot[], axes: { x: string; y: string; xMax: number; yFormat: (v: number) => string; label: string }): HTMLElement {
  const width = 640;
  const height = 300;
  const left = 52;
  const bottom = 40;
  const top = 18;
  const right = 16;
  const plotW = width - left - right;
  const plotH = height - bottom - top;
  const chart = svg("svg", { viewBox: `0 0 ${width} ${height}`, class: "dots", role: "img", "aria-label": axes.label });
  for (const value of [0, 0.25, 0.5, 0.75, 1]) {
    const y = top + plotH - value * plotH;
    chart.append(svg("line", { x1: left, x2: width - right, y1: y, y2: y, class: value === 0 ? "axis" : "grid" }));
    const tick = svg("text", { x: left - 6, y: y + 4, "text-anchor": "end" });
    tick.textContent = axes.yFormat(value);
    chart.append(tick);
  }
  // The axis starts a little left of zero so a dot at zero does not sit on the tick labels.
  const xMin = -0.05 * axes.xMax;
  const scaleX = (value: number) => left + ((Math.min(value, axes.xMax) - xMin) / (axes.xMax - xMin)) * plotW;
  for (let value = 0; value <= axes.xMax; value += 10) {
    const x = scaleX(value);
    const tick = svg("text", { x, y: top + plotH + 16, "text-anchor": "middle" });
    tick.textContent = String(value);
    chart.append(tick);
  }
  const xTitle = svg("text", { x: left + plotW / 2, y: height - 4, "text-anchor": "middle", class: "axis-title" });
  xTitle.textContent = axes.x;
  chart.append(xTitle);
  const sizeMax = Math.max(...dots.map((dot) => dot.size), 1);
  const sorted = [...dots].sort((a, b) => b.size - a.size);
  for (const dot of sorted) {
    const cx = scaleX(dot.x);
    const cy = top + plotH - dot.y * plotH;
    const r = 4 + 9 * Math.sqrt(dot.size / sizeMax);
    chart.append(svg("circle", { cx, cy, r, class: "dot" }));
    if (dot.named) {
      const text = svg("text", { x: cx + r + 4, y: cy + 4, class: "dot-label" });
      text.textContent = dot.label;
      chart.append(text);
    }
  }
  for (const dot of sorted) {
    const cx = scaleX(dot.x);
    const cy = top + plotH - dot.y * plotH;
    chart.append(svg("circle", { cx, cy, r: 13, fill: "transparent", tabindex: 0, "data-tip": dot.tip }));
  }
  return el("div", { class: "chart" }, [el("p", { class: "chart-title" }, [axes.y]), chart]);
}

/** Histogram columns for the height check. */
export function histogram(bins: { lo: number; n: number }[], binWidth: number, xLabel: string): HTMLElement {
  const width = 640;
  const height = 200;
  const left = 40;
  const bottom = 40;
  const top = 8;
  const plotW = width - left - 8;
  const plotH = height - bottom - top;
  const max = niceMax(Math.max(...bins.map((bin) => bin.n)));
  const slot = plotW / bins.length;
  const chart = svg("svg", { viewBox: `0 0 ${width} ${height}`, class: "columns", role: "img", "aria-label": xLabel });
  for (let i = 0; i <= 2; i += 1) {
    const value = (max * i) / 2;
    const y = top + plotH - (value / max) * plotH;
    chart.append(svg("line", { x1: left, x2: width - 8, y1: y, y2: y, class: i === 0 ? "axis" : "grid" }));
    const tick = svg("text", { x: left - 6, y: y + 4, "text-anchor": "end" });
    tick.textContent = String(Math.round(value));
    chart.append(tick);
  }
  bins.forEach((bin, index) => {
    const h = (bin.n / max) * plotH;
    const x = left + index * slot;
    const edge = index === 0 ? `${bin.lo} ft or lower` : index === bins.length - 1 ? `${bin.lo} ft or higher` : `${bin.lo} to ${bin.lo + binWidth} ft`;
    chart.append(svg("rect", { x: x + 1, y: top + plotH - h, width: slot - 2, height: h, rx: Math.min(2, h), class: "col" }));
    chart.append(svg("rect", { x, y: top, width: slot, height: plotH, fill: "transparent", tabindex: 0, "data-tip": `${bin.n} reports\n${edge}` }));
    if (index % 4 === 0) {
      const text = svg("text", { x, y: top + plotH + 14, "text-anchor": "middle" });
      text.textContent = String(bin.lo);
      chart.append(text);
    }
  });
  const title = svg("text", { x: left + plotW / 2, y: height - 4, "text-anchor": "middle", class: "axis-title" });
  title.textContent = xLabel;
  chart.append(title);
  return el("div", { class: "chart" }, [chart]);
}

/** A plain table: the same numbers as the chart, reachable without hovering. */
export function table(head: string[], rows: (string | Node)[][], numeric: number[] = []): HTMLTableElement {
  const out = el("table", { class: "data" });
  out.append(el("thead", {}, [el("tr", {}, head.map((text, i) => el("th", { scope: "col", class: numeric.includes(i) ? "r" : "" }, [text])))]));
  const body = el("tbody");
  for (const row of rows) {
    body.append(el("tr", {}, row.map((cell, i) => el("td", { class: numeric.includes(i) ? "r num" : "" }, [cell]))));
  }
  out.append(body);
  return out;
}
