"use client";

import { useEffect, useRef, useState } from "react";
import type { FlowApi } from "../Flow";
import { Sub, Title } from "../ui";
import * as api from "@/lib/api";
import { load, save } from "@/lib/device";
import { fmtNum } from "@/lib/format";
import type { RankEntry } from "@/lib/types";

/* 담고 달리기 (12절) — 393 기준, 판 345 × 300 */
const GW = 345;
const GH = 300;
const GROUND = 248;
const PX = 70;
const G = 2600;
const JUMP = 660;
const LANDMARKS = ["광화문", "경복궁", "남산서울타워", "63빌딩", "잠실종합운동장", "롯데월드타워"];
const SAMPLES: [string, number][] = [
  ["봄나들이", 1820], ["햇살마중", 1460], ["솔바람", 1190], ["도란도란", 940], ["꽃마중", 720], ["느림보", 510], ["새벽길", 330], ["산들바람", 160],
];

type Ob = { x: number; w: number; h: number; y: number; kind: "pot" | "post" | "bench" | "bird"; speed: number };
type Phase = "ready" | "run" | "pause" | "over";

function mix(hex: string, to: number[], a: number) {
  const h = hex.replace("#", "");
  const c = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
  return `rgb(${c.map((v, i) => Math.round(v * (1 - a) + to[i] * a)).join(",")})`;
}

type LocalRank = { nick: string; steps: number; at: number; me?: boolean }[];
const RANK_KEY = "aigo.game.ranking";
const useApiRank = process.env.NEXT_PUBLIC_RANKING_SOURCE === "api";

function localRanking(myNick: string | null): { top: RankEntry[]; me: { rank: number; entry: RankEntry } | null } {
  const mine = load<LocalRank>(RANK_KEY, []);
  const all: LocalRank = [...SAMPLES.map(([n, s], i) => ({ nick: n, steps: s, at: i })), ...mine].sort((a, b) => b.steps - a.steps || a.at - b.at);
  const rows = all.map((r) => ({ nickname: r.nick, steps: r.steps, at: String(r.at), mine: !!myNick && r.nick === myNick && !!r.me }));
  const idx = rows.findIndex((r) => r.mine);
  return { top: rows.slice(0, 10), me: idx >= 0 ? { rank: idx + 1, entry: rows[idx] } : null };
}

export function Game({ f }: { f: FlowApi }) {
  const u = f.s.user;
  const cv = useRef<HTMLCanvasElement>(null);
  const [phase, setPhase] = useState<Phase>("ready");
  const [steps, setSteps] = useState(0);
  const [best, setBest] = useState(0);
  const [isBest, setIsBest] = useState(false);
  const [rankLine, setRankLine] = useState("");
  const [cheer, setCheer] = useState<string | null>(null);
  const st = useRef({ y: 0, vy: 0, speed: 220, t: 0, dist: 0, obs: [] as Ob[], gap: 300, buffered: 0, overAt: 0, lastKey: 0, phase: "ready" as Phase, cheered: 0 });
  const bestKey = u ? `aigo.game.best.${u.id}` : "aigo.game.best";

  useEffect(() => setBest(load<number>(bestKey, 0)), [bestKey]);

  function reset() {
    Object.assign(st.current, { y: 0, vy: 0, speed: 220, t: 0, dist: 0, obs: [], gap: 300, buffered: 0, cheered: 0 });
    setSteps(0);
    setIsBest(false);
    setRankLine("");
  }

  function setP(p: Phase) {
    st.current.phase = p;
    setPhase(p);
  }

  async function over() {
    const s = st.current;
    setP("over");
    s.overAt = performance.now();
    const n = Math.floor(s.dist / 8);
    navigator.vibrate?.(80);
    const prev = load<number>(bestKey, 0);
    const nb = n > prev;
    if (nb) save(bestKey, n);
    setBest(Math.max(prev, n));
    setIsBest(nb);
    window.dispatchEvent(new CustomEvent("aigo:badge", { detail: { ev: "run", steps: n } }));
    if (!u) return setRankLine("로그인하면 랭킹에 이름이 올라가요");
    if (useApiRank) {
      setRankLine("랭킹에 올리는 중이에요…");
      try {
        const r = await api.gameScore(n);
        setRankLine(`랭킹 ${r.rank}위예요`);
      } catch {
        setRankLine("랭킹에 올리지 못했어요. 다음 판에 다시 올려요");
      }
    } else {
      const nick = u.nickname || "이름 없는 회원";
      const list = load<LocalRank>(RANK_KEY, []).filter((r) => !(r.me && r.nick === nick));
      const myBest = Math.max(n, load<LocalRank>(RANK_KEY, []).find((r) => r.me && r.nick === nick)?.steps ?? 0);
      list.push({ nick, steps: myBest, at: Date.now(), me: true });
      save(RANK_KEY, list);
      const r = localRanking(nick);
      setRankLine(r.me ? `랭킹 ${r.me.rank}위예요` : "");
    }
  }

  function press() {
    const s = st.current;
    if (s.phase === "ready") {
      reset();
      setP("run");
      return jump();
    }
    if (s.phase === "pause") return setP("run");
    if (s.phase === "over") {
      if (performance.now() - s.overAt < 600) return;
      reset();
      setP("run");
      return;
    }
    jump();
  }
  function jump() {
    const s = st.current;
    if (s.y <= 0.5) s.vy = JUMP;
    else s.buffered = performance.now();
  }

  useEffect(() => {
    const c = cv.current;
    if (!c) return;
    const zoom = parseFloat(getComputedStyle(document.querySelector(".app")!).getPropertyValue("--zoom")) || 1;
    const k = Math.min(4, (window.devicePixelRatio || 1) * zoom);
    c.width = GW * k;
    c.height = GH * k;
    const ctx = c.getContext("2d")!;
    ctx.scale(k, k);
    let raf = 0;
    let last = performance.now();
    const coral = f.s.coral;
    const sky = mix(coral, [255, 255, 255], 0.72);
    const far = mix(coral, [255, 255, 255], 0.45);
    const tree = mix(coral, [0, 0, 0], 0.25);

    function spawn() {
      const s = st.current;
      const n = s.dist / 8;
      const r = Math.random();
      let ob: Ob;
      if (n > 350 && Math.random() < 0.2) ob = { kind: "bird", w: 32, h: 20, y: 24 + Math.random() * 8, x: GW + 10, speed: 1.12 };
      else if (r < 0.42) ob = { kind: "pot", w: 24, h: 34, y: 0, x: GW + 10, speed: 1 };
      else if (r < 0.68) ob = { kind: "post", w: 28, h: 46, y: 0, x: GW + 10, speed: 1 };
      else ob = { kind: "bench", w: 54, h: 26, y: 0, x: GW + 10, speed: 1 };
      s.obs.push(ob);
      if (ob.kind === "pot" && n > 250 && Math.random() < 0.3) s.obs.push({ ...ob, x: ob.x + 26 });
      s.gap = ob.w + s.speed * 0.95 + Math.random() * (170 + s.speed * 0.35);
    }

    function draw() {
      const s = st.current;
      ctx.fillStyle = sky;
      ctx.fillRect(0, 0, GW, GH);
      // 먼 빌딩
      ctx.fillStyle = far;
      const off = (s.dist * 0.2) % 60;
      for (let i = -1; i < 8; i++) {
        const h = 40 + ((i * 37) % 50);
        ctx.fillRect(i * 60 - off, GROUND - h, 44, h);
      }
      // 랜드마크 이름
      const lm = LANDMARKS[Math.floor(s.dist / 8 / 330) % LANDMARKS.length];
      ctx.fillStyle = tree;
      ctx.font = "800 13px Pretendard Variable, sans-serif";
      ctx.fillText(lm, 12, 22);
      // 땅
      ctx.fillStyle = "#111";
      ctx.fillRect(0, GROUND, GW, 2);
      ctx.fillStyle = mix(coral, [0, 0, 0], 0.05);
      ctx.fillRect(0, GROUND + 2, GW, GH - GROUND);
      // 장애물
      for (const o of s.obs) {
        const top = GROUND - o.h - o.y;
        if (o.kind === "pot") {
          ctx.fillStyle = tree;
          ctx.beginPath();
          ctx.arc(o.x + o.w / 2, top + 10, 12, 0, Math.PI * 2);
          ctx.fill();
          ctx.fillStyle = "#8A5A3C";
          ctx.fillRect(o.x + 3, top + 16, o.w - 6, o.h - 16);
        } else if (o.kind === "post") {
          ctx.fillStyle = "#E8473D";
          ctx.fillRect(o.x, top, o.w, o.h);
          ctx.fillStyle = "#111";
          ctx.fillRect(o.x + 6, top + 10, o.w - 12, 4);
        } else if (o.kind === "bench") {
          ctx.fillStyle = "#6B4A2E";
          ctx.fillRect(o.x, top, o.w, 8);
          ctx.fillRect(o.x + 4, top + 8, 5, o.h - 8);
          ctx.fillRect(o.x + o.w - 9, top + 8, 5, o.h - 8);
        } else {
          ctx.fillStyle = "#777";
          ctx.beginPath();
          ctx.ellipse(o.x + 16, top + 10, 16, 9, 0, 0, Math.PI * 2);
          ctx.fill();
        }
      }
      // 담고
      const by = GROUND - 2 - s.y;
      ctx.fillStyle = "#DEDEDE";
      ctx.beginPath();
      ctx.arc(PX - 26, by - 40, 14, 0, Math.PI * 2);
      ctx.fill();
      ctx.save();
      ctx.translate(PX, by - 34);
      ctx.scale(0.36, 0.36);
      ctx.translate(-95, -97);
      ctx.fillStyle = "#fff";
      ctx.beginPath();
      ctx.arc(60, 32, 22, 0, Math.PI * 2);
      ctx.arc(126, 28, 22, 0, Math.PI * 2);
      ctx.fill();
      ctx.fill(new Path2D("M22 112 C18 64 52 36 94 36 C138 36 170 62 168 108 C166 142 136 158 94 158 C50 158 24 144 22 112 Z"));
      ctx.fillStyle = "#111";
      ctx.fill(new Path2D("M22 112 C24 94 40 82 58 80 C74 78 84 88 94 84 C106 78 122 76 138 80 C156 86 168 96 168 108 C166 142 136 158 94 158 C50 158 24 144 22 112 Z"));
      ctx.fillStyle = "#fff";
      const closed = s.phase === "over";
      ctx.beginPath();
      ctx.ellipse(78, 113, 9.5, closed ? 1.5 : 15, 0, 0, Math.PI * 2);
      ctx.ellipse(120, 110, 9.5, closed ? 1.5 : 15, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    }

    function frame(now: number) {
      const s = st.current;
      const dt = Math.min(0.033, (now - last) / 1000);
      last = now;
      if (s.phase === "run" && !document.querySelector('[aria-label="새 배지를 얻었어요"]')) {
        s.t += dt;
        s.speed = Math.min(470, 220 + Math.floor(s.t) * 5);
        s.vy -= G * dt;
        s.y = Math.max(0, s.y + s.vy * dt);
        if (s.y === 0) {
          s.vy = Math.max(0, s.vy);
          if (s.buffered && now - s.buffered < 160) {
            s.vy = JUMP;
            s.buffered = 0;
          }
        }
        const dx = s.speed * dt;
        s.dist += dx;
        s.gap -= dx;
        if (s.gap <= 0) spawn();
        s.obs.forEach((o) => (o.x -= dx * o.speed));
        s.obs = s.obs.filter((o) => o.x + o.w > -10);
        const n = Math.floor(s.dist / 8);
        setSteps(n);
        if (Math.floor(n / 500) > s.cheered) {
          s.cheered = Math.floor(n / 500);
          setCheer(`${fmtNum(s.cheered * 500)}걸음!`);
          setTimeout(() => setCheer(null), 1400);
        }
        // 부딪힘 (너그럽게)
        const dl = PX - 18;
        const dr = PX + 18;
        const db = GROUND - s.y + 3;
        const dt2 = GROUND - s.y - 66 + 30;
        for (const o of s.obs) {
          const ol = o.x + 4;
          const or = o.x + o.w - 4;
          const ob = GROUND - o.y + 2 - 2;
          const ot = GROUND - o.y - o.h + 5;
          if (dr > ol && dl < or && db > ot && dt2 < ob) {
            over();
            break;
          }
        }
      }
      draw();
      raf = requestAnimationFrame(frame);
    }
    raf = requestAnimationFrame(frame);
    const vis = () => {
      if (document.hidden && st.current.phase === "run") setP("pause");
    };
    document.addEventListener("visibilitychange", vis);
    const key = (e: KeyboardEvent) => {
      if (e.code !== "Space" && e.code !== "ArrowUp") return;
      if (document.querySelector('[aria-label="새 배지를 얻었어요"]')) return;
      if (e.repeat && st.current.phase !== "run") return;
      e.preventDefault();
      st.current.lastKey = performance.now();
      press();
    };
    window.addEventListener("keydown", key);
    return () => {
      cancelAnimationFrame(raf);
      document.removeEventListener("visibilitychange", vis);
      window.removeEventListener("keydown", key);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [f.s.coral]);

  const big = phase === "ready" ? "출발하기" : phase === "run" ? "폴짝!" : phase === "pause" ? "이어 달리기" : "다시 달리기";
  return (
    <div className="content">
      <Title y={100}>담고 달리기</Title>
      <div className="abs" style={{ left: 24, right: 24, top: 150, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span className="t-tvalue">{fmtNum(steps)}걸음</span>
        <button className="chip chip-soft" disabled={phase === "run"} style={{ opacity: phase === "run" ? 0.4 : 1 }} onClick={() => f.go({ k: "rank" })}>
          최고 {fmtNum(best)}걸음 랭킹 ›
        </button>
      </div>
      <div className="abs" style={{ left: 24, top: 190, width: GW, height: GH, borderRadius: 24, overflow: "hidden", boxShadow: "var(--sh-row)" }} onPointerDown={(e) => e.button === 0 && press()}>
        <canvas ref={cv} style={{ width: GW, height: GH, display: "block" }} aria-label="게임 판" />
        {cheer && (
          <span className="chip" style={{ position: "absolute", left: "50%", top: 60, transform: "translateX(-50%)", fontSize: 18, height: 40, lineHeight: "40px", borderRadius: 20, padding: "0 18px" }}>
            {cheer}
          </span>
        )}
        {phase !== "run" && (
          <div style={{ position: "absolute", inset: 0, background: "rgba(255,255,255,.72)", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", textAlign: "center", padding: 20 }}>
            {phase === "ready" && (
              <>
                <p className="t-tile">담고와 나들이 가요</p>
                <p className="t-sub c-sub pre" style={{ marginTop: 8 }}>
                  {"큰 버튼을 누르면 출발하고,\n한 번 더 누르면 폴짝 뛰어요"}
                </p>
              </>
            )}
            {phase === "pause" && (
              <>
                <p className="t-tile">잠깐 쉬는 중이에요</p>
                <p className="t-sub c-sub" style={{ marginTop: 8 }}>
                  버튼을 누르면 이어서 달려요
                </p>
              </>
            )}
            {phase === "over" && (
              <div role="status" aria-label={`아이고! ${steps}걸음 걸었어요. ${isBest ? "최고 기록이에요." : ""} ${rankLine}`}>
                <p className="t-label c-deep">아이고!</p>
                <p className="t-title" style={{ marginTop: 6 }}>
                  {fmtNum(steps)}걸음
                </p>
                {isBest && (
                  <span className="chip" style={{ marginTop: 6, display: "inline-block" }}>
                    새 기록
                  </span>
                )}
                <p className="t-sub c-sub" style={{ marginTop: 6 }}>
                  {isBest ? "최고 기록이에요! 정말 잘하셨어요" : "다시 하면 더 멀리 갈 수 있어요"}
                </p>
                {rankLine && (
                  <p className="t-caption" style={{ marginTop: 6 }}>
                    {rankLine}
                  </p>
                )}
              </div>
            )}
          </div>
        )}
      </div>
      <button
        className="btn btn-primary"
        style={{ left: 24, top: 516, width: 345, height: 96, justifyContent: "center", fontSize: 28, borderRadius: 24 }}
        onPointerDown={(e) => {
          if (e.button !== 0) return;
          e.preventDefault();
          press();
        }}
        onClick={(e) => {
          if (e.detail === 0 && performance.now() - st.current.lastKey > 400) press();
        }}
      >
        {big}
      </button>
      {phase === "over" ? (
        <button className="abs center-x t-caption c-sub" style={{ top: 634, left: 100, right: 100, height: 34, textDecoration: "underline" }} onClick={() => f.go({ k: "rank" })}>
          랭킹 보기 →
        </button>
      ) : (
        <p className="abs center-x t-caption c-sub" style={{ top: 642 }}>
          게임 화면을 눌러도 뛰어요 · 500걸음마다 칭찬해요
        </p>
      )}
    </div>
  );
}

export function Rank({ f }: { f: FlowApi }) {
  const u = f.s.user;
  const [data, setData] = useState<{ top: RankEntry[]; me: { rank: number; entry: RankEntry } | null } | null>(null);
  const [err, setErr] = useState(false);
  const [n, setN] = useState(0);
  useEffect(() => {
    setErr(false);
    if (!useApiRank) {
      setData(localRanking(u ? u.nickname || "이름 없는 회원" : null));
      return;
    }
    setData(null);
    api.gameRanking(10).then(setData, () => setErr(true));
  }, [n, u]);
  return (
    <div className="content">
      <Title y={100}>랭킹</Title>
      <Sub y={146}>담고 달리기 · 걸음이 많은 순서예요</Sub>
      <div className="card" style={{ top: 196, maxHeight: 440, overflowY: "auto" }}>
        {err ? (
          <>
            <p className="t-answer">랭킹을 불러오지 못했어요</p>
            <p className="t-sub c-mute" style={{ marginTop: 6 }}>
              인터넷이 잘 되는지 보고 다시 눌러 주세요
            </p>
            <button className="btn btn-secondary" style={{ position: "relative", width: "100%", marginTop: 12 }} onClick={() => setN(n + 1)}>
              다시 불러오기
            </button>
          </>
        ) : !data ? (
          <p className="t-sub c-mute">랭킹을 불러오고 있어요…</p>
        ) : data.top.length === 0 ? (
          <p className="t-sub c-mute">아직 아무도 기록이 없어요. 첫 번째가 되어 보세요!</p>
        ) : (
          <>
            {data.top.map((r, i) => (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 12, padding: "9px 0", borderBottom: "1.5px solid var(--soft)" }}>
                <span className="t-tvalue" style={{ width: 30, color: i < 3 ? "var(--coral-deep)" : undefined }}>
                  {i + 1}
                </span>
                <span className="t-answer" style={{ flex: 1 }}>
                  {r.nickname}
                  {r.mine && <span className="chip" style={{ marginLeft: 6, fontSize: 12, height: 22, lineHeight: "22px", padding: "0 8px" }}>나</span>}
                </span>
                <span className="t-count">{fmtNum(r.steps)}걸음</span>
              </div>
            ))}
            {data.me && data.me.rank > 10 && (
              <>
                <p style={{ textAlign: "center" }}>⋯</p>
                <div style={{ display: "flex", gap: 12, padding: "9px 0" }}>
                  <span className="t-tvalue" style={{ width: 30 }}>
                    {data.me.rank}
                  </span>
                  <span className="t-answer" style={{ flex: 1 }}>
                    {data.me.entry.nickname} <span className="chip">나</span>
                  </span>
                  <span className="t-count">{fmtNum(data.me.entry.steps)}걸음</span>
                </div>
              </>
            )}
          </>
        )}
      </div>
      {!u ? (
        <div className="card" style={{ top: 652, display: "flex", alignItems: "center", gap: 10, padding: "14px 16px" }}>
          <span style={{ flex: 1 }}>
            <span className="t-answer" style={{ display: "block" }}>
              내 이름도 올려 볼까요?
            </span>
            <span className="t-caption c-mute">로그인하면 기록이 랭킹에 올라가요</span>
          </span>
          <button className="chip" onClick={() => f.go({ k: "login" })}>
            로그인
          </button>
        </div>
      ) : (
        <p className="abs center-x t-caption c-sub" style={{ top: 660, left: 24, right: 24 }}>
          {data?.me ? "" : "한 판 달리면 내 기록이 랭킹에 올라가요"}
          {!useApiRank ? " 지금은 이 기기에만 저장돼요 · 예시 기록이 섞여 있어요" : ""}
        </p>
      )}
      <button className="btn btn-primary" style={{ left: 24, top: 740, width: 345, justifyContent: "center" }} onClick={f.back}>
        다시 달리기
      </button>
    </div>
  );
}
