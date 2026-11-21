"use client";

import { useEffect } from "react";
import type { FlowApi } from "../Flow";
import { TileArrow } from "../Icons";
import { Caption, Dots, Primary, Progress, Sheet, Sub } from "../ui";
import { BODY, DONT_KNOW, TIME, tileSize, titleSize, twoLines } from "@/lib/questions";

type Props = { f: FlowApi; kind: "body" | "time" | "flex"; i?: number; edit?: boolean };

/** 몸 · 시간 · 질문 N (4.3, 5.2) */
export default function Question({ f, kind, i = 0, edit }: Props) {
  const { s } = f;
  const q = kind === "flex" ? s.qs[i] : null;

  useEffect(() => {
    if (kind === "flex" && !q) f.prepare(i);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kind, i, !!q]);

  const progress =
    kind === "body" ? <Progress on={2} text="2 / 4" right /> : kind === "time" ? <Progress on={3} text="3 / 4" right /> : <Progress on={4} text={`질문 ${i + 1}`} right />;

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

  return (
    <div className="content">
      {progress}
      <h1 className="abs t-title pre" style={{ top: 140, right: 24, left: 150, textAlign: "right", fontSize: size }} tabIndex={-1}>
        {lines.join("\n")}
      </h1>
      <Sub y={140 + lines.length * size * 1.22 + 10} align="right" style={{ left: 170 }}>
        {"하나를\n눌러 주세요"}
      </Sub>
      <div className="abs" style={{ right: 24, top: 296, left: 150, display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 6 }}>
        {kind === "flex" && q!.src === "ai" && <span className="chip">AI가 고른 질문</span>}
        {s.heard.length > 0 && (
          <>
            <span className="t-item" style={{ textAlign: "right", lineHeight: 1.3, background: "var(--white)", borderRadius: 10, padding: "5px 8px" }}>
              이렇게 들었어요 · 틀리면 눌러서 지워요
            </span>
            <span style={{ display: "flex", flexWrap: "wrap", justifyContent: "flex-end", gap: 6 }}>
              {s.heard.map((h) => (
                <button key={h.key + h.value} className="chip" style={{ background: "var(--white)", color: "var(--ink)" }} onClick={() => f.forget(h)} aria-label={`${h.label} 지우기`}>
                  {h.label} ✕
                </button>
              ))}
            </span>
          </>
        )}
      </div>
      <div className="tiles" style={{ top: 404 }}>
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
          <button className={`tile dontknow${cur === null ? " on" : ""}`} onClick={() => pick(null)} aria-pressed={cur === null}>
            <span className="num">{tiles.length + 1}</span>
            <span className="ans" style={{ fontSize: 20 }}>
              {DONT_KNOW}
            </span>
          </button>
        )}
      </div>
      {dkButton && (
        <Primary y={650} onClick={() => pick(null)}>
          {DONT_KNOW}
        </Primary>
      )}
      <Caption y={dkButton ? 732 : 664}>{edit ? "하나를 누르면 확인으로 돌아가요" : "하나를 누르면 다음으로 넘어가요"}</Caption>
    </div>
  );
}
