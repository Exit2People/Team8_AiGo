"use client";

import { useEffect, useRef, useState } from "react";
import type { FlowApi } from "../Flow";
import { CheckIcon } from "../Icons";
import { Caption, Primary, Secondary, Sheet, Sub, Title } from "../ui";
import * as api from "@/lib/api";
import { photoIll } from "@/lib/illust";
import type { ReviewsResp } from "@/lib/types";


/** 방명록 노트 (9.2) */
/* ---- 방명록 노트 (figma-plugin notebook · gbEntry · 17-0 방명록) ----
 * 가죽 표지(프린터 가죽 · 바느질) 위에 종이가 여러 장 겹쳐 있고(아래로 두께가 비쳐요), 위에는 금속 스프링이 종이 구멍을 꿰어요.
 * 종이: 28px 간격 줄 · 코랄 여백선. 한 쪽에 4명, 한 사람 칸(112): 한 줄 2줄 → #고른 것 · — 닉네임 · 날짜 → 신고, 오른쪽에 사진 우표를 테이프로.
 * 쪽 넘기기: 위 장이 스프링 쪽으로 접혀 올라가며(높이가 줄고 뒷면 그늘이 짙어져요) 아래 장이 드러나요. 이전 쪽은 거꾸로. */
const NB = { x: 26, y: 120, w: 341, h: 612 };
const NB_TOP = 56; // 첫 줄
const NB_ENTRY = 112; // 한 사람 칸 (줄 4개)
const STAMP_ROT = [-6, 5, -3, 7];
const STAMP_DY = [-2, 4, 0, 2];

type GbPage = { items: ReviewsResp["items"] | null; err: boolean; page: number; total: number };

function NotePage({ f, c, pg, onTurn, h, cls }: { f: FlowApi; c: NonNullable<FlowApi["s"]["cands"][number]>; pg: GbPage; onTurn: (d: number) => void; h?: number; cls?: string }) {
  const msg = pg.err ? "방명록을 받지 못했어요\n인터넷 연결을 확인해 주세요" : !pg.items ? "방명록을 펼치고 있어요…" : pg.items.length === 0 ? "아직 빈 방명록이에요\n다녀와서 첫 줄을 남겨 주세요" : "";
  return (
    <div className={`nb-page${cls ? ` ${cls}` : ""}`} style={h != null ? { height: h } : undefined}>
      <div className="nb-page-in">
        <div className="nb-rules" />
        <div className="nb-margin" />
        {Array.from({ length: 11 }, (_, i) => (
          <i key={i} className="nb-hole" style={{ left: 16 + i * 30 }} />
        ))}
        {msg ? (
          <div className="nb-entry" style={{ top: NB_TOP - 24 }}>
            <p className="nb-text pre c-mute">{msg}</p>
            {pg.items && pg.items.length === 0 && <span className="nb-stamp-slot" />}
          </div>
        ) : (
          pg.items!.map((r, k) => (
            <div key={r.id} className="nb-entry" style={{ top: NB_TOP - 24 + k * NB_ENTRY }}>
              <p className="nb-text">{r.text}</p>
              {r.tag && <span className="nb-tag">#{r.tag}</span>}
              <span className="nb-by">
                — {r.nick} · {r.date}
              </span>
              <span className="nb-stamp" style={{ top: 6 + STAMP_DY[k % 4], transform: `rotate(${STAMP_ROT[k % 4]}deg)` }}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={k % 2 === 1 ? photoIll(c.place.kind, c.place.name) : "/aigo/ill/photo_forest.svg"}
                  alt=""
                  onError={(e) => (e.currentTarget.src = "/aigo/ill/photo_forest.svg")}
                />
              </span>
              <i className="nb-tape" style={{ top: 4 + STAMP_DY[k % 4], transform: `rotate(${STAMP_ROT[k % 4] - 8}deg)` }} />
              <button
                className="nb-report"
                aria-label={`${r.nick} 님의 한 줄 신고`}
                onClick={() => f.note(`${r.nick} 님의 한 줄을 신고했어요. 운영자가 살펴볼게요.`)}
              >
                신고
              </button>
            </div>
          ))
        )}
        <div className="nb-foot">
          <button className="nb-pill" disabled={pg.page <= 1} onClick={() => onTurn(-1)}>
            ‹ 이전 쪽
          </button>
          <span className="t-count c-mute">
            {pg.page} / {pg.total}쪽
          </span>
          <button className="nb-pill" disabled={pg.page >= pg.total} onClick={() => onTurn(1)}>
            다음 쪽 ›
          </button>
        </div>
      </div>
      <div className="nb-shade" />
    </div>
  );
}

export function Guestbook({ f }: { f: FlowApi }) {
  const c = f.s.cands[f.s.idx];
  const pid = c?.place.id ?? "";
  const [pages, setPages] = useState<Record<number, ReviewsResp>>({});
  const [page, setPage] = useState(1);
  const [err, setErr] = useState(false);
  // 넘기는 중: dir 1 = 다음 쪽(위 장이 접혀 올라가요), -1 = 이전 쪽(접혀 있던 장이 내려와요). from = 넘기기 전 쪽
  const [flip, setFlip] = useState<{ dir: 1 | -1; from: number } | null>(null);
  const loading = useRef(new Set<number>());
  const drag = useRef<{ x: number; y: number } | null>(null);

  async function get(p: number) {
    if (pages[p] || loading.current.has(p)) return;
    loading.current.add(p);
    try {
      const r = await api.reviews(pid, p);
      setPages((o) => ({ ...o, [p]: r }));
      setErr(false);
    } catch {
      setErr(true);
    } finally {
      loading.current.delete(p);
    }
  }
  useEffect(() => {
    if (!pid) return;
    get(page);
    const cur = pages[page];
    if (cur && page < cur.pages) get(page + 1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pid, page, pages[page]?.pages]);

  if (!c) return null;
  const total = pages[page]?.pages ?? pages[1]?.pages ?? 1;
  const pg = (n: number): GbPage => ({ items: pages[n]?.items ?? null, err: err && !pages[n], page: n, total });
  const turn = (d: number) => {
    if (flip) return;
    const n = page + d;
    if (n < 1 || n > total) return;
    setFlip({ dir: d > 0 ? 1 : -1, from: page });
    setPage(n);
    f.later(f.still ? 0 : 340, () => setFlip(null));
  };

  // 넘기는 동안: 아래 장 = 다음 쪽이면 새 쪽, 이전 쪽이면 지금 쪽 / 위 장 = 다음 쪽이면 지금 쪽(접혀 올라감), 이전 쪽이면 새 쪽(내려옴)
  const under = flip ? (flip.dir > 0 ? page : flip.from) : page;
  const over = flip ? (flip.dir > 0 ? flip.from : page) : null;

  return (
    <div className="content">
      <h1 className="sr-only" tabIndex={-1}>
        {c.place.name} 방명록
      </h1>
      <div
        className="nb"
        style={{ touchAction: "pan-x pan-y" }}
        onPointerDown={(e) => (drag.current = { x: e.clientX, y: e.clientY })}
        onPointerUp={(e) => {
          const d = drag.current;
          drag.current = null;
          if (!d) return;
          const dx = e.clientX - d.x;
          const dy = e.clientY - d.y;
          if (Math.max(Math.abs(dx), Math.abs(dy)) < 40) return;
          if (dx < -40 || dy < -40) turn(1);
          else turn(-1);
        }}
      >
        {/* 가죽 표지: 티켓(화면 y 100 ~ 684)을 완전히 덮어요 */}
        <div className="nb-cover">
          <div className="nb-stitch" />
        </div>
        {/* 종이 두께: 아래 장들이 비쳐 보여요 */}
        <div className="nb-thick nb-thick-2" />
        <div className="nb-thick nb-thick-1" />
        <NotePage f={f} c={c} pg={pg(under)} onTurn={turn} />
        {over != null && <NotePage f={f} c={c} pg={pg(over)} onTurn={turn} cls={flip!.dir > 0 ? "nb-turn-up" : "nb-turn-down"} />}
        {/* 금속 스프링: 검정 고리에 흰 빛 한 줄 (종이 위로 걸쳐요) */}
        {Array.from({ length: 11 }, (_, i) => (
          <i key={i} className="nb-ring" style={{ left: NB.x + 18 + i * 30 }} />
        ))}
      </div>
      <Secondary y={756} w={166} white onClick={f.back}>
        티켓 다시 보기
      </Secondary>
      <button className="btn btn-primary" style={{ left: 203, top: 756, width: 166, justifyContent: "center" }} onClick={() => f.choose(true)}>
        여기로 갈게요
      </button>
    </div>
  );
}

function Faces({ names }: { names: string[] }) {
  return (
    <div style={{ display: "flex" }}>
      {names.slice(0, 4).map((n, i) => (
        <span
          key={n + i}
          style={{
            width: 44,
            height: 44,
            borderRadius: 22,
            background: i % 2 ? "var(--ink)" : "var(--white)",
            color: i % 2 ? "var(--white)" : "var(--ink)",
            border: "3px solid var(--coral)",
            marginLeft: i ? -10 : 0,
            textAlign: "center",
            lineHeight: "38px",
            fontWeight: 800,
            fontSize: "calc(17px * var(--fs))",
          }}
        >
          {n.slice(0, 1)}
        </span>
      ))}
    </div>
  );
}

/** 도착 (4.4 arrive) */
export function Arrive({ f }: { f: FlowApi }) {
  const { s, chat } = f;
  const c = s.cands[s.idx];
  if (!c) return null;
  const others = chat.members;
  return (
    <div className="content">
      <span className="abs chip" style={{ left: 24, top: 104 }}>
        {s.arrivedAt} · 도착
      </span>
      <Title y={148} size="m">{`${c.place.name}에\n도착했어요`}</Title>
      <Sheet y={520} />
      <div className="abs" style={{ left: 24, top: 548, display: "flex", gap: 14, alignItems: "center", right: 24 }}>
        {others.length > 0 && <Faces names={others} />}
        <p className="t-answer pre" style={{ lineHeight: 1.35 }}>
          {chat.count > 0 ? `지금 여기 온 ${chat.count}명이\n이야기하고 있어요` : "아직 아무도 없어요.\n먼저 인사해 보세요"}
        </p>
      </div>
      {s.user ? (
        chat.joined ? (
          <Primary y={636} onClick={() => f.replaceTop({ k: "chat" })}>
            톡방으로 돌아가기
          </Primary>
        ) : (
          <Primary y={636} onClick={() => f.go({ k: "chatjoin" })}>
            같이 이야기하기
          </Primary>
        )
      ) : (
        <Primary
          y={636}
          onClick={() => {
            f.backTo.current = [...s.stack.slice(0, -1), { k: "arrive" }];
            f.go({ k: "login" });
          }}
        >
          로그인하고 이야기하기
        </Primary>
      )}
      <Secondary y={708} onClick={f.home}>
        혼자 둘러볼게요
      </Secondary>
      <Caption y={792} dark>
        {s.user ? "내 위치는 보이지 않아요 · 톡방은 오늘 밤 12시에 사라져요" : "톡방은 로그인한 분만 들어갈 수 있어요"}
      </Caption>
    </div>
  );
}

/** 톡방 들어가기 전 약속 (4.4 chatjoin) */
export function ChatJoin({ f }: { f: FlowApi }) {
  const [busy, setBusy] = useState(false);
  return (
    <div className="content">
      <Title y={112} size="m">{"들어가기 전에\n세 가지만 약속해요"}</Title>
      <Sheet y={400} />
      {["전화번호 · 주소는 묻지 않아요", "돈 이야기는 하지 않아요", "불편하면 바로 나가고 신고해요"].map((t, i) => (
        <div
          key={t}
          className="abs"
          style={{ left: 24, top: 428 + i * 52, width: 345, height: 52, display: "flex", alignItems: "center", gap: 16, borderBottom: "1.5px solid var(--soft)" }}
        >
          <CheckIcon />
          <span className="t-body">{t}</span>
        </div>
      ))}
      <p className="abs t-sub c-mute" style={{ left: 24, top: 596 }}>
        ‘{f.chat.myNick}’ 이름으로 들어가요
      </p>
      <Primary
        y={636}
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          await f.chat.join();
          setBusy(false);
        }}
      >
        약속하고 들어가기
      </Primary>
      <Secondary y={708} onClick={f.back}>
        그만둘래요
      </Secondary>
      <Caption y={792} dark>
        사진 · 위치는 보낼 수 없어요
      </Caption>
    </div>
  );
}
