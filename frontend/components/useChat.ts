"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import * as api from "@/lib/api";
import { ApiError } from "@/lib/errors";
import { readBlocked, saveBlocked } from "@/lib/device";
import type { ChatMessage } from "@/lib/types";
import type { FlowState } from "@/lib/flow";

export type ChatApi = ReturnType<typeof useChat>;

type Deps = {
  s: FlowState;
  client: React.RefObject<string>;
  nick: React.RefObject<string>;
  note: (t: string | null) => void;
  replaceTop: (st: { k: "chat" }) => void;
};

/** 톡방 (11_FRONTEND_SPEC 9.3) */
export function useChat({ s, client, nick, note, replaceTop }: Deps) {
  const step = s.stack[s.stack.length - 1];
  const place = s.cands[s.idx]?.place;
  const pid = place?.id ?? "";
  const [msgs, setMsgs] = useState<ChatMessage[]>([]);
  const [members, setMembers] = useState<string[]>([]);
  const [count, setCount] = useState(0);
  const [joined, setJoined] = useState(false);
  const [lost, setLost] = useState(false);
  const [blocked, setBlocked] = useState<string[]>([]);
  const [myNick, setMyNick] = useState("");
  const last = useRef(0);
  const room = useRef("");

  useEffect(() => setBlocked(readBlocked()), []);

  // 장소가 바뀌면 처음부터
  useEffect(() => {
    if (room.current !== pid) {
      room.current = pid;
      last.current = 0;
      setMsgs([]);
      setMembers([]);
      setCount(0);
      setJoined(false);
    }
  }, [pid]);

  const merge = useCallback((list: ChatMessage[], bump: boolean) => {
    if (!list.length) return;
    setMsgs((old) => {
      const seen = new Set(old.map((m) => m.id));
      const add = list.filter((m) => !seen.has(m.id));
      return add.length ? [...old, ...add].sort((a, b) => a.id - b.id) : old;
    });
    if (bump) last.current = Math.max(last.current, ...list.map((m) => m.id));
  }, []);

  const polling = !!pid && (step.k === "arrive" || step.k === "chatjoin" || step.k === "chat");
  useEffect(() => {
    if (!polling) return;
    let alive = true;
    const ctrl = new AbortController();
    async function tick() {
      try {
        const r = await api.chatGet(pid, client.current, last.current, ctrl.signal);
        if (!alive) return;
        setLost(false);
        setMembers(r.members);
        setCount(r.count);
        setJoined(r.joined);
        merge(r.messages, true);
      } catch (e) {
        if (!alive || (e instanceof DOMException && e.name === "AbortError")) return;
        setLost(true);
      }
    }
    tick();
    const t = setInterval(tick, 2000);
    return () => {
      alive = false;
      ctrl.abort();
      clearInterval(t);
    };
  }, [polling, pid, client, merge]);

  const join = useCallback(async () => {
    try {
      const r = await api.chatJoin(pid, client.current, nick.current);
      nick.current = r.nick ?? nick.current;
      setMyNick(nick.current);
      setJoined(true);
      setMembers(r.members);
      setCount(r.count);
      merge(r.messages, true);
      replaceTop({ k: "chat" });
    } catch {
      note("톡방에 들어가지 못했어요. 인터넷 연결을 확인해 주세요.");
    }
  }, [pid, client, nick, merge, replaceTop, note]);

  /** 보내기: 성공 true, 실패면 {alert?|warn?} */
  const send = useCallback(
    async (text: string): Promise<true | { alert?: string; warn?: string }> => {
      try {
        const m = await api.chatSend(pid, client.current, text);
        merge([m], false);
        window.dispatchEvent(new CustomEvent("aigo:badge", { detail: { ev: "chat" } }));
        return true;
      } catch (e) {
        if (e instanceof ApiError && e.status === 400) {
          const d = e.detail as { code?: string; message?: string } | string | null;
          if (d && typeof d === "object" && d.code === "blocked") return { alert: d.message || "보낼 수 없는 말이 들어 있는 것 같아요. 고쳐서 보내 주세요" };
          if (typeof d === "string") return { warn: d };
        }
        return { warn: "보내지 못했어요. 다시 눌러 주세요" };
      }
    },
    [pid, client, merge],
  );

  const leave = useCallback(async () => {
    try {
      await api.chatLeave(pid, client.current);
    } catch {
      /* 실패해도 화면에서는 끝 */
    }
    setJoined(false);
    setMsgs([]);
    last.current = 0;
  }, [pid, client]);

  const report = useCallback(
    async (target: string) => {
      try {
        await api.chatReport(pid, client.current, target);
        note(`${target} 님을 신고했어요. 운영자가 대화를 살펴볼게요.`);
      } catch {
        note("신고하지 못했어요. 다시 해 주세요.");
      }
    },
    [pid, client, note],
  );

  const block = useCallback(
    (target: string) => {
      const next = Array.from(new Set([...readBlocked(), target]));
      saveBlocked(next);
      setBlocked(next);
      note(`${target} 님을 차단했어요. 그 사람의 말이 보이지 않아요.`);
    },
    [note],
  );

  const unblock = useCallback(
    (target: string) => {
      const next = readBlocked().filter((n) => n !== target);
      saveBlocked(next);
      setBlocked(next);
      note(`${target} 님 차단을 풀었어요. 그 사람의 말이 다시 보여요.`);
    },
    [note],
  );

  return { pid, msgs, members, count, joined, lost, blocked, myNick: myNick || nick.current, join, send, leave, report, block, unblock, reset: () => setBlocked([]) };
}
