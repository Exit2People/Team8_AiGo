/** 기기 저장 (11_FRONTEND_SPEC 10절). 실패해도 화면은 이어져요 */

export function load<T>(key: string, fallback: T): T {
  try {
    const v = localStorage.getItem(key);
    return v == null ? fallback : (JSON.parse(v) as T);
  } catch {
    return fallback;
  }
}

export function save(key: string, v: unknown) {
  try {
    if (v == null || (Array.isArray(v) && v.length === 0)) localStorage.removeItem(key);
    else localStorage.setItem(key, JSON.stringify(v));
  } catch {
    /* 시크릿 창 등 */
  }
}

export function drop(key: string) {
  try {
    localStorage.removeItem(key);
  } catch {
    /* */
  }
}

export function today(d = new Date()) {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

export type Visit = { id: string; name: string; date: string; kind: string; from: string; min: number };

const VISITS = "aigo.visits";

export function readVisits(): Visit[] {
  const all = load<Visit[]>(VISITS, []);
  const cut = Date.now() - 30 * 86400_000;
  const keep = all.filter((v) => new Date(v.date + "T00:00:00").getTime() >= cut);
  if (keep.length !== all.length) save(VISITS, keep);
  return keep;
}

export function addVisit(v: Omit<Visit, "date">) {
  const d = today();
  const list = readVisits().filter((x) => !(x.id === v.id && x.date === d));
  list.unshift({ ...v, date: d });
  save(VISITS, list);
}

export function cancelVisit(id: string) {
  const d = today();
  save(
    VISITS,
    readVisits().filter((x) => !(x.id === id && x.date === d)),
  );
}

export type Stamp = { id: string; name: string; date: string; photo: string; text: string; tags: string[]; at: number };
const STAMPS = "aigo.stamps";
export function readStamps(): Record<string, Stamp> {
  return load<Record<string, Stamp>>(STAMPS, {});
}
export function saveStamp(s: Stamp) {
  const all = readStamps();
  all[`${s.id}@${s.date}`] = s;
  try {
    localStorage.setItem(STAMPS, JSON.stringify(all));
    return true;
  } catch {
    return false;
  }
}
export function removeStamp(key: string) {
  const all = readStamps();
  delete all[key];
  save(STAMPS, Object.keys(all).length ? all : null);
}

export function readBlocked(): string[] {
  return load<string[]>("aigo.blocked", []);
}
export function saveBlocked(list: string[]) {
  save("aigo.blocked", list);
}

/** 10.2 탈퇴 보관함 */
const BACKUP_KEYS = ["aigo.visits", "aigo.stamps", "aigo.blocked"];
export function backupDevice(uid: string) {
  try {
    const data: Record<string, string> = {};
    for (const k of BACKUP_KEYS) {
      const v = localStorage.getItem(k);
      if (v != null) data[k] = v;
      localStorage.removeItem(k);
    }
    localStorage.setItem(`aigo.backup.${uid}`, JSON.stringify({ until: Date.now() + 90 * 86400_000, data }));
  } catch {
    /* */
  }
}
export function restoreDevice(uid: string): boolean {
  try {
    const raw = localStorage.getItem(`aigo.backup.${uid}`);
    localStorage.removeItem(`aigo.backup.${uid}`);
    if (!raw) return false;
    const b = JSON.parse(raw) as { until: number; data: Record<string, string> };
    if (!b.until || b.until < Date.now()) {
      dropBadges(uid);
      return false;
    }
    for (const k of BACKUP_KEYS) if (b.data?.[k] != null) localStorage.setItem(k, b.data[k]);
    return true;
  } catch {
    return false;
  }
}
export function discardDevice(uid: string) {
  drop(`aigo.backup.${uid}`);
  dropBadges(uid);
}
export function sweepBackups() {
  try {
    for (let i = localStorage.length - 1; i >= 0; i--) {
      const k = localStorage.key(i);
      if (!k || !k.startsWith("aigo.backup.")) continue;
      let ok = false;
      try {
        const b = JSON.parse(localStorage.getItem(k) || "null");
        ok = !!b?.until && b.until > Date.now();
      } catch {
        ok = false;
      }
      if (!ok) discardDevice(k.slice("aigo.backup.".length));
    }
  } catch {
    /* */
  }
}
function dropBadges(uid: string) {
  const all = load<Record<string, unknown>>("aigo.badges", {});
  if (uid in all) {
    delete all[uid];
    save("aigo.badges", Object.keys(all).length ? all : null);
  }
}

export function uuid(): string {
  try {
    return crypto.randomUUID();
  } catch {
    return "c-" + Math.random().toString(36).slice(2) + Date.now().toString(36);
  }
}
