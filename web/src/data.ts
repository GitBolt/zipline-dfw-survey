import type { Band, ClassGroup, RawCell } from "./types";

/** Class order the pipeline uses when it encodes cells. */
export const CLASSES = ["rotorcraft", "light", "small", "large", "unknown", "other"] as const;
export const LINKS = ["adsb_1090", "uat_or_adsr", "tisb_only", "mlat_only"] as const;

export const GROUPS: { key: Exclude<ClassGroup, "all"> | "other"; label: string; classes: number[]; color: string }[] = [
  { key: "rotorcraft", label: "Helicopters", classes: [0], color: "#eb6834" },
  { key: "light", label: "Light aircraft", classes: [1], color: "#2a78d6" },
  { key: "larger", label: "Larger aircraft", classes: [2, 3], color: "#1baf7a" },
  { key: "other", label: "No category", classes: [4, 5], color: "#9aa4ae" },
];

export function groupOf(classIndex: number): number {
  return GROUPS.findIndex((group) => group.classes.includes(classIndex));
}

export interface Cell {
  h: string;
  lat: number;
  lon: number;
  tier: number;
  inRule: boolean;
  inStandOff: boolean;
  lowestFt: number | null;
  lowAircraft: number;
  cruiseAircraft: number;
  /** Seconds by class group (4) and hour (24), per band. */
  low: Float32Array;
  cruise: Float32Array;
  lowTotal: number;
  cruiseTotal: number;
  /** Low-band seconds by link, in LINKS order. */
  links: [number, number, number, number];
  /** Low-band seconds by 100 ft bin, surface to 1,200 ft. */
  profile: number[];
  standOffSeconds: number;
}

function decode(pairs: number[] | undefined): { grid: Float32Array; total: number } {
  const grid = new Float32Array(4 * 24);
  let total = 0;
  if (pairs) {
    for (let i = 0; i < pairs.length; i += 2) {
      const code = pairs[i];
      const seconds = pairs[i + 1];
      const group = groupOf(Math.floor(code / 24));
      if (group < 0) continue;
      grid[group * 24 + (code % 24)] += seconds;
      total += seconds;
    }
  }
  return { grid, total };
}

export function decodeCells(raw: RawCell[]): Cell[] {
  return raw.map((cell) => {
    const low = decode(cell.lx);
    const cruise = decode(cell.cx);
    const links: [number, number, number, number] = [0, 0, 0, 0];
    for (let i = 0; i < (cell.k?.length ?? 0); i += 2) links[cell.k![i]] = cell.k![i + 1];
    const profile = new Array<number>(12).fill(0);
    for (let i = 0; i < (cell.p?.length ?? 0); i += 2) profile[cell.p![i]] = cell.p![i + 1];
    return {
      h: cell.h,
      lat: cell.lat,
      lon: cell.lon,
      tier: cell.t,
      inRule: cell.v === 1,
      inStandOff: cell.b === 1,
      lowestFt: cell.lh ?? null,
      lowAircraft: cell.ln ?? 0,
      cruiseAircraft: cell.cn ?? 0,
      low: low.grid,
      cruise: cruise.grid,
      lowTotal: low.total,
      cruiseTotal: cruise.total,
      links,
      profile,
      standOffSeconds: cell.so ?? 0,
    };
  });
}

export interface Selection {
  band: Band;
  group: ClassGroup;
  /** First hour kept, 0–23. */
  from: number;
  /** Last hour kept, 0–23, inclusive. */
  to: number;
}

export function groupIndex(group: ClassGroup): number {
  return group === "all" ? -1 : GROUPS.findIndex((item) => item.key === group);
}

/** Aircraft-seconds in a cell for the chosen band, class and hours. */
export function seconds(cell: Cell, selection: Selection): number {
  const grid = selection.band === "cruise" ? cell.cruise : cell.low;
  const wanted = groupIndex(selection.group);
  if (wanted < 0 && selection.from === 0 && selection.to === 23) {
    return selection.band === "cruise" ? cell.cruiseTotal : cell.lowTotal;
  }
  let total = 0;
  for (let group = 0; group < 4; group += 1) {
    if (wanted >= 0 && group !== wanted) continue;
    for (let hour = selection.from; hour <= selection.to; hour += 1) total += grid[group * 24 + hour];
  }
  return total;
}

export function aircraftIn(cell: Cell, band: Band): number {
  return band === "cruise" ? cell.cruiseAircraft : cell.lowAircraft;
}

/** Share of a cell's low-band time that was not direct 1090 MHz ADS-B. */
export function offBandShare(cell: Cell): number | null {
  const total = cell.links[0] + cell.links[1] + cell.links[2] + cell.links[3];
  if (total <= 0) return null;
  return (total - cell.links[0]) / total;
}

const EARTH_MI = 3958.7613;

export function milesBetween(lat0: number, lon0: number, lat1: number, lon1: number): number {
  const rad = Math.PI / 180;
  const dLat = (lat1 - lat0) * rad;
  const dLon = (lon1 - lon0) * rad;
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(lat0 * rad) * Math.cos(lat1 * rad) * Math.sin(dLon / 2) ** 2;
  return 2 * EARTH_MI * Math.asin(Math.sqrt(a));
}

export function bearing(lat0: number, lon0: number, lat1: number, lon1: number): string {
  const rad = Math.PI / 180;
  const y = Math.sin((lon1 - lon0) * rad) * Math.cos(lat1 * rad);
  const x =
    Math.cos(lat0 * rad) * Math.sin(lat1 * rad) -
    Math.sin(lat0 * rad) * Math.cos(lat1 * rad) * Math.cos((lon1 - lon0) * rad);
  const degrees = ((Math.atan2(y, x) / rad) + 360) % 360;
  return ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][Math.floor((degrees + 22.5) / 45) % 8];
}

/** A ring of points `miles` from a centre, for drawing a circle on the map. */
export function circle(lat: number, lon: number, miles: number, steps = 96): [number, number][] {
  const rad = Math.PI / 180;
  const d = miles / EARTH_MI;
  const ring: [number, number][] = [];
  for (let i = 0; i <= steps; i += 1) {
    const theta = (i / steps) * 2 * Math.PI;
    const lat1 = Math.asin(Math.sin(lat * rad) * Math.cos(d) + Math.cos(lat * rad) * Math.sin(d) * Math.cos(theta));
    const lon1 =
      lon * rad +
      Math.atan2(Math.sin(theta) * Math.sin(d) * Math.cos(lat * rad), Math.cos(d) - Math.sin(lat * rad) * Math.sin(lat1));
    ring.push([lon1 / rad, lat1 / rad]);
  }
  return ring;
}
