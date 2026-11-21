"use client";

import { useEffect, useRef, useState } from "react";
import { BADGES, TIERS, record, type BadgeDef, type BadgeEvent } from "@/lib/badges";
import type { FlowState, User } from "@/lib/flow";

/** 배지 기록 + 축하 줄 (11.1 · 11.3) */
export function useBadges(user: User | null) {
  const [queue, setQueue] = useState<BadgeDef[]>([]);
  const userRef = useRef(user);
  const lastUid = useRef<string | null | undefined>(undefined);

  useEffect(() => {
    userRef.current = user;
    const uid = user?.id ?? null;
    if (lastUid.current === undefined) {
      lastUid.current = uid;
      if (uid) {
        const fresh = record(uid, { ev: "check" }, !!user?.homeDong1);
        if (fresh.length) setQueue((q) => [...q, ...fresh]);
      }
      return;
    }
    if (uid && uid !== lastUid.current) {
      const fresh = record(uid, { ev: "login" }, !!user?.homeDong1);
      if (fresh.length) setQueue((q) => [...q, ...fresh]);
    } else if (uid) {
      const fresh = record(uid, { ev: "check" }, !!user?.homeDong1);
      if (fresh.length) setQueue((q) => [...q, ...fresh]);
    }
    lastUid.current = uid;
  }, [user]);

  useEffect(() => {
    function on(e: Event) {
      const u = userRef.current;
      if (!u) return;
      const fresh = record(u.id, (e as CustomEvent<BadgeEvent>).detail, !!u.homeDong1);
      if (fresh.length) setQueue((q) => [...q, ...fresh]);
    }
    window.addEventListener("aigo:badge", on);
    return () => window.removeEventListener("aigo:badge", on);
  }, []);

  return { queue, next: () => setQueue((q) => q.slice(1)), clear: () => setQueue([]) };
}

export function canCelebrate(s: FlowState) {
  const k = s.stack[s.stack.length - 1]?.k;
  return !!s.user && !s.tearing && !s.busy && !["cut", "stamped", "kwait", "welcome"].includes(k);
}

export default function Celebrate({ b, more, onNext, onAll }: { b: BadgeDef; more: boolean; onNext: () => void; onAll: () => void }) {
  const tier = TIERS.find((t) => t.tier === b.tier);
  return (
    <div className="modal-bg" style={{ zIndex: 95 }} onClick={onNext}>
      <div
        className="card"
        role="dialog"
        aria-modal="true"
        aria-label="새 배지를 얻었어요"
        onClick={(e) => e.stopPropagation()}
        style={{ top: 150, textAlign: "center", padding: "28px 22px 22px", animation: "fadeIn .35s ease both" }}
      >
        <p className="t-label c-deep">
          {b.hidden ? "숨은 업적 · " : ""}
          {tier?.name} · {tier?.level}
        </p>
        <p className="t-sub" style={{ marginTop: 8 }}>
          새 배지를 얻었어요!
        </p>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={`/aigo/badges/${b.id}.svg`} alt="" width={160} height={160} style={{ margin: "14px auto 6px", display: "block" }} />
        <p className="t-title">{b.name}</p>
        <p className="t-sub c-mute" style={{ marginTop: 6 }}>
          {b.cheer}
        </p>
        <button className="btn btn-primary" style={{ position: "relative", width: "100%", marginTop: 18, justifyContent: "center" }} onClick={onNext}>
          {more ? "좋아요 · 하나 더 있어요" : "좋아요"}
        </button>
        <button className="btn btn-secondary" style={{ position: "relative", width: "100%", marginTop: 10 }} onClick={onAll}>
          내 업적 모두 보기
        </button>
      </div>
    </div>
  );
}

export { BADGES };
