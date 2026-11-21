"use client";

import { useEffect, useState } from "react";
import type { FlowApi } from "../Flow";
import { Primary } from "../ui";
import { rideText, speakTime } from "@/lib/format";
import { photoIll } from "@/lib/illust";
import type { Leg } from "@/lib/types";
import { load, save } from "@/lib/device";
import { later } from "@/lib/pause";

type Card = { tag: string; name: string; desc: string; car?: string; end?: boolean };

function cards(legs: Leg[]): Card[] {
  return legs.map((l, i) => {
    let tag: string;
    let name = l.station ?? "";
    let desc: string;
    if (l.kind === "하차") {
      tag = legs.length === 1 ? "여기로 걸어가요" : "여기서 내려요";
      if (l.exit) name = `${name} ${l.exit} 출구`;
      desc = l.exit ? `출구로 나와 ${l.walkMin ?? 0}분 걸어요` : `내려서 ${l.walkMin ?? 0}분 걸어요`;
    } else {
      tag = `${l.kind === "환승" ? "여기서 갈아타요" : "여기서 타요"}${l.line ? ` · ${l.line}` : ""}`;
      desc = rideText(l);
    }
    if (l.tip) desc = i === 0 ? `${l.tip} · ${desc}` : `${desc} · ${l.tip}`;
    return { tag, name, desc, car: l.fastCar ? `${l.fastCar}번 칸` : undefined };
  });
}

/** 가는 길 (4.4 route, 8.4) */
/** 제목 글자 크기: 장소 이름이 길수록 작게(두 줄 안에 들어오게) */
function titleSize(name: string) {
  const n = name.length;
  return n <= 9 ? 29 : n <= 16 ? 25 : 22;
}

export default function Route({ f }: { f: FlowApi }) {
  const { s } = f;
  const c = s.cands[s.idx];
  const [nudge, setNudge] = useState(false);
  useEffect(() => {
    if (!c) return;
    f.loadSocial(c.place.id);
    if (s.user || load<string | null>("aigo.nudged", null) === "1") return;
    const cancel = later(1400, () => {
      setNudge(true);
      save("aigo.nudged", "1");
    });
    return cancel;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [c?.place.id]);
  if (!c) return null;
  const r = c.route;
  const list = cards(r?.legs ?? []);
  const arrive = speakTime(r?.arriveAt ?? "");
  list.push({ tag: `도착 · ${arrive}쯤`, name: c.place.name, desc: c.place.kind, end: true });
  const o = s.origin;
  const enc = encodeURIComponent;
  const kakao =
    o && o.lat != null && o.lng != null
      ? `https://map.kakao.com/link/by/traffic/${enc(o.name)},${o.lat},${o.lng}/${enc(c.place.name)},${c.place.lat},${c.place.lng}`
      : `https://map.kakao.com/link/to/${enc(c.place.name)},${c.place.lat},${c.place.lng}`;
  const soc = s.social[c.place.id];

  return (
    <div className="content">
      {/* 제목 · 이동 시간 · 경로 카드를 위에서부터 차례로 쌓아요. 장소 이름이 길어 제목이 두 줄이 되면 카드가 그만큼 내려가고 짧아져요(겹치지 않게) */}
      <div className="abs" style={{ left: 24, right: 24, top: 100, bottom: 206, display: "flex", flexDirection: "column" }}>
        <h1
          className="t-title-s"
          tabIndex={-1}
          title={c.place.name}
          style={{
            flex: "none",
            fontSize: `calc(${titleSize(c.place.name)}px * var(--fs-t))`,
            wordBreak: "keep-all",
            overflowWrap: "anywhere",
            display: "-webkit-box",
            WebkitLineClamp: 2,
            WebkitBoxOrient: "vertical",
            overflow: "hidden",
          }}
        >
          {`${c.place.name} 가는 길`}
        </h1>
        <p className="t-sub" style={{ flex: "none", marginTop: 6, marginBottom: 12, color: "var(--ink)", wordBreak: "keep-all" }}>
          {`이동 시간 약 ${r?.totalMin ?? 0}분 · ${arrive}쯤 도착해요${r?.estimated ? " (어림)" : ""}`}
        </p>
      <div className="scroll rise-in" style={{ flex: 1, minHeight: 0, background: "var(--white)", borderRadius: 24, boxShadow: "var(--sh-row)" }}>
        {list.map((k, i) => (
          <div key={i} style={{ position: "relative", minHeight: 118, padding: "12px 16px 14px 80px" }}>
            {i < list.length - 1 && <div style={{ position: "absolute", left: 38.5, top: 68, bottom: -6, borderLeft: "3px dotted var(--mute)" }} />}
            <div
              style={{
                position: "absolute",
                left: 16,
                top: 12,
                width: 48,
                height: 48,
                borderRadius: 16,
                background: k.end ? "var(--coral)" : "var(--soft)",
                color: k.end ? "var(--white)" : "var(--ink)",
                textAlign: "center",
                lineHeight: "48px",
              }}
              className="t-tile"
            >
              {i + 1}
            </div>
            {k.car && (
              <span className="chip" style={{ position: "absolute", right: 16, top: 10, height: 32, lineHeight: "32px", fontSize: "calc(16px * var(--fs))", borderRadius: 16 }}>
                {k.car}
              </span>
            )}
            {k.end && (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={photoIll(c.place.kind, c.place.name)} alt="" width={72} height={72} style={{ position: "absolute", right: 16, top: 12, borderRadius: 16, objectFit: "cover" }} />
            )}
            <p className="t-sub c-deep" style={{ paddingRight: k.end ? 80 : 0 }}>
              {k.tag}
            </p>
            <p className="t-tile" style={{ marginTop: 6, wordBreak: "keep-all", overflowWrap: "anywhere", paddingRight: k.end ? 80 : 0 }}>
              {k.name}
            </p>
            <p className="t-answer c-sub" style={{ marginTop: 8, lineHeight: 1.35, wordBreak: "keep-all" }}>
              {k.desc}
            </p>
          </div>
        ))}
      </div>
      </div>
      <a className="btn btn-white" style={{ left: 24, top: 660, width: 166, justifyContent: "center" }} href={kakao} target="_blank" rel="noopener noreferrer">
        카카오맵 보기
      </a>
      <button className="btn btn-primary" style={{ left: 203, top: 660, width: 166, justifyContent: "center" }} onClick={f.arrive}>
        도착했어요
      </button>
      <p className="abs center-x t-caption c-sub pre" style={{ top: 736, left: 24, right: 24 }}>
        {`${soc && soc.expectedToday > 0 ? `오늘 ${soc.expectedToday}명이 여기 올 예정이에요. ` : ""}도착하면 여기 온 분들과 이야기할 수 있어요`}
      </p>
      {nudge && (
        <div className="modal-bg" onClick={() => setNudge(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
            <h2 className="t-title pre">{"같이 갈 분을\n찾아 보세요"}</h2>
            <p className="t-sub c-mute pre" style={{ marginTop: 10 }}>
              {"로그인하면 오늘 같은 곳에 가는 분과\n동행할 수 있어요"}
            </p>
            <p className="t-caption c-mute" style={{ marginTop: 8 }}>
              로그인하지 않아도 그대로 쓸 수 있어요
            </p>
            <button
              className="btn btn-kakao"
              style={{ marginTop: 18 }}
              onClick={() => {
                setNudge(false);
                f.backTo.current = [...f.s.stack]; // 로그인 · 가입이 끝나면 이 길 안내로 돌아와요
                f.go({ k: "login" });
              }}
            >
              <span>카카오로 시작하기</span>
              <span aria-hidden="true">→</span>
            </button>
            <button className="btn btn-secondary" onClick={() => setNudge(false)}>
              다음에 할게요
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export { Primary };
