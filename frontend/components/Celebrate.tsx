"use client";

import { useEffect, useRef, useState } from "react";
import { BADGES, record, type BadgeDef, type BadgeEvent } from "@/lib/badges";
import { BadgeCelebrate } from "./Badges";
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

/** 얻은 순간 축하 (components/Badges.tsx BadgeCelebrate) */
export default function Celebrate({ b, more, onNext, onAll }: { b: BadgeDef; more: boolean; onNext: () => void; onAll: () => void }) {
  return <BadgeCelebrate badge={b} more={more ? 1 : 0} onNext={onNext} onOpenAll={onAll} />;
}

export { BADGES };
