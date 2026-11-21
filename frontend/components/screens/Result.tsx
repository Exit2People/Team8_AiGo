"use client";

import { useEffect, useState, type CSSProperties } from "react";
import type { FlowApi } from "../Flow";
import { Barcode, Printer, PRINTER_SLOT_Y, TicketPaper } from "../Icons";
import { Caption, Secondary } from "../ui";
import { lastLeg, linesText, placeNameSize } from "@/lib/format";
import { wideIll } from "@/lib/illust";
import type { Candidate } from "@/lib/types";
import { later } from "@/lib/pause";

/** 티켓 한 장 (8.2) — 313×584 */
export function Ticket({ c, i, n, closed, expected }: { c: Candidate; i: number; n: number; closed: boolean; expected: number }) {
  const ill = wideIll(c.place.kind, c.place.name);
  const [src, setSrc] = useState<string>(c.place.photo && c.place.photo.startsWith("https") ? c.place.photo : ill);
  useEffect(() => {
    setSrc(c.place.photo && c.place.photo.startsWith("https") ? c.place.photo : ill);
  }, [c.place.id, c.place.photo, ill]);
  const legs = c.route?.legs ?? [];
  const last = lastLeg(c);
  const first = legs[0];
  const name = c.place.name;
  const size = placeNameSize(name);
  const transfers = c.route?.transfers ?? 0;
  return (
    // 티켓은 칸 위치가 정해진 인쇄물 모양이라 글씨 크기 설정과 상관없이 기준 크기로 그려요(넘치거나 겹치지 않게)
    <div style={{ position: "relative", width: 313, height: 584, filter: "drop-shadow(0 10px 16px rgba(89,20,15,.3))", ["--fs" as string]: 1, ["--fs-t" as string]: 1 }}>
      <TicketPaper />
      <div style={{ position: "absolute", left: 12, top: 12, width: 289, height: 170, borderRadius: 12, overflow: "hidden", background: "var(--chip)" }}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={src} alt="" referrerPolicy="no-referrer" onError={() => setSrc(ill)} style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }} />
        {expected > 0 && (
          <span className="chip" style={{ position: "absolute", left: 10, bottom: 10 }}>
            오늘 {expected}명이 여기 올 예정이에요
          </span>
        )}
      </div>
      <span className="abs t-mono c-tgray" style={{ left: 24, top: 208 }}>
        AI GO · 오늘의 나들이
      </span>
      <span className="abs t-tlabel c-tgray" style={{ right: 24, top: 208 }} aria-label={`후보 ${n}곳 가운데 ${i + 1}번째`}>
        후보 {i + 1} / {n}
      </span>
      <span className="abs t-count c-deep" style={{ left: 24, top: 230 }}>
        오늘은 여기 어때요?
      </span>
      <h1
        className="abs"
        tabIndex={-1}
        style={{
          left: 22,
          right: 20,
          top: 250,
          height: 66,
          display: "flex",
          alignItems: "center",
          fontSize: size,
          fontWeight: 900,
          lineHeight: 1.05,
          letterSpacing: "-0.05em",
          overflow: "hidden",
          wordBreak: "keep-all",
        }}
      >
        <span style={{ display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" }}>{name}</span>
      </h1>
      <span className="abs chip" style={{ left: 24, top: 322, background: "var(--chip)", color: "var(--ink)" }}>
        {c.place.kind} · {c.place.gu}
      </span>
      <p
        className="abs t-sub c-sub pre"
        style={{ left: 24, right: 20, top: 360, display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden", lineHeight: 1.35 }}
      >
        {c.reason}
      </p>
      <div className="abs" style={{ left: 20, width: 273, top: 421, borderTop: "2px dashed #C9C3BA" }} />
      {[
        ["노선", linesText(legs)],
        ["출구", last?.exit ? last.exit : "안내 없음"],
        ["걷기", `약 ${last?.walkMin ?? 0}분`],
      ].map(([k, v], n2) => (
        <div key={k} className="abs" style={{ left: 24 + n2 * 89, top: 440, width: 86 }}>
          <span className="t-tlabel c-tgray" style={{ display: "block" }}>
            {k}
          </span>
          {/* 가이드: 칸 이름 y 440 · 칸 값 y 456 (22 / 줄 높이 1) */}
          <p className="t-tvalue" style={{ position: "absolute", top: 16, left: 0, width: 86, fontSize: v.length > 5 ? 16 : 22, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
            {v}
          </p>
        </div>
      ))}
      {[
        ["타는 곳", first?.station ?? "출발 동"],
        ["갈아타기", transfers ? `${transfers}번` : "없음"],
        ["운영 상황", closed ? "닫음" : c.open?.today ?? "운영 시간 확인 필요"],
        // 가이드: 칸 값(456 ~ 478) 아래 489부터 19씩, 바코드(548) 위에서 끝나요
      ].map(([k, v], n2) => (
        <div key={k} className="abs" style={{ left: 24, right: 24, top: 489 + n2 * 19, height: 15, alignItems: "center", display: "flex", justifyContent: "space-between", gap: 8 }}>
          <span className="t-tmeta c-tgray" style={{ flex: "none" }}>
            {k}
          </span>
          <span className="t-tinfo" style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", color: k === "운영 상황" && closed ? "var(--coral-deep)" : undefined }}>
            {v}
          </span>
        </div>
      ))}
      <div className="abs" style={{ left: 74, top: 548 }}>
        <Barcode />
      </div>
    </div>
  );
}

/** 티켓 절취선 높이 (티켓 위에서부터, 양끝 반원 홈 가운데) */
const TEAR_Y = 422;
/** 뜯긴 자리의 잔 톱니: 위 · 아래 조각이 같은 톱니로 맞물려요. 그림자까지 담기게 티켓 밖으로 넉넉히 잡아요 */
const TEAR_CLIP = (() => {
  const zig: string[] = [];
  for (let x = -24, k = 0; x <= 337; x += 5, k++) zig.push(`${x}px ${TEAR_Y + (k % 2 ? 3 : -3)}px`);
  return {
    top: `polygon(-24px -24px, 337px -24px, ${[...zig].reverse().join(", ")})`,
    bottom: `polygon(${zig.join(", ")}, 337px 640px, -24px 640px)`,
  };
})();

/** 결과 (4.4 result) */
export default function Result({ f }: { f: FlowApi }) {
  const { s } = f;
  const c = s.cands[s.idx];
  const key = `${s.receivedAt}-${s.idx}`;
  const printed = !!s.printed[key];
  const [phase, setPhase] = useState<"wait" | "up" | "done">(printed ? "done" : "wait");

  useEffect(() => {
    if (!c) return;
    f.loadSocial(c.place.id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [c?.place.id]);

  useEffect(() => {
    if (s.printed[key] || f.still) {
      setPhase("done");
      if (!s.printed[key]) f.set((p) => ({ printed: { ...p.printed, [key]: true } }));
      return;
    }
    setPhase("wait");
    // 담고가 한 손으로 프린터 단추를 누르고(press) → 티켓이 나오기 시작하면 사라져요(s4)
    f.setPoseOv("press");
    // 배지 축하 화면이 떠 있으면 티켓 출력도 그 자리에 멈춰요(later)
    const t1 = later(900, () => {
      setPhase("up");
      f.setPoseOv("s4");
    });
    const t2 = later(900 + 3000, () => {
      setPhase("done");
      f.set((p) => ({ printed: { ...p.printed, [key]: true } }));
      f.setPoseOv(null);
    });
    return () => {
      t1();
      t2();
      f.setPoseOv(null);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  if (!c) return null;
  const soc = s.social[c.place.id];
  const closed = s.closed.includes(c.place.id);
  const lastOne = s.idx >= s.cands.length - 1;
  const y = phase === "wait" ? 584 : 0;
  const shown = phase === "done";
  const gone = s.tearing || shown;
  // 티켓이 다 나오면 프린터는 아래로 내려가며 완전히 사라져요 (몸체 · 입구 같이)
  const printerStyle: CSSProperties = {
    left: 24,
    top: 652,
    opacity: gone ? 0 : 1,
    visibility: gone ? "hidden" : "visible",
    transform: gone ? "translateY(120px)" : "none",
    // 사라질 때만 천천히, 다음 후보에서 다시 나올 땐 바로 보여요
    transition: gone ? "opacity .6s, transform .7s, visibility 0s .7s" : "none",
    filter: "drop-shadow(0 14px 26px rgba(89,20,15,.45))",
  };

  return (
    <div className="content">
      {/* 프린터 몸체 (티켓 뒤) */}
      <div className="abs" style={printerStyle}>
        <Printer part="body" />
      </div>
      {/* 티켓 영역: 프린터 출력 입구 틈(y 652 + 32 = 684) 아래는 잘려서, 티켓이 틈에서 나오는 것처럼 보여요 */}
      <div className="abs" style={{ left: 24, top: 62, width: 345, height: 652 + PRINTER_SLOT_Y - 62, overflow: "hidden" }}>
        {!s.tearing && (
          <div
            style={{
              position: "absolute",
              left: 16,
              top: 38,
              transform: `translateY(${y}px)`,
              transition: phase === "up" ? "transform 3s cubic-bezier(.3,0,.2,1)" : "none",
            }}
          >
            <Ticket c={c} i={s.idx} n={s.cands.length} closed={closed} expected={soc?.expectedToday ?? 0} />
          </div>
        )}
      </div>
      {/* 프린터 입구 · 표시등 (티켓 앞) */}
      <div className="abs" style={{ ...printerStyle, filter: "none" }}>
        <Printer part="front" led={phase !== "wait"} />
      </div>
      {/* 티켓 뜯기: 잘리는 칸 밖에서, 프린터보다 위에 온전한 티켓을 절취선(톱니)대로 위아래로 나눠 그려요 */}
      {s.tearing &&
        (["top", "bottom"] as const).map((part) => (
          <div
            key={part}
            className={`abs tear-${part}`}
            style={{
              left: 24 + 16,
              top: 62 + 38,
              zIndex: 5,
              clipPath: TEAR_CLIP[part],
              transformOrigin: part === "top" ? `20% ${TEAR_Y}px` : `80% ${TEAR_Y}px`,
            }}
          >
            <Ticket c={c} i={s.idx} n={s.cands.length} closed={closed} expected={soc?.expectedToday ?? 0} />
          </div>
        ))}
      {/* 찌익: 벌어지는 절취선 자리, 조각들 위에 */}
      {s.tearing && (
        <span className="abs center-x t-title tear-word" style={{ top: 62 + 38 + TEAR_Y - 20, zIndex: 6, color: "var(--ink)" }} aria-hidden="true">
          찌익
        </span>
      )}
      {/* 뜯는 동안엔 방명록 칩 · 버튼을 감춰 아래 조각이 그 뒤로 지나가지 않게 해요 */}
      {shown && !s.tearing && (
        <>
          <div className="abs center-x" style={{ top: 704, display: "flex", justifyContent: "center" }}>
            {closed ? (
              <span className="chip" style={{ background: "var(--white)", color: "var(--coral-deep)", height: "auto", lineHeight: 1.35, padding: "6px 12px", whiteSpace: "normal", maxWidth: 345 }}>
                지금은 들어갈 수 있는 시간이 지났어요. 다른 곳을 봐 주세요.
              </span>
            ) : soc && soc.reviewCount > 0 ? (
              <button className="chip" style={{ background: "var(--white)", color: "var(--ink)" }} onClick={() => f.go({ k: "guestbook" })}>
                다녀온 사람들의 방명록 {soc.reviewCount}개 보기 ›
              </button>
            ) : soc ? (
              <span className="chip" style={{ background: "rgba(255,255,255,.6)", color: "var(--ink)" }}>
                아직 방명록이 비어 있어요
              </span>
            ) : null}
          </div>
          {lastOne ? (
            <Secondary y={756} w={closed ? 345 : 166} white onClick={() => f.search("stay", true)}>
              새로 찾기
            </Secondary>
          ) : (
            <Secondary y={756} w={closed ? 345 : 166} white onClick={() => f.showCand(s.idx + 1)}>
              다른 곳 보기
            </Secondary>
          )}
          {!closed && (
            <button className="btn btn-primary" style={{ left: 203, top: 756, width: 166, justifyContent: "center" }} onClick={() => f.choose()} disabled={s.tearing}>
              여기로 갈게요
            </button>
          )}
          {lastOne && s.cands.length >= 2 && (
            <Caption y={830} onClick={() => f.showCand(0)}>
              첫 번째 곳부터 다시 보기
            </Caption>
          )}
        </>
      )}
    </div>
  );
}
