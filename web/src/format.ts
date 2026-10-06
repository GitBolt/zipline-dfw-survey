export function pct(share: number | null | undefined, digits = 0): string {
  if (share == null || Number.isNaN(share)) return "n/a";
  const value = share * 100;
  if (digits === 0 && value > 0 && value < 1) return "under 1%";
  return `${value.toFixed(digits)}%`;
}

export function num(value: number | null | undefined, digits = 0): string {
  if (value == null || Number.isNaN(value)) return "n/a";
  return value.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function feet(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "n/a";
  return `${Math.round(value).toLocaleString("en-US")} ft`;
}

/** Aircraft-minutes per day, written the way a person would say it. */
export function perDay(minutes: number): string {
  if (minutes <= 0) return "none";
  if (minutes < 1) return "under a minute a day";
  if (minutes < 90) return `${num(minutes)} min a day`;
  return `${num(minutes / 60, 1)} h a day`;
}

export function hourLabel(hour: number): string {
  const h = ((hour % 24) + 24) % 24;
  if (h === 0) return "midnight";
  if (h === 12) return "noon";
  return h < 12 ? `${h} am` : `${h - 12} pm`;
}

export function hourRange(from: number, toExclusive: number): string {
  return `${hourLabel(from)}–${hourLabel(toExclusive)}`;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

export function day(iso: string, weekday = false): string {
  const [year, month, date] = iso.slice(0, 10).split("-").map(Number);
  const text = `${date} ${MONTHS[(month ?? 1) - 1]}`;
  if (!weekday) return text;
  return `${DAYS[new Date(Date.UTC(year, (month ?? 1) - 1, date)).getUTCDay()]} ${text}`;
}

export function coord(lat: number, lon: number): string {
  return `${Math.abs(lat).toFixed(3)}°${lat >= 0 ? "N" : "S"} ${Math.abs(lon).toFixed(3)}°${lon >= 0 ? "E" : "W"}`;
}

type Child = Node | string | null | undefined | false;

export function el<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  attrs: Record<string, string> = {},
  children: Child[] = [],
): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === "class") node.className = value;
    else node.setAttribute(key, value);
  }
  for (const child of children) if (child) node.append(child);
  return node;
}

export function svg<K extends keyof SVGElementTagNameMap>(
  tag: K,
  attrs: Record<string, string | number> = {},
  children: (SVGElement | string)[] = [],
): SVGElementTagNameMap[K] {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, String(value));
  for (const child of children) node.append(child);
  return node;
}
