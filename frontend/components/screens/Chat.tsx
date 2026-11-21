"use client";

import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { FlowApi } from "../Flow";
import { ChevronIcon } from "../Icons";
import Mic from "../Mic";
import { load, save } from "@/lib/device";
import type { ChatMessage } from "@/lib/types";

type Menu = null | "main" | "people" | "report" | "block";

/** 누르면 바로 보내는 말. 앞의 셋은 서버가 '빠른 말'로 알아봐요 */
const QUICK = ["반가워요", "고마워요", "좋아요", "날씨가 좋네요", "천천히 둘러보세요", "조심히 가세요"];
const MAX = 200;
const BIG_KEY = "aigo.chat.big";

/** 닉네임마다 늘 같은 동그라미 색 */
const FACE = [
  { bg: "var(--coral)", fg: "#fff" },
  { bg: "var(--ink)", fg: "#fff" },
  { bg: "var(--amber)", fg: "var(--ink)" },
  { bg: "#8a8580", fg: "#fff" },
  { bg: "var(--coral-deep)", fg: "#fff" },
];
function faceOf(nick: string) {
  let h = 0;
  for (const ch of nick) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return FACE[h % FACE.length];
}

function Face({ nick, size = 36 }: { nick: string; size?: number }) {
  const c = faceOf(nick);
  return (
    <span
      aria-hidden="true"
      style={{ display: "inline-block", flex: "none", width: size, height: size, borderRadius: size / 2, background: c.bg, color: c.fg, textAlign: "center", lineHeight: `${size}px`, fontWeight: 800, fontSize: size * 0.45 }}
    >
      {nick.slice(0, 1)}
    </span>
  );
}

/** 오늘 밤 12시까지 남은 시간 */
function leftText(now: number) {
  const end = new Date(now);
  end.setHours(24, 0, 0, 0);
  const min = Math.max(0, Math.round((end.getTime() - now) / 60_000));
  if (min >= 60) return `${Math.floor(min / 60)}시간 ${min % 60 ? `${min % 60}분 ` : ""}뒤에 사라져요`;
  return min > 0 ? `${min}분 뒤에 사라져요` : "곧 사라져요";
}

/** 말 묶음: 같은 사람이 잇달아 쓴 말은 이름 · 동그라미를 한 번만, 시각은 마지막에만 */
type Row = { m: ChatMessage; first: boolean; last: boolean };
function group(list: ChatMessage[]): Row[] {
  return list.map((m, i) => {
    const prev = list[i - 1];
    const next = list[i + 1];
    const same = (a?: ChatMessage) => !!a && a.kind !== "system" && m.kind !== "system" && a.nick === m.nick && a.mine === m.mine;
    return { m, first: !same(prev), last: !same(next) || next?.at !== m.at };
  });
}

/** 톡방 (9.3) */
export default function Chat({ f }: { f: FlowApi }) {
  const { chat, s } = f;
  const c = s.cands[s.idx];
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [alert, setAlert] = useState<string | null>(null);
  const [warn, setWarn] = useState<string | null>(null);
  const [menu, setMenu] = useState<Menu>(null);
  const [ask, setAsk] = useState(false);
  const [who, setWho] = useState<string | null>(null); // 이름을 눌러 연 사람
  const [big, setBig] = useState(() => load<boolean>(BIG_KEY, false)); // 톡방은 화면 흐름 안에서만 그려져서(서버에서 그리지 않아요) 바로 읽어도 돼요
  const [unread, setUnread] = useState(0);
  const [now, setNow] = useState(() => Date.now());
  const listRef = useRef<HTMLDivElement>(null);
  const atBottom = useRef(true);
  const seen = useRef(0);

  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 60_000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    const m = () => setMenu("main");
    const a = () => {
      setMenu(null);
      setWho(null);
      setAsk(true);
    };
    window.addEventListener("aigo:chat-menu", m);
    window.addEventListener("aigo:chat-leave-ask", a);
    return () => {
      window.removeEventListener("aigo:chat-menu", m);
      window.removeEventListener("aigo:chat-leave-ask", a);
    };
  }, []);

  const shown = useMemo(() => chat.msgs.filter((m) => m.mine || m.kind === "system" || !chat.blocked.includes(m.nick)), [chat.msgs, chat.blocked]);
  const rows = useMemo(() => group(shown), [shown]);
  const talked = shown.some((m) => m.kind !== "system");

  // 새 말이 오면: 맨 아래를 보고 있었거나 내가 쓴 말이면 내려가고, 위를 읽는 중이면 '새 말' 알림만 띄워요
  useLayoutEffect(() => {
    const el = listRef.current;
    if (!el) return;
    const added = shown.slice(seen.current);
    seen.current = shown.length;
    if (!added.length) return;
    if (atBottom.current || added.some((m) => m.mine)) {
      el.scrollTop = el.scrollHeight;
      setUnread(0);
    } else setUnread((n) => n + added.filter((m) => m.kind !== "system").length);
  }, [shown]);

  function onScroll() {
    const el = listRef.current;
    if (!el) return;
    atBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 48;
    if (atBottom.current) setUnread(0);
  }
  function toBottom() {
    const el = listRef.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: f.still ? "auto" : "smooth" });
    setUnread(0);
  }

  async function send(t: string) {
    const v = t.trim();
    if (!v || sending) return;
    setSending(true);
    setWarn(null);
    const r = await chat.send(v);
    setSending(false);
    if (r === true) {
      if (t === text) setText("");
      return;
    }
    if (r.alert) {
      setAlert(r.alert);
      setTimeout(() => setAlert(null), 2600);
    } else if (r.warn) setWarn(r.warn);
  }

  async function leave() {
    setAsk(false);
    await chat.leave();
    const member = !!s.user;
    f.home();
    if (member) {
      setTimeout(() => {
        f.go({ k: "mine" });
        setTimeout(() => f.note("톡방에서 나왔어요. 오늘 다녀온 곳에 우표를 붙여 보세요."), 60);
      }, 30);
    } else setTimeout(() => f.note("톡방에서 나왔어요."), 30);
  }

  function toggleBig() {
    const v = !big;
    setBig(v);
    save(BIG_KEY, v);
  }

  const others = chat.members.filter((n) => n !== chat.myNick);
  const fs = big ? 22 : 18; // 말풍선 글씨 크기
  const left = MAX - text.length;

  return (
    <div className="content">
      <h1 className="sr-only" tabIndex={-1}>
        {c?.place.name} 톡방
      </h1>

      {/* 위: 함께 있는 사람 · 남은 시간 · 글씨 크기 */}
      <div className="abs" style={{ left: 16, right: 16, top: 92, height: 44, display: "flex", alignItems: "center", gap: 10 }}>
        <button
          style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0, flex: 1, textAlign: "left" }}
          onClick={() => setMenu("people")}
          aria-label={`함께 있는 사람 ${chat.count}명 보기`}
        >
          <span style={{ display: "flex", flex: "none" }}>
            {chat.members.slice(0, 4).map((n, i) => (
              <span key={n} style={{ marginLeft: i ? -10 : 0, borderRadius: 18, boxShadow: "0 0 0 2.5px #fff" }}>
                <Face nick={n} size={30} />
              </span>
            ))}
          </span>
          <span style={{ minWidth: 0 }}>
            <span className="t-answer" style={{ display: "block", fontSize: 15 }}>
              여기 온 {chat.count}명
            </span>
            <span className="t-item" style={{ display: "block", marginTop: 2, color: "var(--sub)" }}>
              {leftText(now)}
            </span>
          </span>
        </button>
        <button className="chip chip-soft" style={{ flex: "none", height: 34, fontSize: 14 }} onClick={toggleBig} aria-pressed={big}>
          {big ? "글씨 보통" : "글씨 크게"}
        </button>
      </div>

      {alert && (
        <div className="toast" role="alert" style={{ top: 140, background: "var(--coral-deep)" }}>
          {alert}
        </div>
      )}

      {/* 대화 */}
      <div
        ref={listRef}
        onScroll={onScroll}
        className="abs scroll"
        style={{ left: 12, right: 12, top: 142, bottom: 190, padding: "6px 4px 10px" }}
        aria-live="polite"
        aria-label="대화"
      >
        <p style={{ textAlign: "center", margin: "0 0 10px" }}>
          <span className="t-item" style={{ display: "inline-block", padding: "5px 12px", borderRadius: 14, background: "rgba(255,255,255,.72)", color: "var(--sub)" }}>
            오늘 · 전화번호 · 주소 · 돈 이야기는 하지 않아요
          </span>
        </p>
        {!talked && (
          <div style={{ textAlign: "center", padding: "18px 8px", margin: "6px 0 10px", borderRadius: 18, background: "rgba(255,255,255,.8)" }}>
            <p className="t-answer" style={{ fontSize: 18 }}>
              먼저 인사해 보세요
            </p>
            <p className="t-item c-mute" style={{ marginTop: 6 }}>
              아래 빠른 말을 누르면 바로 보내져요
            </p>
          </div>
        )}
        {rows.map(({ m, first, last }) =>
          m.kind === "system" ? (
            <p key={m.id} style={{ textAlign: "center", margin: "10px 0" }}>
              <span className="t-item" style={{ display: "inline-block", padding: "4px 12px", borderRadius: 12, background: "rgba(255,255,255,.72)", color: "var(--sub)" }}>
                {m.text}
              </span>
            </p>
          ) : m.mine ? (
            <div key={m.id} style={{ display: "flex", justifyContent: "flex-end", alignItems: "flex-end", gap: 6, marginTop: first ? 12 : 4 }}>
              {last && <span className="t-item c-sub">{m.at}</span>}
              <span
                style={{
                  background: "var(--ink)",
                  color: "#fff",
                  borderRadius: last ? "18px 18px 4px 18px" : 18,
                  padding: "10px 14px",
                  fontSize: fs,
                  fontWeight: 700,
                  lineHeight: 1.35,
                  maxWidth: 240,
                  wordBreak: "break-word",
                }}
              >
                {m.text}
              </span>
            </div>
          ) : (
            <div key={m.id} style={{ display: "flex", gap: 8, marginTop: first ? 12 : 4, alignItems: "flex-start" }}>
              {first ? (
                <button onClick={() => setWho(m.nick)} aria-label={`${m.nick} 님 메뉴`} style={{ flex: "none", borderRadius: 18 }}>
                  <Face nick={m.nick} />
                </button>
              ) : (
                <span style={{ flex: "none", width: 36 }} />
              )}
              <div style={{ minWidth: 0 }}>
                {first && (
                  <button className="t-item" style={{ color: "var(--ink)", fontWeight: 800 }} onClick={() => setWho(m.nick)}>
                    {m.nick}
                  </button>
                )}
                <div style={{ display: "flex", alignItems: "flex-end", gap: 6, marginTop: first ? 4 : 0 }}>
                  <span
                    style={{
                      background: m.kind === "quick" ? "color-mix(in srgb, var(--amber) 28%, #fff)" : "#fff",
                      boxShadow: "0 2px 6px rgba(89,20,15,.08)",
                      borderRadius: first ? "4px 18px 18px 18px" : 18,
                      padding: "10px 14px",
                      fontSize: fs,
                      fontWeight: 700,
                      lineHeight: 1.35,
                      maxWidth: 220,
                      wordBreak: "break-word",
                    }}
                  >
                    {m.text}
                  </span>
                  {last && <span className="t-item c-sub">{m.at}</span>}
                </div>
              </div>
            </div>
          ),
        )}
        {chat.lost && (
          <p className="t-item" role="status" style={{ textAlign: "center", color: "var(--coral-deep)", margin: "10px 0" }}>
            연결이 끊겼어요. 다시 이어지면 새 말이 보여요.
          </p>
        )}
      </div>

      {unread > 0 && (
        <button
          className="abs chip"
          style={{ left: "50%", transform: "translateX(-50%)", bottom: 200, height: 40, padding: "0 16px", fontSize: 16, boxShadow: "var(--sh-row)", zIndex: 2 }}
          onClick={toBottom}
        >
          새 말 {unread}개 ↓
        </button>
      )}

      {/* 빠른 말: 옆으로 밀어서 더 볼 수 있어요 */}
      <div className="abs scroll" style={{ left: 0, right: 0, bottom: 112, height: 60, display: "flex", gap: 8, padding: "4px 16px", overflowX: "auto", overflowY: "hidden" }} aria-label="빠른 말">
        {QUICK.map((q) => (
          <button
            key={q}
            className="btn btn-white"
            style={{ position: "relative", flex: "none", height: 52, padding: "0 18px", fontSize: 17, boxShadow: "var(--sh-row)" }}
            onClick={() => send(q)}
            disabled={sending}
          >
            {q}
          </button>
        ))}
      </div>

      {(warn || left <= 30) && (
        <p className="abs t-caption" role={warn ? "alert" : undefined} style={{ left: 24, right: 24, bottom: 88, color: warn ? "var(--coral-deep)" : "var(--ink)" }}>
          {warn ?? `${left}자 더 쓸 수 있어요`}
        </p>
      )}

      {/* 쓰기 · 말로 쓰기 · 보내기 */}
      <form
        className="abs"
        style={{ left: 16, right: 16, bottom: 24, display: "flex", gap: 8, alignItems: "center" }}
        onSubmit={(e) => {
          e.preventDefault();
          send(text);
        }}
      >
        <div style={{ position: "relative", flex: 1, minWidth: 0 }}>
          <input
            className="textbox"
            style={{ width: "100%", height: 56, padding: "0 58px 0 14px", fontSize: 18 }}
            maxLength={MAX}
            value={text}
            placeholder="여기에 쓰기"
            onChange={(e) => {
              setText(e.target.value);
              if (warn) setWarn(null);
            }}
            aria-label="여기에 쓰기"
            enterKeyHint="send"
          />
          <div style={{ position: "absolute", right: 4, top: 4 }}>
            <Mic value={text} max={MAX} up onText={setText} />
          </div>
        </div>
        <button
          type="submit"
          className="btn btn-primary"
          style={{ position: "relative", width: 86, height: 56, justifyContent: "center", padding: 0 }}
          disabled={!text.trim() || sending}
          aria-label={sending ? "보내는 중" : "보내기"}
        >
          {sending ? "…" : "보내기"}
        </button>
      </form>

      {/* 이름을 눌렀을 때: 그 사람 신고 · 차단 */}
      {who && (
        <div className="modal-bg" onClick={() => setWho(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-label={`${who} 님`}>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <Face nick={who} size={48} />
              <h2 className="t-tile">{who} 님</h2>
            </div>
            {chat.blocked.includes(who) ? (
              <button
                className="btn btn-secondary"
                style={{ marginTop: 18 }}
                onClick={() => {
                  chat.unblock(who);
                  setWho(null);
                }}
              >
                차단 풀기
              </button>
            ) : (
              <button
                className="btn btn-secondary"
                style={{ marginTop: 18 }}
                onClick={() => {
                  chat.block(who);
                  setWho(null);
                }}
              >
                차단하기 · 이 사람 말을 안 볼래요
              </button>
            )}
            <button
              className="btn btn-secondary"
              style={{ color: "var(--coral-deep)" }}
              onClick={() => {
                chat.report(who);
                setWho(null);
              }}
            >
              신고하기
            </button>
            <p className="t-caption c-mute pre" style={{ marginTop: 12 }}>
              {"신고하면 운영자가 대화를 살펴봐요.\n누가 신고했는지는 알리지 않아요."}
            </p>
            <button className="btn btn-white" onClick={() => setWho(null)}>
              닫기
            </button>
          </div>
        </div>
      )}

      {menu && (
        <div className="modal-bg" onClick={() => setMenu(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-label="톡방 메뉴">
            {menu === "main" ? (
              <>
                <h2 className="t-tile">톡방 메뉴</h2>
                {[
                  [`함께 있는 사람 ${chat.members.length}명`, () => setMenu("people")],
                  ["신고하기", () => setMenu("report")],
                  ["차단하기", () => setMenu("block")],
                ].map(([t, fn]) => (
                  <button key={t as string} className="row" style={{ marginTop: 10, minHeight: 56, justifyContent: "space-between" }} onClick={fn as () => void}>
                    <span className="t-answer">{t as string}</span>
                    <ChevronIcon />
                  </button>
                ))}
                <button
                  className="btn btn-secondary"
                  style={{ color: "var(--coral-deep)" }}
                  onClick={() => {
                    setMenu(null);
                    setAsk(true);
                  }}
                >
                  톡방 나가기
                </button>
                <p className="t-caption c-mute pre" style={{ marginTop: 12 }}>
                  {"신고하면 운영자가 대화를 살펴봐요.\n누가 신고했는지는 알리지 않아요."}
                </p>
                <button className="btn btn-white" onClick={() => setMenu(null)}>
                  닫기
                </button>
              </>
            ) : (
              <>
                <h2 className="t-tile">{menu === "people" ? "함께 있는 사람" : menu === "report" ? "누구를 신고할까요?" : "누구를 차단할까요?"}</h2>
                <div className="scroll" style={{ maxHeight: 300, marginTop: 6 }}>
                  {(menu === "people" ? chat.members : others).length === 0 && (
                    <p className="t-sub c-mute" style={{ marginTop: 12 }}>
                      아직 다른 사람이 없어요
                    </p>
                  )}
                  {(menu === "people" ? chat.members : others).map((n) => {
                    const isBlocked = chat.blocked.includes(n);
                    const me = n === chat.myNick;
                    return (
                      <div key={n} className="row" style={{ marginTop: 8, minHeight: 52, boxShadow: "none", background: "var(--soft)", gap: 10 }}>
                        <Face nick={n} size={32} />
                        <span className="main t-answer">
                          {n}
                          {me && menu === "people" ? " (나)" : ""}
                          {isBlocked && menu === "people" ? " · 차단함" : ""}
                        </span>
                        {menu === "people" && !me && (
                          <button className="chip chip-soft" style={{ background: "#fff" }} onClick={() => { setMenu(null); setWho(n); }}>
                            더 보기
                          </button>
                        )}
                        {menu === "report" && (
                          <button
                            className="chip"
                            onClick={() => {
                              setMenu(null);
                              chat.report(n);
                            }}
                          >
                            신고
                          </button>
                        )}
                        {menu === "block" && (
                          <button
                            className="chip"
                            onClick={() => {
                              setMenu(null);
                              if (isBlocked) chat.unblock(n);
                              else chat.block(n);
                            }}
                          >
                            {isBlocked ? "차단 풀기" : "차단"}
                          </button>
                        )}
                      </div>
                    );
                  })}
                </div>
                <p className="t-caption c-mute pre" style={{ marginTop: 12 }}>
                  {menu === "block" ? "차단하면 그 사람의 말이 내 화면에서 보이지 않아요." : menu === "people" ? "이름을 누르면 신고 · 차단할 수 있어요." : "신고하면 운영자가 대화를 살펴봐요.\n누가 신고했는지는 알리지 않아요."}
                </p>
                <button className="btn btn-white" onClick={() => setMenu("main")}>
                  뒤로
                </button>
              </>
            )}
          </div>
        </div>
      )}

      {ask && (
        <div className="modal-bg" onClick={() => setAsk(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
            <h2 className="t-title pre">{"톡방에서 정말\n나가시겠어요?"}</h2>
            <p className="t-sub c-mute pre" style={{ marginTop: 10 }}>
              {`나가면 함께 있는 분들께\n‘${chat.myNick} 님이 나갔어요’가 보여요`}
            </p>
            <button className="btn btn-secondary" style={{ marginTop: 18 }} onClick={() => setAsk(false)}>
              그만둘래요
            </button>
            <button className="btn btn-primary" style={{ justifyContent: "center" }} onClick={leave}>
              나갈래요
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
