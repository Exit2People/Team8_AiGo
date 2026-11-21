/* design_handoff/1-svg/shapes · printer · barcode 를 코드 안 SVG로 (테마 색을 따라가게 코랄은 currentColor 대신 var(--coral)) */

export function CheckIcon({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 30 30" aria-hidden="true">
      <circle cx="15" cy="15" r="15" style={{ fill: "var(--coral)" }} />
      <path d="M8.5 15.5 L13 20 L21.5 10.5" stroke="#FFFFFF" strokeWidth="3.4" strokeLinecap="round" strokeLinejoin="round" fill="none" />
    </svg>
  );
}

export function PinIcon({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 30 30" aria-hidden="true">
      <circle cx="15" cy="15" r="15" style={{ fill: "var(--coral)" }} />
      <path d="M15 6.5 C11.2 6.5 8.6 9.3 8.6 12.8 C8.6 17.4 15 23.5 15 23.5 C15 23.5 21.4 17.4 21.4 12.8 C21.4 9.3 18.8 6.5 15 6.5 Z" fill="#FFFFFF" />
      <circle cx="15" cy="12.8" r="2.6" style={{ fill: "var(--coral)" }} />
    </svg>
  );
}

export function TileArrow({ color = "#111111" }: { color?: string }) {
  return (
    <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true">
      <path d="M6 16 L16 6 M8 6 H16 V14" stroke={color} strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" fill="none" />
    </svg>
  );
}

export function ChevronIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M9 5 L16 12 L9 19" stroke="#8A8580" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" fill="none" />
    </svg>
  );
}

export function KakaoIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true">
      <path d="M11 2.5 C5.8 2.5 1.6 5.8 1.6 9.9 C1.6 12.5 3.3 14.8 5.9 16.1 L4.9 19.8 C4.8 20.2 5.2 20.5 5.6 20.3 L10 17.3 C10.3 17.3 10.7 17.3 11 17.3 C16.2 17.3 20.4 14 20.4 9.9 C20.4 5.8 16.2 2.5 11 2.5 Z" fill="#111111" />
    </svg>
  );
}

/** 담고 얼굴 (프로필 동그라미 안) */
export function DamgoFace({ size = 52 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 52 52" aria-hidden="true">
      <g transform="translate(26 31) scale(0.3425) translate(-95 -97)">
        <circle cx="60" cy="32" r="22" fill="#FFFFFF" />
        <circle cx="126" cy="28" r="22" fill="#FFFFFF" />
        <path d="M22 112 C18 64 52 36 94 36 C138 36 170 62 168 108 C166 142 136 158 94 158 C50 158 24 144 22 112 Z" fill="#FFFFFF" />
        <path d="M22 112 C24 94 40 82 58 80 C74 78 84 88 94 84 C106 78 122 76 138 80 C156 86 168 96 168 108 C166 142 136 158 94 158 C50 158 24 144 22 112 Z" fill="#111111" />
        <ellipse cx="68" cy="117" rx="9.5" ry="15" transform="rotate(-8 68 117)" fill="#FFFFFF" />
        <ellipse cx="110" cy="114" rx="9.5" ry="15" transform="rotate(6 110 114)" fill="#FFFFFF" />
      </g>
    </svg>
  );
}

/** 티켓 프린터 (345×84, 화면 24·652) */
/** 출력 입구 틈의 세로 가운데 (프린터 위에서부터). 티켓은 여기서 잘려 나와요 (figma-plugin printerFront: y 680 · 높이 8) */
export const PRINTER_SLOT_Y = 32;

/**
 * 티켓 프린터 (345 × 84).
 * part="body"는 몸체만(티켓 뒤), part="front"는 출력 입구 · 테두리 · 표시등만(티켓 앞) 그려요.
 * 둘을 티켓 앞뒤로 겹쳐 두면 티켓이 입구 틈에서 정확히 나오는 것처럼 보여요.
 */
export function Printer({ led = true, part = "all" }: { led?: boolean; part?: "all" | "body" | "front" }) {
  const body = part !== "front";
  const front = part !== "body";
  return (
    <svg width="345" height="84" viewBox="0 0 345 84" aria-hidden="true" style={{ display: "block" }}>
      <defs>
        <linearGradient id="pr-body" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#3A3A3A" />
          <stop offset="0.4" stopColor="#141414" />
          <stop offset="1" stopColor="#0B0B0B" />
        </linearGradient>
        <linearGradient id="pr-lip" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#FFFFFF" stopOpacity="0.16" />
          <stop offset="1" stopColor="#FFFFFF" stopOpacity="0" />
        </linearGradient>
      </defs>
      {body && <rect width="345" height="84" rx="22" fill="url(#pr-body)" />}
      {front && (
        <>
          <rect x="12" y="28" width="321" height="8" rx="4" fill="#000000" />
          <rect x="12" y="35" width="321" height="6" rx="3" fill="url(#pr-lip)" />
          <circle cx="315" cy="56" r="4" fill="#F2A33A" style={{ opacity: led ? 1 : 0.25, transition: "opacity .2s" }} />
        </>
      )}
    </svg>
  );
}

const BARS = [
  [0, 3], [6, 1], [9, 2], [13, 1], [17, 1], [20, 3], [25, 1], [29, 2], [33, 2], [37, 1], [41, 1], [44, 2], [48, 3],
  [54, 1], [57, 1], [60, 2], [65, 1], [68, 3], [73, 1], [77, 1], [80, 2], [84, 1], [88, 2], [92, 3], [97, 1], [101, 1],
  [104, 2], [108, 1], [112, 3], [117, 2], [121, 1], [125, 1], [128, 2], [132, 1], [136, 1], [139, 3], [144, 2], [149, 1],
];

/** 티켓 바코드 (꾸밈, 150×30) */
export function Barcode() {
  return (
    <svg width="150" height="30" viewBox="0 0 150 30" aria-hidden="true">
      <g fill="#111111">
        {BARS.map(([x, w]) => (
          <rect key={x} x={x} y="0" width={w} height="30" />
        ))}
      </g>
    </svg>
  );
}

/** 티켓 종이 (313×584, 절취선 홈 y 422) */
export function TicketPaper() {
  return (
    <svg width="313" height="584" viewBox="0 0 313 584" aria-hidden="true" style={{ position: "absolute", inset: 0 }}>
      <defs>
        <linearGradient id="tk-paper" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#FFFEFB" />
          <stop offset="0.7" stopColor="#F6F3EE" />
          <stop offset="1" stopColor="#E8E4DD" />
        </linearGradient>
      </defs>
      <path
        d="M 0 18 C 0 8.06 8.06 0 18 0 L 295 0 C 304.94 0 313 8.06 313 18 L 313 410 C 306.37 410 301 415.37 301 422 C 301 428.63 306.37 434 313 434 L 313 584 L 0 584 L 0 434 C 6.63 434 12 428.63 12 422 C 12 415.37 6.63 410 0 410 Z"
        fill="url(#tk-paper)"
      />
    </svg>
  );
}

export function MicIcon({ on }: { on?: boolean }) {
  return (
    <svg width="26" height="26" viewBox="0 0 24 24" aria-hidden="true">
      <rect x="9" y="3" width="6" height="11" rx="3" fill={on ? "#FFFFFF" : "#111111"} />
      <path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21" stroke={on ? "#FFFFFF" : "#111111"} strokeWidth="2.2" strokeLinecap="round" fill="none" />
    </svg>
  );
}
