/**
 * 브라우저 막대(아이폰 사파리 상태 표시줄 자리 · 주소창 뒤, 안드로이드 theme-color) 색을
 * 화면에 실제로 보이는 색으로 맞춰요.
 *
 * 아이폰 사파리(iOS 26 이후)는 theme-color를 무시하고
 *  - 위: 화면 맨 위에 붙은 position: fixed 요소(높이 6px 이상, 숨기지 않은 것)의 색
 *  - 아래(와 그 요소가 없을 때 위): body 바탕색
 * 으로 칠하고, 페이지가 스크롤될 때 다시 읽어요.
 */

export type RGBA = [number, number, number, number];

/** 아이폰 · 아이패드 사파리 (안드로이드 제외, 데스크톱 모드 iPadOS는 MacIntel + 터치로 판별) */
export function isIOS(): boolean {
  if (typeof navigator === "undefined") return false;
  const ua = navigator.userAgent;
  if (/Android/.test(ua)) return false;
  return /iPhone|iPod|iPad/.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
}

let probe: HTMLElement | null = null;
/** 어떤 CSS 색 글자든 rgba 숫자로 (color-mix · color(srgb …) · transparent 모두) */
export function toRGBA(css: string): RGBA {
  const s = css.trim();
  let m = s.match(/^rgba?\(([^)]+)\)$/);
  if (!m) {
    if (!probe) {
      probe = document.createElement("i");
      probe.style.display = "none";
      document.body.appendChild(probe);
    }
    probe.style.color = "";
    probe.style.color = s;
    const c = getComputedStyle(probe).color;
    m = c.match(/^rgba?\(([^)]+)\)$/);
    if (!m) {
      const cs = c.match(/^color\(srgb\s+([\d.e-]+)\s+([\d.e-]+)\s+([\d.e-]+)(?:\s*\/\s*([\d.e-]+%?))?\)$/);
      if (cs) {
        const a = cs[4] === undefined ? 1 : cs[4].endsWith("%") ? parseFloat(cs[4]) / 100 : parseFloat(cs[4]);
        return [parseFloat(cs[1]) * 255, parseFloat(cs[2]) * 255, parseFloat(cs[3]) * 255, a];
      }
      return [0, 0, 0, 0];
    }
  }
  const t = m[1].split(/[\s,/]+/).filter(Boolean);
  const ch = (v: string) => (v.endsWith("%") ? (parseFloat(v) / 100) * 255 : parseFloat(v));
  const a = t[3] === undefined ? 1 : t[3].endsWith("%") ? parseFloat(t[3]) / 100 : parseFloat(t[3]);
  return [ch(t[0]), ch(t[1]), ch(t[2]), a];
}

export function toHex([r, g, b]: RGBA): string {
  return "#" + [r, g, b].map((v) => Math.round(Math.max(0, Math.min(255, v))).toString(16).padStart(2, "0")).join("");
}

/** 쉼표로 나누되 괄호 안은 그대로 */
function splitTop(s: string): string[] {
  const out: string[] = [];
  let depth = 0;
  let cur = "";
  for (const ch of s) {
    if (ch === "(") depth++;
    if (ch === ")") depth--;
    if (ch === "," && depth === 0) {
      out.push(cur.trim());
      cur = "";
    } else cur += ch;
  }
  if (cur.trim()) out.push(cur.trim());
  return out;
}

type Stop = { c: RGBA; at: number };
/** 위에서 아래로 가는 linear-gradient의 색 멈춤 자리 (0 ~ 1). 다른 방향은 null */
function gradientStops(img: string): Stop[] | null {
  const m = img.match(/^linear-gradient\((.*)\)$/);
  if (!m) return null;
  const parts = splitTop(m[1]);
  if (parts.length && /^(to |-?[\d.]+(deg|turn|rad))/.test(parts[0])) {
    const dir = parts.shift()!;
    if (!/^(to bottom|180deg|0\.5turn)$/.test(dir)) return null;
  }
  const stops: { c: RGBA; at: number | null }[] = parts.map((p) => {
    const pm = p.match(/^(.*?)\s+(-?[\d.]+)%$/);
    return pm ? { c: toRGBA(pm[1]), at: parseFloat(pm[2]) / 100 } : { c: toRGBA(p), at: null };
  });
  if (!stops.length) return null;
  if (stops[0].at === null) stops[0].at = 0;
  if (stops[stops.length - 1].at === null) stops[stops.length - 1].at = 1;
  // 자리 없는 멈춤은 앞뒤 사이에 고르게
  for (let i = 1; i < stops.length; i++) {
    if (stops[i].at !== null) continue;
    let j = i;
    while (stops[j].at === null) j++;
    const a = stops[i - 1].at!;
    const b = stops[j].at!;
    for (let k = i; k < j; k++) stops[k].at = a + ((b - a) * (k - i + 1)) / (j - i + 1);
  }
  return stops as Stop[];
}

function colorInStops(stops: Stop[], t: number): RGBA {
  if (t <= stops[0].at) return stops[0].c;
  for (let i = 1; i < stops.length; i++) {
    if (t <= stops[i].at) {
      const a = stops[i - 1];
      const b = stops[i];
      const u = b.at === a.at ? 1 : (t - a.at) / (b.at - a.at);
      return [0, 1, 2, 3].map((k) => a.c[k] + (b.c[k] - a.c[k]) * u) as RGBA;
    }
  }
  return stops[stops.length - 1].c;
}

/** 요소와 조상의 opacity를 곱한 값 */
function effOpacity(el: Element): number {
  let o = 1;
  for (let e: Element | null = el; e && e !== document.documentElement; e = e.parentElement) o *= parseFloat(getComputedStyle(e).opacity || "1");
  return o;
}

/** 한 요소가 그 점에 칠하는 바탕 층들 (아래 → 위 순서: 바탕색, 그 위 그라데이션) */
function layersAt(el: Element, y: number): RGBA[] {
  const cs = getComputedStyle(el);
  if (cs.visibility === "hidden") return [];
  const op = effOpacity(el);
  if (op <= 0.001) return [];
  const out: RGBA[] = [];
  const bc = toRGBA(cs.backgroundColor);
  if (bc[3] > 0) out.push([bc[0], bc[1], bc[2], bc[3] * op]);
  if (cs.backgroundImage && cs.backgroundImage !== "none") {
    const r = el.getBoundingClientRect();
    // 여러 겹이면 맨 위(첫째)가 가장 위라서 뒤에서부터
    for (const img of splitTop(cs.backgroundImage).reverse()) {
      const st = gradientStops(img);
      if (!st) continue;
      const t = r.height > 0 ? (y - r.top) / r.height : 0;
      const c = colorInStops(st, Math.max(0, Math.min(1, t)));
      if (c[3] > 0) out.push([c[0], c[1], c[2], c[3] * op]);
    }
  }
  return out;
}

/**
 * 화면의 한 점에 실제로 보이는 바탕색 — 겹친 요소를 위부터 보며 불투명한 바탕이 나올 때까지 모으고,
 * 반투명한 층(그라데이션 · opacity)까지 합쳐요. pointer-events: none인 바탕 층도 읽도록 잠깐 켜요.
 * skip: 읽지 않을 요소(막대 띠 자신)
 */
export function visibleColorAt(x: number, y: number, skip?: Element | null): RGBA {
  const root = document.documentElement;
  root.classList.add("bar-probe");
  let els: Element[];
  try {
    els = document.elementsFromPoint(x, y);
  } finally {
    root.classList.remove("bar-probe");
  }
  const stack: RGBA[] = []; // 위 → 아래
  for (const el of els) {
    if (skip && (el === skip || skip.contains(el))) continue;
    const ls = layersAt(el, y).reverse(); // 위 → 아래
    let opaque = false;
    for (const l of ls) {
      stack.push(l);
      if (l[3] >= 0.999) {
        opaque = true;
        break;
      }
    }
    if (opaque) break;
  }
  // 맨 아래(불투명)부터 위로 섞어요. 다 투명하면 흰색 위에
  let c: RGBA = [255, 255, 255, 1];
  for (let i = stack.length - 1; i >= 0; i--) {
    const [r, g, b, a] = stack[i];
    c = [c[0] * (1 - a) + r * a, c[1] * (1 - a) + g * a, c[2] * (1 - a) + b * a, 1];
  }
  return c;
}

/** 안드로이드 등: theme-color 메타를 새로 갈아 끼워요 (바뀐 걸 확실히 읽게) */
export function setThemeColor(color: string) {
  document.querySelectorAll('meta[name="theme-color"]').forEach((m) => m.remove());
  const m = document.createElement("meta");
  m.name = "theme-color";
  m.content = color;
  document.head.appendChild(m);
}

/** 사파리가 막대 색을 다시 읽게: 2px 자리를 잠깐 만들어 1px 내렸다 올리고, 자리를 지워요.
 *  html · body는 overflow: hidden이라 그대로는 스크롤되지 않아서, 그 한순간만 스크롤되게 풀어요 */
export function nudgeSafari() {
  const html = document.documentElement;
  const body = document.body;
  const prev = { hOver: html.style.overflow, bOver: body.style.overflow, bH: body.style.height };
  html.style.overflow = "auto";
  body.style.overflow = "visible";
  body.style.height = "calc(100% + 2px)";
  window.scrollTo(0, 1);
  requestAnimationFrame(() => {
    window.scrollTo(0, 0);
    requestAnimationFrame(() => {
      html.style.overflow = prev.hOver;
      body.style.overflow = prev.bOver;
      body.style.height = prev.bH;
      if (html.scrollTop) html.scrollTop = 0;
    });
  });
}
