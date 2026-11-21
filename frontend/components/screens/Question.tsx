"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { FlowApi } from "../Flow";
import { TileArrow } from "../Icons";
import { Dots, Progress, Sheet, Sub } from "../ui";
import { BODY, DONT_KNOW, TIME, tileSize, titleSize, twoLines } from "@/lib/questions";
import { later } from "@/lib/pause";

type Props = { f: FlowApi; kind: "body" | "time" | "flex"; i?: number; edit?: boolean };

/** 몸 · 시간 · 질문 N (4.3, 5.2) */
export default function Question({ f, kind, i = 0, edit }: Props) {
  const { s } = f;
  const q = kind === "flex" ? s.qs[i] : null;
  const ready = kind !== "flex" || !!q;
  const base = kind === "flex" ? (q?.src === "ai" ? "q1" : "fb") : kind;
  // 등장 연출 (5.2): 질문이 가운데 크게 0.9초 → 제자리로 0.6초 → 선택지가 올라와요
  const [phase, setPhase] = useState<"in" | "top" | "base">(() => (edit || f.still || f.navDir.current === "back" ? "base" : "in"));
  const h1 = useRef<HTMLHeadingElement>(null);
  const subRef = useRef<HTMLParagraphElement>(null);
  const chipRef = useRef<HTMLSpanElement>(null);
  const [measured, setMeasured] = useState({ title: 0, sub: 0, chip: 0 });
  useLayoutEffect(() => {
    const read = () => {
      const next = { title: h1.current?.offsetHeight ?? 0, sub: subRef.current?.offsetHeight ?? 0, chip: chipRef.current?.offsetHeight ?? 0 };
      setMeasured((m) => (m.title === next.title && m.sub === next.sub && m.chip === next.chip ? m : next));
    };
    read();
    const ro = new ResizeObserver(read);
    for (const el of [h1.current, subRef.current, chipRef.current]) if (el) ro.observe(el);
    return () => ro.disconnect();
  });
  const [fx, setFx] = useState("none");
  useLayoutEffect(() => {
    if (!ready || phase !== "in") return;
    const el = h1.current;
    if (el) {
      const w = el.scrollWidth;
      const k = Math.min(1.75, 345 / Math.max(1, w));
      setFx(`translate(${196.5 - (369 - (w * k) / 2)}px, 336px) scale(${k})`);
    }
    f.setPoseOv(`${base}In`);
    const ts = [
      later(900, () => {
        setPhase("top");
        f.setPoseOv(`${base}Top`);
      }),
      later(900 + 600 + 80, () => {
        setPhase("base");
        f.setPoseOv(null);
      }),
    ];
    return () => {
      ts.forEach((cancel) => cancel());
      f.setPoseOv(null);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready]);

  useEffect(() => {
    if (kind === "flex" && !q) f.prepare(i);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kind, i, !!q]);

  const progress =
    kind === "body" ? <Progress on={2} text="2 / 4" right /> : kind === "time" ? <Progress on={3} text="3 / 4" right /> : <Progress on={4} text={`질문 ${i + 1}`} right bar={!!q && q.src !== "ai"} />; // AI가 고른 질문(과 고르는 중)엔 진행 막대를 빼요

  if (kind === "flex" && !q) {
    return (
      <div className="content" role="status" aria-busy="true">
        {progress}
        <Sheet y={852} />
        <div style={{ opacity: s.qNotice ? 1 : 0, transition: "opacity .6s" }}>
          <h1 className="abs center-x t-title pre" style={{ top: 572 }} tabIndex={-1}>
            {"다음 질문을\n고르고 있어요"}
          </h1>
          <Sub y={664} align="center">{"담고(AI)가 오늘 갈 수 있는 곳을 살펴보고\n다음 질문을 골라요"}</Sub>
          <Dots y={728} />
        </div>
      </div>
    );
  }

  const question = kind === "body" ? BODY.question : kind === "time" ? TIME.question : q!.question;
  const choices = kind === "body" ? BODY.choices : kind === "time" ? TIME.choices : q!.choices;
  const dk = kind === "flex" ? q!.dk : true;
  const cur = kind === "body" ? s.body : kind === "time" ? s.time : q!.answered ? q!.a : undefined;
  const pick = (v: string | null) => (kind === "body" ? f.answerBody(v) : kind === "time" ? f.answerTime(v) : f.answerFlex(i, v));

  const lines = twoLines(question).split("\n");
  const size = titleSize(question);
  const tiles = choices.slice(0, 4);
  const dkTile = dk && tiles.length <= 3;
  const dkButton = dk && tiles.length === 4;
  const heard = s.heard.length > 0;
  const ai = kind === "flex" && q!.src === "ai";

  // 제목이 길어 줄이 늘면(글씨 크기 · 화면 폭에 따라) 그만큼 아래 안내 · 칩 · 선택지를 내려요 — 실제 높이를 재요
  const estTitle = lines.length * size * 1.22;
  const titleH = Math.max(estTitle, measured.title);
  const subTop = 140 + titleH + 10;
  const subBottom = subTop + (measured.sub || 46);
  const chipTop = Math.max(296, subBottom + 10);
  const stackTop = Math.max(heard ? 404 : 424, (ai ? chipTop + (measured.chip || 32) : subBottom) + 16);

  return (
    <div className="content">
      {progress}
      <h1
        ref={h1}
        className="abs t-title pre"
        style={{
          top: 140,
          right: 24,
          maxWidth: 219,
          textAlign: "right",
          // 낱말 가운데서 줄을 바꾸지 않아요 (띄어쓰기에서만) — 줄이 늘면 아래 것들이 그만큼 내려가요
          wordBreak: "keep-all",
          fontSize: size,
          transformOrigin: "100% 0",
          transform: phase === "in" ? fx : "none",
          transition: phase === "top" ? "transform .6s cubic-bezier(.45,0,.2,1)" : "none",
          zIndex: 2,
        }}
        tabIndex={-1}
      >
        {lines.join("\n")}
      </h1>
      <p ref={subRef} className="abs pre t-sub c-sub" style={{ top: subTop, right: 24, left: 170, textAlign: "right", opacity: phase === "in" ? 0 : 1, transition: "opacity .4s" }}>
        {"하나를\n눌러 주세요"}
      </p>
      {ai && (
        <span ref={chipRef} className="abs chip" style={{ right: 24, top: chipTop, opacity: phase === "base" ? 1 : 0, transition: "opacity .4s" }}>
          AI가 고른 질문
        </span>
      )}
      {/* 담고 머리 · 앞발 아래로 한 줄로 쌓아요: (들은 말 상자) → 선택지 → 잘 모르겠어요 → 안내.
          들은 말이 있으면 그만큼 선택지가 자연스럽게 아래로 내려가요 */}
      <div className={`qStack${heard && dkButton ? " tight" : ""}`} style={{ top: stackTop }}>
        {heard && (
          <section className="heardBox" aria-label="이렇게 들었어요" style={{ opacity: phase === "base" ? 1 : 0, transition: "opacity .4s" }}>
            <p className="heardLabel">이렇게 들었어요 · 틀리면 눌러서 지워요</p>
            <div className="heardChips">
              {s.heard.map((h) => (
                <button key={h.key + h.value} className="chip heardChip" onClick={() => f.forget(h)} aria-label={`${h.label} 지우기`}>
                  {h.label}
                  <span aria-hidden="true">✕</span>
                </button>
              ))}
            </div>
          </section>
        )}
        <div
          className="tiles"
          style={{
            opacity: phase === "base" ? 1 : 0,
            transform: phase === "base" ? "none" : "translateY(60px)",
            transition: "opacity .45s ease, transform .55s cubic-bezier(.22,1,.36,1)",
          }}
        >
          {tiles.map((c, n) => {
            const hint = kind === "time" ? TIME.hints[c] : undefined;
            const on = cur === c;
            return (
              <button key={c} className={`tile${on ? " on" : ""}`} onClick={() => pick(c)} aria-pressed={on}>
                <span className="num">{n + 1}</span>
                <span className="tarrow">
                  <TileArrow color={on ? "#FFFFFF" : "#111111"} />
                </span>
                <span className="ans" style={{ fontSize: tileSize(c) }}>
                  {c}
                  {hint && <span className="hint">{hint}</span>}
                </span>
              </button>
            );
          })}
          {dkTile && (
            // "잘 모르겠어요"도 다른 선택지와 같은 모양 · 색이에요 (고르면 똑같이 검정으로)
            <button className={`tile${cur === null ? " on" : ""}`} onClick={() => pick(null)} aria-pressed={cur === null}>
              <span className="num">{tiles.length + 1}</span>
              <span className="tarrow">
                <TileArrow color={cur === null ? "#FFFFFF" : "#111111"} />
              </span>
              <span className="ans" style={{ fontSize: tileSize(DONT_KNOW) }}>
                {DONT_KNOW}
              </span>
            </button>
          )}
        </div>
        <div style={{ opacity: phase === "base" ? 1 : 0, transition: "opacity .4s" }}>
          {dkButton && (
            <button className="btn btn-primary qDk" onClick={() => pick(null)}>
              <span>{DONT_KNOW}</span>
              <span className="arrow" aria-hidden="true">
                →
              </span>
            </button>
          )}
          <p className={`t-caption pre c-sub qCaption${dkButton ? " withDk" : ""}`}>{edit ? "하나를 누르면 확인으로 돌아가요" : "하나를 누르면 다음으로 넘어가요"}</p>
        </div>
      </div>
    </div>
  );
}
