"use client";

import { useEffect, useRef, useState } from "react";
import type { FlowApi } from "../Flow";
import { CheckIcon } from "../Icons";
import { Caption, Primary, Secondary, Sheet, Sub, Title } from "../ui";
import * as api from "@/lib/api";
import { photoIll } from "@/lib/illust";
import type { ReviewsResp } from "@/lib/types";

const TILT = [-6, 5, -4, 6];

/** 방명록 노트 (9.2) */
export function Guestbook({ f }: { f: FlowApi }) {
  const c = f.s.cands[f.s.idx];
  const pid = c?.place.id ?? "";
  const [pages, setPages] = useState<Record<number, ReviewsResp>>({});
  const [page, setPage] = useState(1);
  const [err, setErr] = useState(false);
  const [flip, setFlip] = useState(false);
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
  const cur = pages[page];
  const total = cur?.pages ?? 1;
  const turn = (d: number) => {
    if (flip) return;
    const n = page + d;
    if (n < 1 || n > total) return;
    setFlip(true);
    setPage(n);
    f.later(520, () => setFlip(false));
  };

  return (
    <div className="content">
      <h1 className="sr-only" tabIndex={-1}>
        {c.place.name} 방명록
      </h1>
      <div
        className="abs"
        style={{
          left: 24,
          top: 104,
          width: 345,
          height: 548,
          background: "var(--g-paper)",
          borderRadius: 24,
          boxShadow: "var(--sh-ticket)",
          padding: "20px 20px 16px",
          backgroundImage: "repeating-linear-gradient(to bottom, transparent 0 39px, rgba(201,195,186,.5) 39px 40px)",
          backgroundColor: "#FFFEFB",
          transition: "transform .52s ease",
          transform: flip ? "rotateX(6deg)" : "none",
          touchAction: "pan-x pan-y",
        }}
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
        <p className="t-mono c-tgray">AI GO · GUEST BOOK</p>
        <p className="t-tile" style={{ marginTop: 8 }}>
          다녀온 사람들의 방명록
        </p>
        {err ? (
          <p className="t-sub c-sub" style={{ marginTop: 24 }}>
            방명록을 받지 못했어요. 인터넷 연결을 확인해 주세요.
          </p>
        ) : !cur ? (
          <p className="t-sub c-mute" style={{ marginTop: 24 }}>
            불러오고 있어요…
          </p>
        ) : cur.items.length === 0 ? (
          <p className="t-sub c-mute" style={{ marginTop: 24 }}>
            아직 남긴 글이 없어요
          </p>
        ) : (
          <div style={{ marginTop: 14, display: "flex", flexDirection: "column", gap: 12 }}>
            {cur.items.map((r, i) => (
              <div key={r.id} style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={i % 2 === 1 ? photoIll(c.place.kind, c.place.name) : "/aigo/ill/photo_forest.svg"}
                  alt=""
                  width={52}
                  height={62}
                  onError={(e) => (e.currentTarget.src = "/aigo/ill/photo_forest.svg")}
                  style={{ flex: "none", transform: `rotate(${TILT[i % 4]}deg)`, border: "3px solid #fff", boxShadow: "var(--sh-row)", objectFit: "cover" }}
                />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <p className="t-answer" style={{ lineHeight: 1.3, wordBreak: "keep-all" }}>
                    {r.text}
                  </p>
                  <p className="t-item c-mute" style={{ marginTop: 6, lineHeight: 1.3 }}>
                    {r.tag ? `#${r.tag} ` : ""}— {r.nick} · {r.date}
                  </p>
                </div>
                <button
                  className="t-item c-mute"
                  style={{ flex: "none", padding: "4px 2px", textDecoration: "underline" }}
                  aria-label={`${r.nick} 님의 한 줄 신고`}
                  onClick={() => f.note(`${r.nick} 님의 한 줄을 신고했어요. 운영자가 살펴볼게요.`)}
                >
                  신고
                </button>
              </div>
            ))}
          </div>
        )}
        <div style={{ position: "absolute", left: 16, right: 16, bottom: 14, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <button className="chip chip-soft" disabled={page <= 1} style={{ opacity: page <= 1 ? 0.4 : 1 }} onClick={() => turn(-1)}>
            ‹ 이전 쪽
          </button>
          <span className="t-count">
            {page} / {total}쪽
          </span>
          <button className="chip chip-soft" disabled={page >= total} style={{ opacity: page >= total ? 0.4 : 1 }} onClick={() => turn(1)}>
            다음 쪽 ›
          </button>
        </div>
      </div>
      <Secondary y={672} w={166} white onClick={f.back}>
        티켓 다시 보기
      </Secondary>
      <button className="btn btn-primary" style={{ left: 203, top: 672, width: 166, justifyContent: "center" }} onClick={() => f.choose(true)}>
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
