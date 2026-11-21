"use client";

import type { FlowApi } from "../Flow";
import { Caption, Primary, Progress, Title } from "../ui";
import { buildConditions, type Step } from "@/lib/flow";
import { rangeSentence } from "@/lib/range";
import { SLOT_NAME } from "@/lib/questions";
import { useRef, useState } from "react";
import Pack, { type PackRect } from "../Pack";

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
  const [from, setFrom] = useState<PackRect[]>([]);
  const listRef = useRef<HTMLDivElement>(null);
  const go = () => {
    if (packing) return;
    if (f.still) return f.search("push");
    setFrom(measureRows(listRef.current));
    setPacking(true);
  };

  return (
    <div className="content">
      {/* 가방에 담을 때: 진행 막대 · 제목은 완전히 사라지고, 답 줄은 그 자리에서 가방 카드로 바뀌니 원래 줄은 감춰요 */}
      <div style={{ opacity: packing ? 0 : 1, visibility: packing ? "hidden" : undefined, transition: "opacity .3s, visibility 0s .3s" }}>
        <Progress on={4} text="확인" />
        <Title y={112}>{"이대로\n찾아볼까요?"}</Title>
      </div>
      <div ref={listRef} className="list scroll" style={{ top: 262, height: 382, gap: 6, padding: "4px 0 12px" }}>
        {rows.map((r, n) => (
          // 질문(항목)이 두 줄이어도 겹치지 않게 모든 줄을 60으로 키우고, 목록이 차도 줄이 눌리지 않게(flex: none) 해요. 넘치면 목록이 밀려요
          <div key={n} data-pack-row className="row" style={{ minHeight: 60, flex: "none", padding: "6px 10px 6px 16px", visibility: packing ? "hidden" : undefined }}>
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
        <p className="t-sub c-sub" style={{ marginTop: 8, wordBreak: "keep-all", opacity: packing ? 0 : 1, transition: "opacity .3s" }}>
          {rangeSentence(s.origin?.name ?? "", cond.range)}
        </p>
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
          rows={rows.map((r) => ({ name: r.name, value: r.value, fix: !!r.fix }))}
          from={from}
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

/** 답 줄 자리를 화면(393 × 852) 좌표로 재요. 목록 칸은 (24, 262, 345 × 382)이라 그 크기로 배율을 구해요.
 *  목록이 스크롤돼 안 보이던 줄은 vis: false */
const LIST = { x: 24, y: 262, h: 382 };
function measureRows(list: HTMLDivElement | null): PackRect[] {
  if (!list) return [];
  const lr = list.getBoundingClientRect();
  const k = lr.height / LIST.h || 1; // 화면 배율(zoom)
  return [...list.querySelectorAll<HTMLElement>("[data-pack-row]")].map((el) => {
    const r = el.getBoundingClientRect();
    return {
      x: LIST.x + (r.left - lr.left) / k,
      y: LIST.y + (r.top - lr.top) / k,
      w: r.width / k,
      h: r.height / k,
      vis: r.bottom > lr.top + 4 && r.top < lr.bottom - 4,
    };
  });
}
