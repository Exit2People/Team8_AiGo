"use client";

import { useEffect, useState, type CSSProperties } from "react";
import { Printer } from "./Icons";
import { later } from "@/lib/pause";

/**
 * 가방 담기 → 프린터 (figma-plugin: 13-1 ~ 13-4, PACK 시간 · preview-bag-motion.png)
 * start — 확인 화면의 답 줄과 똑같은 자리 · 모양
 * fold  — 답 줄이 그 자리에서 `가방 카드`(232 × 64)로 접혀 위로 모이고, 아래에서 가방이 올라와요 (0.6)
 * pack  — 가방이 가운데로 올라오고, 카드가 하나씩 똑바로 쏙 들어가요. 처음 담은 카드가 가장 깊이, 다음 카드는 그 앞에 조금씩 위로.
 *         들어갈 때마다 가방이 부풀어요
 * close — 뒤판 위로 서 있던 뚜껑이 (끝에 똑딱이가 달린 채로) 앞으로 넘어와 입구를 덮어요. 안에 든 카드는 보이지 않아요
 * snap  — 똑딱이 단추를 딸깍 눌러 잠가요
 * morph — 가방 전체가 한 덩어리로 부드럽게 눌리며 납작하게 넓어져 프린터 몸체가 되고, 똑딱이는 작아지며 표시등이 돼요 (0.85)
 *         끝 무렵 진짜 프린터 그림으로 겹쳐 바뀌어요 → 찾기 화면 프린터 자리(24, 652, 345 × 84)와 같아요
 */
export type PackPhase = "start" | "fold" | "pack" | "close" | "snap" | "morph";

export type PackRow = { name: string; value: string; fix?: boolean };
/** 확인 화면에서 잰 답 줄 자리 (화면 393 × 852 좌표). vis가 false면 목록 밖에 있어 안 보이던 줄이에요 */
export type PackRect = { x: number; y: number; w: number; h: number; vis: boolean };

const CARD_FILL = ["#FFFFFF", "#F4F2EF", "#EDE9E2", "#DEDEDE", "#FFFFFF"];
const TILT = [-2, 1.5, -1, 2, -1.5, 1];
const BODY = "linear-gradient(to bottom, #3a3a3a 0%, #141414 40%, #0b0b0b 100%)";
const SPRING = "cubic-bezier(.34,1.2,.64,1)";
const EASE = "cubic-bezier(.42,0,.58,1)";
const SMOOTH = "cubic-bezier(.65,0,.35,1)"; // 천천히 시작해 천천히 끝나요

// 가방 (393 × 852 좌표)
const BAG = { cx: 196.5, w: 270, h: 320 };
const BAG_X = BAG.cx - BAG.w / 2;
const TOP = { start: 900, fold: 560, pack: 410 };
const CARD = { x: BAG.cx - 116, w: 232, h: 64 };
const DEPTH = 34; // 처음 담은 카드가 입구보다 이만큼 더 깊이 들어가요
const STACK = 8; // 다음 카드는 이만큼씩 위에 (그 앞에) 놓여요
// 뚜껑: 뒤판 윗부분과 38px 겹쳐 서 있다가, 아랫변(경첩)을 축으로 앞으로 넘어와요
const LID = { h: 130, overlap: 38 };
// 똑딱이: 닫힌 뚜껑 아랫변에 34px 걸치고 38px 내려와요 (60 × 72, 단추 가운데 30 · 39)
const TAB = { w: 60, h: 72, onLid: 34, cx: 30, cy: 39 };
// 찾기 화면의 프린터 자리와 표시등 가운데 (Icons Printer: 315, 56)
const PRINTER_AT = { left: 24, top: 652, width: 345, height: 84 };
const LED = { x: PRINTER_AT.left + 315, y: PRINTER_AT.top + 56 };
const TAB_LED_SCALE = 0.2;
// 가방 상자(TOP.pack 기준) → 프린터 상자로 눌러 펴는 변환
const SX = PRINTER_AT.width / BAG.w;
const SY = PRINTER_AT.height / BAG.h;
const SQUASH = `translate(${PRINTER_AT.left - BAG_X * SX}px, ${PRINTER_AT.top - TOP.pack * SY}px) scale(${SX}, ${SY})`;

const T = { fold: 600, wait1: 450, step: 420, afterDrop: 250, close: 560, snap: 600, morph: 850, end: 150 };

export default function Pack({
  rows,
  from,
  onPose,
  onDone,
}: {
  rows: PackRow[];
  from: PackRect[];
  onPose: (k: string | null) => void;
  onDone: () => void;
}) {
  const len = rows.length;
  const [phase, setPhase] = useState<PackPhase>("start");
  const [n, setN] = useState(0); // 가방에 들어간 카드 수
  const [bump, setBump] = useState(0);
  const [sok, setSok] = useState(0); // "쏙" 글자

  useEffect(() => {
    const ts: (() => void)[] = [];
    const at = (ms: number, fn: () => void) => ts.push(later(ms, fn)); // 배지 축하 중에는 멈춰요
    let t = 40;
    at(t, () => {
      setPhase("fold");
      onPose("pack1");
    });
    t += T.fold + T.wait1;
    at(t, () => {
      setPhase("pack");
      onPose("pack2");
    });
    for (let i = 1; i <= len; i++) {
      const d = t + 200 + (i - 1) * T.step;
      at(d, () => setN(i));
      at(d + 260, () => {
        setBump((b) => b + 1);
        setSok(i);
      });
    }
    t += 200 + len * T.step + T.afterDrop;
    at(t, () => {
      setSok(0);
      setPhase("close");
    });
    t += T.close;
    at(t, () => {
      setPhase("snap");
      onPose("pack3");
    });
    t += T.snap;
    at(t, () => {
      setPhase("morph");
      onPose("morph");
    });
    t += T.morph + T.end;
    at(t, onDone);
    return () => {
      ts.forEach((cancel) => cancel());
      onPose(null);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const started = phase !== "start";
  const packing = phase === "pack" || phase === "close" || phase === "snap";
  const flat = phase === "morph";
  const closed = phase === "close" || phase === "snap" || flat;
  const pressed = phase === "snap";
  const bagTop = !started ? TOP.start : phase === "fold" ? TOP.fold : TOP.pack;
  const mouth = bagTop + 90;
  const bumpCls = phase === "pack" && bump > 0 ? `pack-bump${bump % 2}` : "";

  // 접혀 모인 카드 자리: 위에서부터 차례로, 가방 위로 넘지 않게 간격을 줄여요
  const foldGap = len > 1 ? Math.min(56, (TOP.fold - CARD.h - 6 - 228) / (len - 1)) : 0;
  // 가방 안 자리: 처음 담은 카드가 가장 깊이, 다음 카드는 조금씩 위에
  const slot = (i: number) => mouth + DEPTH - i * STACK;
  // 담는 중에 남은 카드: 입구 바로 위에 다음 카드가 맨 아래 · 맨 앞, 나머지는 그 위로 (13-2처럼)
  const waitBottom = TOP.pack + 90 - CARD.h - DEPTH;
  const waitGap = (rem: number) => (rem > 1 ? Math.min(72, Math.max(24, (waitBottom - 110) / (rem - 1))) : 0);
  const waitY = (i: number) => waitBottom - (i - n) * waitGap(len - n);

  const lidTop = bagTop - LID.h + LID.overlap;
  const tabTop = lidTop + LID.h * 2 - TAB.onLid; // 닫힌 뚜껑에 달린 똑딱이의 화면 자리
  const tabCy = tabTop + TAB.cy;
  const pocketSub = phase === "pack" && n > 0 ? `${n}개째 담는 중` : closed ? `${len}개 다 담았어요` : "오늘의 선택";
  const rise = `top .6s ${EASE}`;

  return (
    <div className="abs" style={{ inset: 0, zIndex: 20, pointerEvents: "none" }} aria-hidden="true">
      {/* 가방 한 덩어리: 프린터가 될 때 통째로 부드럽게 눌려 납작해져요 */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          transformOrigin: "0 0",
          transform: flat ? SQUASH : "none",
          // 가방은 끝까지 불투명하게 두고, 위로 진짜 프린터가 다 겹친 뒤에 빠져요 (반투명하게 비치지 않게)
          opacity: flat ? 0 : 1,
          transition: flat ? `transform ${T.morph / 1000}s ${SMOOTH}, opacity .12s ${T.morph / 1000}s` : "none",
        }}
      >
        {/* 뒤판 */}
        <div
          className={bumpCls}
          style={{
            position: "absolute",
            zIndex: 10,
            left: BAG_X,
            top: bagTop,
            width: BAG.w,
            height: BAG.h,
            borderRadius: "38px 38px 50px 50px",
            background: BODY,
            boxShadow: "var(--sh-printer)",
            transformOrigin: "50% 100%",
            transition: rise,
          }}
        />

        {/* 카드 */}
        {rows.map((r, i) => {
          const f = from[i] ?? { x: 24, y: 262 + i * 54, w: 345, h: 48, vis: false };
          const inBag = i < n;
          let box: CSSProperties;
          if (!started) {
            box = { left: f.x, top: f.y, width: f.w, height: f.h, borderRadius: 14, transform: "none" };
          } else {
            const y = inBag ? slot(i) : packing ? waitY(i) : 228 + i * foldGap;
            const rot = inBag ? 0 : TILT[i % TILT.length];
            box = { left: CARD.x, top: y, width: CARD.w, height: CARD.h, borderRadius: 12, transform: `rotate(${rot}deg)` };
          }
          // 가방 안: 나중에 담은 카드가 앞. 밖: 담는 중엔 다음 카드가 맨 앞
          const z = inBag ? 30 + i : packing ? 80 + (len - i) : 80 + i;
          return (
            <div
              key={i}
              style={{
                position: "absolute",
                zIndex: z,
                background: started ? CARD_FILL[i % CARD_FILL.length] : "var(--white)",
                boxShadow: "var(--sh-row)",
                overflow: "hidden",
                opacity: closed || (!started && !f.vis) ? 0 : 1,
                transition: inBag
                  ? `top .5s cubic-bezier(.5,0,.25,1), transform .2s ${EASE}, opacity .2s .3s`
                  : `left .6s ${SPRING}, top .6s ${SPRING}, width .6s ${SPRING}, height .6s ${SPRING}, border-radius .6s, transform .6s ${SPRING}, background .4s, opacity .3s`,
                ...box,
              }}
            >
              {/* 확인 화면의 답 줄 모습 → 접히며 사라져요 */}
              <div
                style={{
                  position: "absolute",
                  left: 0,
                  top: 0,
                  width: f.w,
                  height: f.h,
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                  padding: "6px 10px 6px 16px",
                  opacity: started ? 0 : 1,
                  transition: "opacity .25s",
                }}
              >
                <span style={{ width: 104, flex: "none" }}>
                  <span className="t-label c-deep" style={{ display: "block" }}>
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <span className="t-item c-mute" style={{ display: "block", marginTop: 4, lineHeight: 1.25, wordBreak: "keep-all" }}>
                    {r.name}
                  </span>
                </span>
                <span className="t-answer" style={{ flex: 1, minWidth: 0, wordBreak: "keep-all" }}>
                  {r.value}
                </span>
                {r.fix && <span className="chip chip-soft">고치기</span>}
              </div>
              {/* 가방 카드 모습: 번호 · 항목 · 답을 한 줄에 (윗줄 24px만 보여도 읽혀요) */}
              <div style={{ position: "absolute", inset: 0, opacity: started ? 1 : 0, transition: "opacity .3s .15s" }}>
                <div style={{ position: "absolute", left: 14, right: 14, top: 2, height: 22, display: "flex", alignItems: "center", gap: 8 }}>
                  <span className="t-label c-deep" style={{ flex: "none" }}>
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <span className="t-item c-mute" style={{ flex: 1, minWidth: 0, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                    {r.name}
                  </span>
                  <span className="t-answer" style={{ flex: "none", maxWidth: 122, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", textAlign: "right" }}>
                    {r.value}
                  </span>
                </div>
                <span className="t-item c-mute" style={{ position: "absolute", right: 14, top: 42, opacity: 0.55 }}>
                  · · · · · ·
                </span>
              </div>
            </div>
          );
        })}

        {/* 주머니 입구 그늘 */}
        <div
          style={{
            position: "absolute",
            zIndex: 55,
            left: BAG_X + 8,
            top: mouth - 14,
            width: BAG.w - 16,
            height: 14,
            background: "linear-gradient(to bottom, rgba(17,17,17,0), rgba(17,17,17,.45))",
            transition: rise,
          }}
        />
        {/* 앞 주머니 */}
        <div
          className={bumpCls}
          style={{
            position: "absolute",
            zIndex: 60,
            left: BAG_X,
            top: mouth,
            width: BAG.w,
            height: BAG.h - 90,
            background: BODY,
            borderRadius: "16px 16px 50px 50px",
            boxShadow: "0 -8px 16px rgba(0,0,0,.5), inset 0 2px 0 rgba(255,255,255,.13)",
            transformOrigin: "50% 100%",
            transition: rise,
          }}
        >
          <div style={{ position: "absolute", inset: 10, border: "2px dashed rgba(222,222,222,.3)", borderRadius: "10px 10px 42px 42px" }} />
          <span className="abs center-x t-answer" style={{ top: 128, color: "rgba(222,222,222,.5)", whiteSpace: "nowrap" }}>
            담고의 가방
          </span>
          <span className="abs center-x t-item" style={{ top: 156, color: "rgba(222,222,222,.38)", whiteSpace: "nowrap" }}>
            {pocketSub}
          </span>
        </div>

        {/* 뚜껑: 담는 동안은 뒤판 위로 서 있고, 다 담기면 앞으로 넘어와 입구와 카드를 덮어요. 똑딱이는 처음부터 뚜껑 끝에 달려 있어요 */}
        <div
          style={{
            position: "absolute",
            zIndex: closed ? 70 : 12,
            left: BAG_X,
            top: lidTop,
            width: BAG.w,
            height: LID.h,
            transformOrigin: "50% 100%",
            transform: `perspective(900px) rotateX(${closed ? -180 : 0}deg)`,
            transition: `transform .55s cubic-bezier(.55,0,.35,1.12), ${rise}`,
          }}
        >
          <div
            style={{
              position: "absolute",
              inset: 0,
              background: BODY,
              borderRadius: "38px 38px 6px 6px",
              boxShadow: closed ? "0 -10px 18px rgba(0,0,0,.45)" : "none",
            }}
          >
            <div style={{ position: "absolute", inset: 9, border: "2px dashed rgba(222,222,222,.26)", borderRadius: "30px 30px 4px 4px" }} />
          </div>
          {/* 뚜껑이 넘어오면 위아래가 뒤집히니, 미리 거꾸로 달아 두어 닫혔을 때 바로 보여요.
              열려 있을 땐 가죽 혀가 뚜껑 끝 위로 솟아 있어요 */}
          <div
            style={{
              position: "absolute",
              left: BAG.w / 2 - TAB.cx,
              top: -(TAB.h - TAB.onLid),
              transform: "scaleY(-1)",
              opacity: flat ? 0 : 1,
            }}
          >
            <SnapTab pressed={pressed} />
          </div>
        </div>
      </div>

      {/* 진짜 프린터 (찾기 화면과 같은 그림 · 자리): 거의 다 눌린 가방 위로 겹쳐 나타나요 */}
      <div
        style={{
          position: "absolute",
          zIndex: 1,
          left: PRINTER_AT.left,
          top: PRINTER_AT.top,
          filter: "drop-shadow(0 14px 26px rgba(89,20,15,.45))",
          opacity: flat ? 1 : 0,
          transition: flat ? `opacity .3s ${(T.morph - 330) / 1000}s ${EASE}` : "none",
        }}
      >
        <Printer />
      </div>

      {/* 프린터가 될 때만: 뚜껑의 똑딱이와 같은 자리에서 이어받아 작아지며 표시등으로 가요 */}
      <div
        className={flat ? "pack-led" : undefined}
        style={{
          position: "absolute",
          zIndex: 90,
          left: flat ? LED.x - TAB.cx * TAB_LED_SCALE : BAG.cx - TAB.cx,
          top: flat ? LED.y - TAB.cy * TAB_LED_SCALE : tabTop,
          transformOrigin: "0 0",
          transform: flat ? `scale(${TAB_LED_SCALE})` : "none",
          opacity: flat ? 1 : 0,
          transition: flat ? `left ${T.morph / 1000}s ${SMOOTH}, top ${T.morph / 1000}s ${SMOOTH}, transform ${T.morph / 1000}s ${SMOOTH}` : "none",
        }}
      >
        <SnapTab pressed={false} />
      </div>

      {/* 소리 글자 */}
      {phase === "pack" && sok > 0 && (
        <span key={sok} className="t-answer pack-sound" style={{ position: "absolute", zIndex: 95, left: 334, top: 420, color: "var(--ink)" }}>
          쏙
        </span>
      )}
      {phase === "snap" && (
        <>
          <span className="t-answer pack-sound" style={{ position: "absolute", zIndex: 95, left: 338, top: tabCy - 17, color: "var(--ink)" }}>
            딸깍
          </span>
          <svg className="pack-sound" width="393" height="852" style={{ position: "absolute", zIndex: 95, left: 0, top: 0 }}>
            {[
              [-50, -13, -40, -7],
              [-54, 9, -42, 7],
              [50, -13, 40, -7],
              [54, 9, 42, 7],
            ].map(([x1, y1, x2, y2], k) => (
              <line key={k} x1={BAG.cx + x1} y1={tabCy + y1} x2={BAG.cx + x2} y2={tabCy + y2} stroke="rgba(255,255,255,.8)" strokeWidth={2.4} strokeLinecap="round" />
            ))}
          </svg>
        </>
      )}
    </div>
  );
}

/** 주황 가죽 똑딱이 (60 × 72): 접힌 부분 · 가죽 혀 · 바느질 · 금속 단추 (figma-plugin snapTab) */
function SnapTab({ pressed }: { pressed: boolean }) {
  return (
    <div style={{ position: "relative", width: TAB.w, height: TAB.h }}>
      <div style={{ position: "absolute", left: 7, top: 0, width: 46, height: 14, background: "var(--amber)", borderRadius: "7px 7px 0 0" }} />
      <div style={{ position: "absolute", left: 7, top: 0, width: 46, height: 14, background: "var(--ink)", opacity: 0.3, borderRadius: "7px 7px 0 0" }} />
      <div
        style={{
          position: "absolute",
          left: 4,
          top: 7,
          width: 52,
          height: 60,
          borderRadius: "9px 9px 26px 26px",
          background: "linear-gradient(to bottom, rgba(255,255,255,.14), rgba(255,255,255,0) 40%, rgba(17,17,17,.16)), var(--amber)",
          boxShadow: "0 6px 9px rgba(0,0,0,.5), inset 0 2px 0 rgba(255,255,255,.3)",
        }}
      />
      <div style={{ position: "absolute", left: 9, top: 12, width: 42, height: 50, border: "1.5px dashed rgba(255,255,255,.6)", borderRadius: "6px 6px 21px 21px" }} />
      <div
        style={{
          position: "absolute",
          left: 17,
          top: 26,
          width: 26,
          height: 26,
          borderRadius: 13,
          background: "radial-gradient(circle at 40% 35%, #fff, #dedede 50%, #8a8580)",
          boxShadow: pressed ? "0 1px 2px rgba(0,0,0,.5)" : "0 3px 5px rgba(0,0,0,.5)",
          transform: pressed ? "scale(.88)" : "none",
          transition: "transform .15s .1s, box-shadow .15s .1s",
        }}
      />
    </div>
  );
}
