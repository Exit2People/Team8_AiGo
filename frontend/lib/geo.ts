import dongs from "@/data/dongs.json";
import { NEAR_RADIUS_KM, WALK_M_PER_MIN } from "./constants";
import type { Origin } from "./types";

export type Dong = { id: string; gu: string; name: string; lat: number; lng: number };
export const DONGS = dongs as Dong[];

const ko = new Intl.Collator("ko");
export const GUS: string[] = Array.from(new Set(DONGS.map((d) => d.gu))).sort(ko.compare);

export function dongsOf(gu: string): Dong[] {
  return DONGS.filter((d) => d.gu === gu).sort((a, b) => ko.compare(a.name, b.name));
}

export function dongToOrigin(d: Dong): Origin {
  return { id: d.id, name: d.name, type: "동", lines: [d.gu], lat: d.lat, lng: d.lng };
}

function haversineM(lat1: number, lng1: number, lat2: number, lng2: number) {
  const R = 6_371_000;
  const r = Math.PI / 180;
  const dLat = (lat2 - lat1) * r;
  const dLng = (lng2 - lng1) * r;
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(lat1 * r) * Math.cos(lat2 * r) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

export type NearDong = Dong & { distanceM: number; walkMin: number };

/** 4.2.1 — 좌표는 이 계산에만 써요 (어디에도 보내지 않아요) */
export function nearbyDongs(lat: number, lng: number): { outside: boolean; widened: boolean; list: NearDong[] } {
  const all = DONGS.map((d) => {
    const m = haversineM(lat, lng, d.lat, d.lng);
    return { ...d, distanceM: m, walkMin: Math.max(1, Math.round(m / WALK_M_PER_MIN)) };
  }).sort((a, b) => a.distanceM - b.distanceM);
  if (!all.length || all[0].distanceM > 5000) return { outside: true, widened: false, list: [] };
  const inR = all.filter((d) => d.distanceM <= NEAR_RADIUS_KM * 1000);
  if (inR.length) return { outside: false, widened: false, list: inR };
  return { outside: false, widened: true, list: [all[0]] };
}

export function distText(m: number) {
  return m >= 1000 ? `${(m / 1000).toFixed(1)}km` : `${Math.max(10, Math.round(m / 10) * 10)}m`;
}
