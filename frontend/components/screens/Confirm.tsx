"use client";

import type { FlowApi } from "../Flow";
import { Caption, Primary, Progress, Title } from "../ui";
import { buildConditions, type Step } from "@/lib/flow";
import { rangeSentence } from "@/lib/range";
import { SLOT_NAME } from "@/lib/questions";
import { useState } from "react";
import Pack from "../Pack";

type Row = { name: string; value: string; fix?: Step };

/** 확인 (4.3 confirm) */
export default function Confirm({ f }: { f: FlowApi }) {
  const { s } = f;
  const rows: Row[] = [{ name: "출발", value: s.origin?.name ?? "" }];
  if (s.place) rows.push({ name: "가고 싶은 곳", value: s.place });
  if (s.who) rows.push({ name: "같이 가는 분", value: s.who });
  if (s.wish.length) rows.push({ name: "하고 싶은 일", value: s.wish.join(" · ") });
  rows.push({ name: "오늘 컨디션", value: s.body ?? "상관없어요", fix: { k: "body", edit: true } });
  rows.push({ name: "다녀올 시간", value: s.time ?? "상관없어요", fix: { k: "time", edit: true } });
  s.qs.forEach((q, i) => {
    if (!q.answered) return;
    rows.push({ name: q.slot ? SLOT_NAME[q.slot] : q.question, value: q.a ?? "상관없어요", fix: { k: "flex", i, edit: true } });
  });
  const cond = buildConditions(s);
  const [packing, setPacking] = useState(false);
  const go = () => {
    if (packing) return;
    if (f.still) return f.search("push");
    setPacking(true);
  };

  return (
    <div className="content">
      <div style={{ opacity: packing ? 0.15 : 1, transition: "opacity .4s" }}>
      <Progress on={4} text="확인" />
      <Title y={112}>{"이대로\n찾아볼까요?"}</Title>
      <div className="list scroll" style={{ top: 262, height: 382, gap: 6, padding: "4px 0 12px" }}>
        {rows.map((r, n) => (
          <div key={n} className="row" style={{ minHeight: 48, padding: "6px 10px 6px 16px" }}>
            <span style={{ width: 104, flex: "none" }}>
              <span className="t-label c-deep" style={{ display: "block" }}>
                {String(n + 1).padStart(2, "0")}
              </span>
              <span className="t-item c-mute" style={{ display: "block", marginTop: 4, lineHeight: 1.25, wordBreak: "keep-all" }}>
                {r.name}
              </span>
            </span>
            <span className="main t-answer" style={{ wordBreak: "keep-all" }}>
              {r.value}
            </span>
            {r.fix && (
              <button className="chip chip-soft" onClick={() => f.go(r.fix!)} aria-label={`${r.name} 고치기`}>
                고치기
              </button>
            )}
          </div>
        ))}
        <p className="t-sub c-sub" style={{ marginTop: 8, wordBreak: "keep-all" }}>
          {rangeSentence(s.origin?.name ?? "", cond.range)}
        </p>
      </div>
      </div>
      {!packing && (
        <>
          <Primary y={662} onClick={go}>
            이대로 찾기
          </Primary>
          <Caption y={746} onClick={f.home}>
            처음부터 다시
          </Caption>
        </>
      )}
      {packing && (
        <Pack
          rows={rows}
          onPose={f.setPoseOv}
          onDone={() => {
            f.setPoseOv(null);
            setPacking(false);
            f.search("push");
          }}
        />
      )}
    </div>
  );
}
