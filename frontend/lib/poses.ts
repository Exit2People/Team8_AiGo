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
 * 꼬리는 늘 위를 향해요: 큰 원(꼬리 뿌리) 위에 작은 원(꼬리 끝)이 오도록 고쳐요.
 * - 끝이 뿌리보다 아래 있는 자세는 뿌리를 기준으로 위로 뒤집어요.
 * - 원이 하나뿐인 자세는 뿌리 위에 끝 원(0.8배)을 더해요.
 * poses.json은 그대로 두고 불러올 때만 고쳐요.
 */
function tailUp(p: Pose): Pose {
  const cached = UP.get(p);
  if (cached) return cached;
  const [base, tip, ...rest] = p.t;
  let out = p;
  if (base && base[3]) {
    const side = base[0] >= p.h[0] ? 1 : -1; // 꼬리가 머리 오른쪽이면 1
    let up: Pose["t"][number];
    if (tip && tip[3]) {
      up = tip[1] > base[1] ? [tip[0], base[1] - (tip[1] - base[1]), tip[2], 1] : tip;
    } else {
      up = [base[0] + side * base[2] * 0.08, base[1] - base[2] * 0.62, Math.round(base[2] * 0.8), 1];
    }
    // 두 원은 늘 하나로 붙어 있어요: 가운데 사이가 두 반지름 합의 0.7배를 넘지 않게 끝 원을 당겨요
    const dx = up[0] - base[0];
    const dy = up[1] - base[1];
    const dist = Math.hypot(dx, dy);
    const max = ((base[2] + up[2]) / 2) * 0.7;
    if (dist > max) up = [base[0] + (dx * max) / dist, base[1] + (dy * max) / dist, up[2], 1];
    out = { ...p, t: [base, up, ...rest] };
  }
  UP.set(p, out);
  return out;
}

export function getPose(key: string): Pose {
  return tailUp(POSES[key] ?? POSES[key.replace(/(In|Top)$/, "")] ?? POSES.s1);
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
  loc: 450, locUp: 378, near: 260, gu: 260, st: 260, body: 320, time: 320, q1: 320, fb: 320, ask: 520, ask2: 520,
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
