"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Stage from "./Stage";
import TopBar from "./TopBar";
import Screen from "./screens";
import Busy from "./screens/Busy";
import * as api from "@/lib/api";
import { ApiError } from "@/lib/errors";
import { BASIC, DONT_KNOW } from "@/lib/questions";
import { GEO_TIMEOUT, MAX_FLEX_QUESTIONS, OPEN_FAIL, Q_FALLBACK, Q_NOTICE, REC_FAIL, REC_NOTICE, RECHECK_AFTER, NOTE_MS } from "@/lib/constants";
import { dongToOrigin, nearbyDongs, type Dong } from "@/lib/geo";
import { addVisit, cancelVisit, load, readVisits, save, sweepBackups, uuid } from "@/lib/device";
import { buildConditions, initialState, poseOf, type FlowState, type Q, type Step, type User } from "@/lib/flow";
import { getPose } from "@/lib/poses";
import type { Candidate, QuestionResp } from "@/lib/types";
import { THEMES } from "@/lib/theme";
import { useChat, type ChatApi } from "./useChat";
import Celebrate, { canCelebrate, useBadges } from "./Celebrate";
import { WAG, useIdle } from "./useIdle";
import { setPaused } from "@/lib/pause";
import { clockText } from "@/lib/format";

const NICKS = ["봄나들이", "햇살마중", "솔바람", "도란도란", "꽃마중", "느림보", "새벽길", "산들바람"];

type Req = { ctrl: AbortController; kind: "search" | "q" | "open" };

export type FlowApi = ReturnType<typeof useFlow> & { chat: ChatApi };

function isAbort(e: unknown) {
  return e instanceof DOMException && e.name === "AbortError";
}

function useFlow() {
  const [s, setS] = useState<FlowState>(initialState);
  const sRef = useRef(s);
  const req = useRef<Req | null>(null);
  const timers = useRef<Set<ReturnType<typeof setTimeout>>>(new Set());
  const noteTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const client = useRef("");
  const nick = useRef("");
  const backTo = useRef<Step[] | null>(null);
  /** 마지막 이동 방향 (질문 등장 연출은 뒤로 온 경우 건너뛰어요) */
  const navDir = useRef<"go" | "replace" | "back">("go");
  const [still, setStill] = useState(false);
  /** 연출 중 담고 자세 덮어쓰기 (가방 · 질문 등장) */
  const [poseOv, setPoseOv] = useState<string | null>(null);

  const set = useCallback((fn: Partial<FlowState> | ((p: FlowState) => Partial<FlowState>)) => {
    const prev = sRef.current;
    const patch = typeof fn === "function" ? fn(prev) : fn;
    const next = { ...prev, ...patch };
    sRef.current = next;
    setS(next);
  }, []);

  const later = useCallback((ms: number, fn: () => void) => {
    const t = setTimeout(() => {
      timers.current.delete(t);
      fn();
    }, ms);
    timers.current.add(t);
    return t;
  }, []);

  const note = useCallback(
    (text: string | null) => {
      if (noteTimer.current) clearTimeout(noteTimer.current);
      set({ note: text });
      if (text) noteTimer.current = setTimeout(() => set({ note: null }), NOTE_MS);
    },
    [set],
  );

  const top = () => sRef.current.stack[sRef.current.stack.length - 1];

  /* ---------- 화면 이동 (2절) ---------- */
  const go = useCallback(
    (step: Step) => {
      if (noteTimer.current) clearTimeout(noteTimer.current);
      navDir.current = "go";
      set((p) => ({ stack: [...p.stack, step], note: null }));
      try {
        history.pushState({ aigo: sRef.current.stack.length }, "");
      } catch {
        /* */
      }
    },
    [set],
  );

  const replaceTop = useCallback(
    (step: Step) => {
      navDir.current = "replace";
      set((p) => ({ stack: [...p.stack.slice(0, -1), step] }));
    },
    [set],
  );

  const back = useCallback(() => {
    history.back();
  }, []);

  const backWith = useCallback(
    (text: string) => {
      history.back();
      setTimeout(() => note(text), 80);
    },
    [note],
  );

  const abortReq = useCallback(() => {
    req.current?.ctrl.abort();
    req.current = null;
  }, []);

  const home = useCallback(() => {
    abortReq();
    set((p) => ({
      ...initialState(),
      origin: p.origin,
      user: p.user,
      coral: p.coral,
      social: p.social,
      stack: [{ k: "start" }],
    }));
  }, [abortReq, set]);

  const landHome = useCallback(
    (text?: string) => {
      backTo.current = null;
      home();
      if (text) setTimeout(() => note(text), 30);
    },
    [home, note],
  );

  const landAuthed = useCallback(
    (text?: string) => {
      const b = backTo.current;
      if (b) {
        backTo.current = null;
        set({ stack: b });
        if (text) setTimeout(() => note(text), 30);
      } else landHome(text);
    },
    [landHome, note, set],
  );

  /* popstate (2.1) */
  useEffect(() => {
    function onPop() {
      const r = req.current;
      if (r) {
        r.ctrl.abort();
        req.current = null;
        set({ busy: null });
        if (r.kind === "search") {
          history.pushState({ aigo: 1 }, "");
          return;
        }
      }
      const p = sRef.current;
      if (p.stack.length <= 1) return;
      const t = p.stack[p.stack.length - 1];
      if (t.k === "chat") {
        history.pushState({ aigo: 1 }, "");
        window.dispatchEvent(new CustomEvent("aigo:chat-leave-ask"));
        return;
      }
      if (t.k === "route") {
        const c = p.cands[p.idx];
        if (c) {
          cancelVisit(c.place.id);
          api.expectCancel(c.place.id, client.current).then(
            (r2) => set((q) => ({ social: { ...q.social, [c.place.id]: { ...(q.social[c.place.id] ?? { reviewCount: 0, topTags: [] }), expectedToday: r2.expectedToday } } })),
            () => {},
          );
        }
      }
      if (noteTimer.current) clearTimeout(noteTimer.current);
      navDir.current = "back";
      set((q) => ({ stack: q.stack.slice(0, -1), note: null, preparing: -1, qNotice: false }));
    }
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, [set]);

  /* 처음 한 번: 기기 표시 · 닉네임 · 테마 · 로그인 상태 · 주소 읽기 */
  useEffect(() => {
    client.current = uuid();
    nick.current = NICKS[Math.floor(Math.random() * NICKS.length)];
    sweepBackups();
    const theme = load<string>("aigo.theme", "A");
    const coral = THEMES.find((t) => t.id === theme)?.color ?? THEMES[0].color;
    const cached = load<User | null>("aigo.user", null);
    set({ coral, user: cached });
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) setStill(true);
    const url = new URL(location.href);
    const qp = url.searchParams;
    const login = qp.get("login");
    const toKwait = qp.has("signup") || qp.has("restore") || login === "ok";
    if (qp.has("login") || qp.has("signup") || qp.has("restore")) {
      qp.delete("login");
      qp.delete("signup");
      qp.delete("restore");
      history.replaceState(null, "", url.pathname + (qp.toString() ? `?${qp}` : "") + url.hash);
    }
    if (toKwait) {
      set({ stack: [{ k: "start" }, { k: "kwait" }] });
      history.pushState({ aigo: 2 }, "");
    } else {
      if (login === "fail") setTimeout(() => note("카카오 로그인을 하지 못했어요. 다시 해 주세요."), 50);
      if (login === "banned") setTimeout(() => note("이용이 제한된 계정이에요. 궁금한 점은 운영자에게 문의해 주세요"), 50);
      api.me().then(
        (m) => {
          const u = m.loggedIn ? m : null;
          save("aigo.user", u);
          set({ user: u });
        },
        () => {},
      );
    }
    const ts = timers.current;
    return () => {
      ts.forEach(clearTimeout);
    };
  }, [set, note]);

  /* 화면이 바뀌면 제목에 초점 (2.2) */
  const stepKey = `${s.stack.length}:${top()?.k}`;
  useEffect(() => {
    const h = document.querySelector<HTMLElement>(".content h1");
    h?.focus({ preventScroll: true });
  }, [stepKey]);

  /* ---------- 출발점 (4.2) ---------- */
  const setOriginDong = useCallback(
    (d: Dong) => {
      set({ origin: dongToOrigin(d) });
      go({ k: "open" });
    },
    [go, set],
  );

  const useMyLocation = useCallback(() => {
    const fail = () => {
      set({ busy: null });
      go({ k: "gu" });
      setTimeout(() => note("위치를 받지 못했어요. 출발할 곳을 직접 골라 주세요."), 30);
    };
    if (!("geolocation" in navigator)) return fail();
    set({ busy: "가까운 동을 찾고 있어요" });
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const r = nearbyDongs(pos.coords.latitude, pos.coords.longitude);
        set({ busy: null });
        if (r.outside) {
          go({ k: "gu" });
          setTimeout(() => note("위치로는 서울에서만 찾을 수 있어요. 출발할 곳을 직접 골라 주세요."), 30);
          return;
        }
        go({ k: "nearby", list: r.list, widened: r.widened });
      },
      fail,
      { timeout: GEO_TIMEOUT, maximumAge: 0, enableHighAccuracy: false },
    );
  }, [go, note, set]);

  /* ---------- 질문 (5절) ---------- */
  const nextEmpty = useCallback(
    (how: "go" | "replace" = "go") => {
      const p = sRef.current;
      const nav = how === "go" ? go : replaceTop;
      if (p.body === undefined) return nav({ k: "body" });
      if (p.time === undefined) return nav({ k: "time" });
      const n = p.qs.length;
      if (n >= MAX_FLEX_QUESTIONS && p.qs.every((q) => q.answered)) return nav({ k: "confirm" });
      return nav({ k: "flex", i: p.qs.filter((q) => q.answered).length });
    },
    [go, replaceTop],
  );

  const submitOpen = useCallback(
    async (text: string | null) => {
      const base: Partial<FlowState> = { body: undefined, time: undefined, qs: [], heard: [], filled: [], place: null, who: null, wish: [], fallback: false };
      set(base);
      const t = (text ?? "").trim();
      if (!t || t === DONT_KNOW) return nextEmpty();
      abortReq();
      const ctrl = new AbortController();
      req.current = { ctrl, kind: "open" };
      set({ busy: "질문 0 말씀을 듣고 있어요" });
      let timedOut = false;
      const timer = setTimeout(() => {
        timedOut = true;
        ctrl.abort();
      }, OPEN_FAIL);
      try {
        const r = await api.questionsOpen(buildConditions(sRef.current), t, ctrl.signal);
        clearTimeout(timer);
        if (req.current?.ctrl === ctrl) req.current = null;
        const f = new Set(r.filled);
        const c = r.conditions;
        const qs: Q[] = [];
        for (const b of BASIC) {
          const v = c.basic[b.slot];
          if (f.has(b.slot) && v) qs.push({ question: b.question, choices: b.choices, slot: b.slot, src: "open", answered: true, a: v, dk: b.slot !== "inout" });
        }
        set({
          busy: null,
          body: f.has("body") ? c.body : undefined,
          time: f.has("time") ? c.time : undefined,
          qs,
          place: f.has("place") ? c.extra.place : null,
          who: f.has("who") ? c.extra.who : null,
          wish: f.has("wish") ? (c.extra.wish ?? []) : [],
          filled: r.filled,
          heard: r.heard?.items ?? [],
        });
        nextEmpty();
      } catch (e) {
        clearTimeout(timer);
        if (req.current?.ctrl === ctrl) req.current = null;
        set({ busy: null });
        // 뒤로로 멈췄으면 아무것도 안 해요
        if (isAbort(e) && !timedOut) return;
        if (top().k === "open") nextEmpty();
      }
    },
    [abortReq, nextEmpty, set],
  );

  const toBasic = useCallback(
    (i: number) => {
      const p = sRef.current;
      const used = new Set(p.qs.slice(0, i).map((q) => q.slot));
      const b = BASIC.find((x) => !used.has(x.slot));
      if (!b) {
        set({ preparing: -1, qNotice: false });
        return replaceTop({ k: "confirm" });
      }
      const q: Q = { question: b.question, choices: b.choices, slot: b.slot, src: "basic", answered: false, a: null, dk: b.slot !== "inout" };
      set((pp) => ({ fallback: true, qs: [...pp.qs.slice(0, i), q], preparing: -1, qNotice: false }));
    },
    [replaceTop, set],
  );

  const prepare = useCallback(
    async (i: number) => {
      const p = sRef.current;
      if (p.preparing === i) return;
      if (p.fallback) return toBasic(i);
      abortReq();
      const ctrl = new AbortController();
      req.current = { ctrl, kind: "q" };
      set({ preparing: i, qNotice: false });
      const tn = setTimeout(() => {
        if (sRef.current.preparing === i) set({ qNotice: true });
      }, Q_NOTICE);
      let timedOut = false;
      const tf = setTimeout(() => {
        timedOut = true;
        ctrl.abort();
      }, Q_FALLBACK);
      const stillHere = () => {
        const t = top();
        return t.k === "flex" && t.i === i;
      };
      try {
        const cond = buildConditions({ ...sRef.current, qs: sRef.current.qs.slice(0, i) });
        const r: QuestionResp = await api.questionsNext(cond, ctrl.signal);
        clearTimeout(tn);
        clearTimeout(tf);
        if (req.current?.ctrl === ctrl) req.current = null;
        if (!stillHere()) return set({ preparing: -1, qNotice: false });
        if (r.done) {
          set({ preparing: -1, qNotice: false });
          return replaceTop({ k: "confirm" });
        }
        if (r.fallback === true || (!r.question && r.needsAi)) {
          const fb = typeof r.fallback === "object" && r.fallback ? r.fallback : null;
          if (fb?.question && fb.choices?.length) return putQ(i, fb, "basic");
          return toBasic(i);
        }
        if (r.question && r.choices?.length) return putQ(i, r, "ai");
        return toBasic(i);
      } catch (e) {
        clearTimeout(tn);
        clearTimeout(tf);
        if (req.current?.ctrl === ctrl) req.current = null;
        if (isAbort(e) && !timedOut) return set({ preparing: -1, qNotice: false });
        if (stillHere()) toBasic(i);
        else set({ preparing: -1, qNotice: false });
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [abortReq, replaceTop, set, toBasic],
  );

  function putQ(i: number, r: QuestionResp, src: "ai" | "basic") {
    const slot = r.slot === "want" || r.slot === "walk" || r.slot === "inout" ? r.slot : null;
    const raw = (r.choices ?? []).filter(Boolean);
    const hadDk = raw.includes(DONT_KNOW);
    const choices = raw.filter((c) => c !== DONT_KNOW).slice(0, 4);
    const q: Q = { question: r.question ?? "", choices, slot, src, answered: false, a: null, dk: slot !== "inout" || hadDk };
    set((p) => ({ qs: [...p.qs.slice(0, i), q], preparing: -1, qNotice: false }));
  }

  const answerBody = useCallback(
    (v: string | null) => {
      const edit = top().k === "body" && (top() as { edit?: boolean }).edit;
      set((p) => ({ body: v, filled: p.filled.filter((f) => f !== "body") }));
      if (edit) return back();
      nextEmpty();
    },
    [back, nextEmpty, set],
  );

  const answerTime = useCallback(
    (v: string | null) => {
      const edit = top().k === "time" && (top() as { edit?: boolean }).edit;
      set((p) => ({ time: v, filled: p.filled.filter((f) => f !== "time") }));
      if (edit) return back();
      const n = sRef.current.qs.filter((q) => q.src === "open").length;
      if (n >= MAX_FLEX_QUESTIONS) return go({ k: "confirm" });
      go({ k: "flex", i: n });
    },
    [back, go, set],
  );

  const answerFlex = useCallback(
    (i: number, v: string | null) => {
      const t = top();
      const edit = t.k === "flex" && t.edit;
      set((p) => {
        const old = p.qs[i];
        if (!old) return {};
        const changed = old.answered && old.a !== v;
        const qs = p.qs.slice(0, changed && !edit ? i + 1 : p.qs.length);
        qs[i] = { ...old, answered: true, a: v };
        return { qs, filled: old.slot === "walk" ? p.filled.filter((f) => f !== "walk") : p.filled };
      });
      if (edit) return back();
      if (i + 1 >= MAX_FLEX_QUESTIONS) return go({ k: "confirm" });
      go({ k: "flex", i: i + 1 });
    },
    [back, go, set],
  );

  /** 이렇게 들었어요 칩 지우기 (5.2, AI 없이) */
  const forget = useCallback(
    (item: { key: string; value: string }) => {
      const p = sRef.current;
      const patch: Partial<FlowState> = { heard: p.heard.filter((h) => !(h.key === item.key && h.value === item.value)) };
      let qs = p.qs;
      if (item.key === "body") patch.body = undefined;
      else if (item.key === "time") patch.time = undefined;
      else if (item.key === "place") patch.place = null;
      else if (item.key === "who") patch.who = null;
      else if (item.key === "wish") patch.wish = p.wish.filter((w) => w !== item.value);
      else {
        const at = qs.findIndex((q) => q.src === "open" && q.slot === item.key);
        if (at >= 0) qs = qs.slice(0, at).concat(qs.slice(at + 1).filter((q) => q.src === "open"));
        patch.qs = qs;
      }
      patch.filled = p.filled.filter((f) => f !== item.key);
      if (req.current?.kind === "q") abortReq();
      set({ ...patch, preparing: -1, qNotice: false });
      const t = top();
      const order = (k: string) => (k === "body" ? 0 : k === "time" ? 1 : 2);
      const n = sRef.current;
      if (n.body === undefined && order(t.k) > 0) return replaceTop({ k: "body" });
      if (n.time === undefined && order(t.k) > 1) return replaceTop({ k: "time" });
      if (t.k === "flex" && patch.qs) {
        const i = n.qs.filter((q) => q.answered).length;
        replaceTop({ k: "flex", i });
      }
    },
    [abortReq, replaceTop, set],
  );

  /* ---------- 찾기 (8.1) ---------- */
  const search = useCallback(
    async (how: "push" | "stay", keepSeen = false) => {
      const p = sRef.current;
      abortReq();
      const ctrl = new AbortController();
      req.current = { ctrl, kind: "search" };
      set({ busy: "갈 곳을 찾고 있어요" });
      const tn = setTimeout(() => {
        if (req.current?.ctrl === ctrl) set({ busy: "조금만 더 기다려 주세요. 거의 다 찾았어요" });
      }, REC_NOTICE);
      let timedOut = false;
      const tf = setTimeout(() => {
        timedOut = true;
        ctrl.abort();
      }, REC_FAIL);
      const exclude = keepSeen ? p.seen : [];
      const place = (step: Step) => {
        if (how === "push") return go(step);
        if (top().k !== step.k) return go(step);
        replaceTop(step);
      };
      try {
        const r = await api.recommend(buildConditions(p, exclude), readVisits().map((v) => v.id), ctrl.signal);
        clearTimeout(tn);
        clearTimeout(tf);
        if (req.current?.ctrl === ctrl) req.current = null;
        set({ busy: null });
        if (!r.candidates?.length) return place({ k: "notFound", why: (r.why as "none" | "timeout") === "timeout" ? "timeout" : "none" });
        const ids = r.candidates.map((c) => c.place.id);
        set((q) => ({
          cands: r.candidates,
          idx: 0,
          receivedAt: Date.now(),
          closed: [],
          seen: Array.from(new Set([...(keepSeen ? q.seen : []), ...ids])),
          weather: r.weather?.weather ?? "",
        }));
        // note()는 앞 안내를 덮어써서 두 안내를 한 줄로 합쳐요
        const told: string[] = [];
        if (r.expanded?.from?.length && r.expanded.words?.length)
          told.push(`${r.expanded.from.join(" · ")} → ${r.expanded.words.join(" · ")}으로 넓혀 찾았어요`);
        if (r.relaxed) told.push("가까운 곳이 없어서 조금 더 먼 곳까지 찾았어요");
        if (told.length) setTimeout(() => note(told.join(" · ")), 60);
        window.dispatchEvent(new CustomEvent("aigo:badge", { detail: { ev: "recommend" } }));
        if (how === "push" || top().k !== "result") go({ k: "result" });
      } catch (e) {
        clearTimeout(tn);
        clearTimeout(tf);
        if (req.current?.ctrl === ctrl) req.current = null;
        set({ busy: null });
        if (isAbort(e) && !timedOut) return;
        place({ k: "notFound", why: timedOut ? "timeout" : "offline" });
      }
    },
    [abortReq, go, replaceTop, set],
  );

  /** 결과 보기 (5.5) */
  const skipToResult = useCallback(() => {
    abortReq();
    const p = sRef.current;
    const filled = [...p.filled];
    const told: string[] = [];
    const patch: Partial<FlowState> = { preparing: -1, qNotice: false };
    if (p.body == null) {
      patch.body = "좀 무거워요";
      filled.push("body");
      told.push("몸 → 좀 무거워요");
    }
    if (p.time == null) {
      patch.time = "반나절";
      filled.push("time");
      told.push("시간 → 반나절");
    }
    if (!p.qs.some((q) => q.answered && q.slot === "walk" && q.a)) {
      filled.push("walk");
      told.push("걷기 → 조금만요");
    }
    patch.filled = Array.from(new Set(filled));
    patch.qs = p.qs.filter((q) => q.answered);
    set(patch);
    search("push").then(() => {
      if (told.length) note(`답하지 않은 건 무난하게 정했어요 · ${told.join(" · ")}`);
    });
  }, [abortReq, note, search, set]);

  /* ---------- 결과 · 고르기 (8.2 · 8.3) ---------- */
  const cand = (): Candidate | undefined => sRef.current.cands[sRef.current.idx];

  const loadSocial = useCallback(
    (id: string) => {
      api.social(id).then(
        (r) => set((p) => ({ social: { ...p.social, [id]: r } })),
        () => {},
      );
    },
    [set],
  );

  const showCand = useCallback((i: number) => set({ idx: i }), [set]);

  const choose = useCallback(
    async (fromGuestbook = false) => {
      const p = sRef.current;
      const c = cand();
      if (!c || p.tearing) return;
      if (Date.now() - p.receivedAt > RECHECK_AFTER) {
        try {
          const o = await api.placeOpen(c.place.id);
          if (o.open === false) {
            set((q) => ({ closed: [...q.closed, c.place.id] }));
            return;
          }
        } catch {
          /* 확인 실패면 막지 않아요 */
        }
      }
      addVisit({ id: c.place.id, name: c.place.name, kind: c.place.kind, from: p.origin?.name ?? "", min: c.route?.totalMin ?? 0 });
      window.dispatchEvent(new CustomEvent("aigo:badge", { detail: { ev: "ticket" } }));
      api.expect(c.place.id, client.current).then(
        (r) => set((q) => ({ social: { ...q.social, [c.place.id]: { ...(q.social[c.place.id] ?? { reviewCount: 0, topTags: [] }), expectedToday: r.expectedToday } } })),
        () => {},
      );
      if (fromGuestbook) {
        replaceTop({ k: "route" });
        return;
      }
      set({ tearing: true });
      later(still ? 0 : 900, () => {
        set({ tearing: false });
        go({ k: "route" });
      });
    },
    [go, later, replaceTop, set, still],
  );

  /** 로그인 사본 맞추기 */
  const setUser = useCallback(
    (u: User | null) => {
      save("aigo.user", u);
      set({ user: u });
    },
    [set],
  );

  const refreshMe = useCallback(async (): Promise<User | null> => {
    const m = await api.me();
    const u = m.loggedIn ? m : null;
    setUser(u);
    return u;
  }, [setUser]);

  /** 도착했어요 (9.1) */
  const arrive = useCallback(() => {
    const c = cand();
    if (!c) return;
    set({ arrivedAt: clockText() });
    window.dispatchEvent(new CustomEvent("aigo:badge", { detail: { ev: "arrive", id: c.place.id, kind: c.place.kind, gu: c.place.gu, weather: sRef.current.weather } }));
    go({ k: "arrive" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [go, set]);

  return {
    s,
    sRef,
    navDir,
    poseOv,
    setPoseOv,
    arrive,
    setUser,
    refreshMe,
    set,
    go,
    replaceTop,
    back,
    backWith,
    home,
    landHome,
    landAuthed,
    note,
    later,
    still,
    client,
    nick,
    backTo,
    abortReq,
    setOriginDong,
    useMyLocation,
    submitOpen,
    prepare,
    answerBody,
    answerTime,
    answerFlex,
    forget,
    search,
    skipToResult,
    loadSocial,
    showCand,
    choose,
  };
}

export default function Flow() {
  const base = useFlow();
  const chat = useChat({ s: base.s, client: base.client, nick: base.nick, note: base.note, replaceTop: base.replaceTop });
  const f: FlowApi = { ...base, chat };
  const { s } = f;
  const step = s.stack[s.stack.length - 1];
  const busy = s.busy && !s.busy.startsWith("질문") ? s.busy : null;
  const poseKey = useMemo(() => {
    if (busy) return busy.startsWith("가까운") ? "kwait" : busy.startsWith("조금만") ? "wait" : "find";
    if (s.busy?.startsWith("질문 0")) return "ask";
    if (f.poseOv) return f.poseOv;
    return poseOf(step, s);
  }, [busy, s, step, f.poseOv]);

  const badges = useBadges(s.user);
  const idle = useIdle(poseKey, !f.still && !busy && !f.poseOv && !s.busy);
  const shownKey = idle.key;
  const isResult = poseKey === "s4" || poseKey === "s4p";
  const cele = badges.queue.length && canCelebrate(s) ? badges.queue[0] : null;
  useEffect(() => {
    setPaused(!!cele); // 축하 화면이 떠 있는 동안 게임을 그 자리에 멈춰요
    return () => setPaused(false);
  }, [cele]);

  return (
    <Stage
      poseKey={poseKey}
      pose={getPose(shownKey)}
      blink={idle.blink}
      wag={WAG.has(poseKey)}
      move={idle.key !== poseKey ? 0.45 : isResult ? 1 : 0.6}
      coral={s.coral}
      still={f.still}
      inert={!!cele}
      overlay={
        <>
          {s.note ? (
            <div className="toast" role="status">
              {s.note}
            </div>
          ) : null}
          {cele && (
            <Celebrate
              b={cele}
              more={badges.queue.length > 1}
              onNext={badges.next}
              onAll={() => {
                badges.clear();
                if (step.k !== "badges") f.go({ k: "badges" });
              }}
            />
          )}
        </>
      }
    >
      {busy ? (
        <Busy text={busy} />
      ) : (
        <>
          <Screen f={f} step={step} />
          <TopBar f={f} step={step} />
        </>
      )}
    </Stage>
  );
}

export { ApiError };
