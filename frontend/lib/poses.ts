import raw from "@/data/poses.json";

/** data/poses.json 한 자세 (12_PLACEHOLDERS 3.1) */
export type Pose = {
  /** [회전 중심 X, Y, 배율(190×170 기준), 회전(도)] */
  h: [number, number, number, number];
  /** [시선 X, 시선 Y, 깜빡임] */
  e: [number, number, number];
  /** 꼬리 원 2개: [가운데 X, Y, 지름, 보임] */
  t: [number, number, number, number][];
  /** 앞발 2개: [가운데 X, Y, rx, ry, 회전, 보임] */
  p: [number, number, number, number, number, number][];
  /** 1이면 담고 전체 숨김 */
  x: number;
};

const POSES = raw as unknown as Record<string, Pose>;

const UP = new Map<Pose, Pose>();

/**
 * 꼬리 모양 (2026-11-21 사용자 그림): 작은 원 = 머리 쪽에 붙은 꼬리 뿌리,
 * 큰 원 = 뿌리에서 위 · 바깥쪽으로 이어져 부푼 꼬리 끝.
 * 그림 속 두 원의 비율 · 자리(큰 원 지름 80 기준): 작은 원은 큰 원 가운데에서 머리 쪽으로 10, 아래로 47, 지름 58.
 * 큰 원은 화면마다 디자인에서 꼬리를 둔 자리(poses.json 첫 원)에서 지름의 0.3배만큼 위로 올려 머리 위로 부푼 끝이 보이게 두고,
 * 작은 원을 그림 비율대로 그 아래 · 머리 쪽에 붙여요
 * → 화면 가장자리의 담고도 꼬리가 예전만큼 보여요.
 * 그런데 디자인 자리가 머리보다 아래인 화면(고민 · 찾는 중 · 도착 …)은 그렇게 두면 작은 원이 얼굴 밑에 매달려 떨어져 보여요.
 * 이때는 그림처럼 작은 원을 머리 옆(머리 기준 바깥 73, 아래 25)에 붙이고 큰 원을 그 위 · 바깥으로 이어요.
 */
const TIP_D = 80;
/** 메인(시작) 화면은 머리가 아주 커서 꼬리가 가려져요 → 꼬리만 오른쪽 위(오른쪽 귀 너머)로 빼요 [x, y] */
const TAIL_NUDGE: Record<string, [number, number]> = { s1: [28, -70], home: [28, -70], s1i: [28, -70] };
const NUDGED = new Map<Pose, [number, number]>(Object.entries(TAIL_NUDGE).filter(([k]) => POSES[k]).map(([k, v]) => [POSES[k], v]));
const ROOT_FROM_TIP: [number, number, number] = [-10, 47, 58]; // [바깥쪽 +x, 아래 +y, 지름]
/** 그림 속 작은 원 자리: 머리 SVG 가운데(95,97)에서 바깥 73 · 아래 25 */
const ROOT_ON_HEAD: [number, number] = [73, 25];

/** 머리 안쪽(대략 타원) 정도 — 1보다 크면 머리 밖이에요 */
function headEllipse([hx, hy, s, r]: Pose["h"], x: number, y: number): number {
  const a = (-r * Math.PI) / 180;
  const dx = x - hx;
  const dy = y - hy;
  const u = dx * Math.cos(a) - dy * Math.sin(a);
  const v = dx * Math.sin(a) + dy * Math.cos(a);
  return (u / (73 * s)) ** 2 + ((v - 4 * s) / (60 * s)) ** 2;
}

/** 꼬리 두 원을 [뿌리(작은 원), 끝(큰 원)]으로 다시 놓아요. poses.json은 그대로 두고 불러올 때만 고쳐요. */
function tailShape(p: Pose): Pose {
  const cached = UP.get(p);
  if (cached) return cached;
  const [base, , ...rest] = p.t;
  let out = p;
  if (base && base[3]) {
    const [hx, , , r] = p.h;
    const side = base[0] >= hx ? 1 : -1; // 꼬리가 머리 오른쪽이면 1
    const k = base[2] / TIP_D;
    const nudge = NUDGED.get(p) ?? [0, 0];
    const tx = base[0] + nudge[0];
    const ty = base[1] - base[2] * 0.3 + nudge[1];
    const a = (r * Math.PI) / 180; // 머리가 기울면 꼬리도 같이
    const x = side * ROOT_FROM_TIP[0] * k;
    const y = ROOT_FROM_TIP[1] * k;
    const root: Pose["t"][number] = [tx + x * Math.cos(a) - y * Math.sin(a), ty + x * Math.sin(a) + y * Math.cos(a), ROOT_FROM_TIP[2] * k, 1];
    const tip: Pose["t"][number] = [tx, ty, base[2], 1];
    if (!NUDGED.has(p) && headEllipse(p.h, root[0], root[1]) > 0.85) {
      // 작은 원이 머리 밖에 매달려 보이면: 머리 옆에 붙이고 큰 원을 그 위 · 바깥으로
      const s = p.h[2];
      const hx0 = side * ROOT_ON_HEAD[0] * s;
      const hy0 = ROOT_ON_HEAD[1] * s;
      const rx = hx + hx0 * Math.cos(a) - hy0 * Math.sin(a);
      const ry = p.h[1] + hx0 * Math.sin(a) + hy0 * Math.cos(a);
      const ux = -side * ROOT_FROM_TIP[0] * k;
      const uy = -ROOT_FROM_TIP[1] * k;
      const att: Pose["t"][number] = [rx, ry, ROOT_FROM_TIP[2] * k, 1];
      const top: Pose["t"][number] = [rx + ux * Math.cos(a) - uy * Math.sin(a), ry + ux * Math.sin(a) + uy * Math.cos(a), base[2], 1];
      out = { ...p, t: [att, top, ...rest] };
    } else out = { ...p, t: [root, tip, ...rest] };
  }
  UP.set(p, out);
  return out;
}

export function getPose(key: string): Pose {
  return tailShape(POSES[key] ?? POSES[key.replace(/(In|Top)$/, "")] ?? POSES.s1);
}

export function hasPose(key: string): boolean {
  return key in POSES;
}

/** 바탕 종류 (11_FRONTEND_SPEC 1.4): grad · flat · 코랄 단색이 끝나는 Y */
const GRAD = new Set(["s1", "home", "kwait", "arrive", "chatjoin", "login", "agree", "addr", "elogin", "sud"]);
const FLAT = new Set([
  "find", "wait", "s4p", "s4", "s4d", "gb1", "gbf", "gb2", "gbb", "press", "pack1", "pack2", "pack3", "morph",
  "stamped", "nextp", "next", "nextd",
]);
const END_Y: Record<string, number> = {
  loc: 450, locUp: 378, near: 260, gu: 260, st: 260, open: 260, body: 320, time: 320, q1: 320, fb: 320, ask: 520, ask2: 520,
  last: 250, fill: 480, tear: 700, route: 250, none: 520, off: 520, end: 520, mine: 220, mine2: 220,
  chat: 160, chatmenu: 160, my: 160, del: 160, su1: 250, myedit: 160, upload: 220, cut: 230, review: 220,
  sdetail: 220, nudge: 250, voice: 520,
};

export type Bg = { coralY: number; deep: number; warm: number };

export function bgFor(key: string): Bg {
  const k = key.replace(/(In|Top|i|t)$/, "");
  const base = GRAD.has(k) || GRAD.has(key) ? "grad" : FLAT.has(k) || FLAT.has(key) ? "flat" : "num";
  if (base === "grad") return { coralY: 0, deep: 1, warm: 1 };
  if (base === "flat") return { coralY: 0, deep: 0, warm: 0 };
  const end = END_Y[key] ?? END_Y[k] ?? (/^su\d$/.test(key) ? 250 : 320);
  return { coralY: end - 900, deep: 0, warm: 1 };
}
