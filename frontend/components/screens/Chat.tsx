"use client";

import { useEffect, useRef, useState } from "react";
import type { FlowApi } from "../Flow";
import { ChevronIcon } from "../Icons";

type Menu = null | "main" | "people" | "report" | "block";

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
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const m = () => setMenu("main");
    const a = () => {
      setMenu(null);
      setAsk(true);
    };
    window.addEventListener("aigo:chat-menu", m);
    window.addEventListener("aigo:chat-leave-ask", a);
    return () => {
      window.removeEventListener("aigo:chat-menu", m);
      window.removeEventListener("aigo:chat-leave-ask", a);
    };
  }, []);

  const shown = chat.msgs.filter((m) => m.mine || m.kind === "system" || !chat.blocked.includes(m.nick));
  useEffect(() => {
    const el = listRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [shown.length]);

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

  const others = chat.members.filter((n) => n !== chat.myNick);

  return (
    <div className="content">
      <h1 className="sr-only" tabIndex={-1}>
        {c?.place.name} 톡방
      </h1>
      <p className="abs center-x t-caption" style={{ top: 96, color: "var(--ink)" }}>
        여기 온 {chat.count}명 · 오늘 밤 12시에 사라져요
      </p>
      {alert && (
        <div className="toast" role="alert" style={{ top: 120, background: "var(--coral-deep)" }}>
          {alert}
        </div>
      )}
      <div
        ref={listRef}
        className="abs scroll"
        style={{ left: 16, right: 16, top: 122, bottom: 172, background: "var(--white)", borderRadius: 24, padding: "14px 12px", boxShadow: "var(--sh-row)" }}
        aria-live="polite"
      >
        {shown.map((m) =>
          m.kind === "system" ? (
            <p key={m.id} className="t-item c-mute" style={{ textAlign: "center", margin: "10px 0" }}>
              {m.text}
            </p>
          ) : m.mine ? (
            <div key={m.id} style={{ display: "flex", justifyContent: "flex-end", alignItems: "flex-end", gap: 6, margin: "8px 0" }}>
              <span className="t-item c-mute">{m.at}</span>
              <span style={{ background: "var(--ink)", color: "#fff", borderRadius: "18px 18px 4px 18px", padding: "10px 14px", fontSize: 18, fontWeight: 700, maxWidth: 240, wordBreak: "break-word" }}>
                {m.text}
              </span>
            </div>
          ) : (
            <div key={m.id} style={{ display: "flex", gap: 8, margin: "8px 0", alignItems: "flex-start" }}>
              <span style={{ flex: "none", width: 36, height: 36, borderRadius: 18, background: "var(--soft)", textAlign: "center", lineHeight: "36px", fontWeight: 800 }}>{m.nick.slice(0, 1)}</span>
              <div>
                <p className="t-item c-mute">{m.nick}</p>
                <div style={{ display: "flex", alignItems: "flex-end", gap: 6, marginTop: 4 }}>
                  <span style={{ background: "var(--soft)", borderRadius: "4px 18px 18px 18px", padding: "10px 14px", fontSize: 18, fontWeight: 700, maxWidth: 220, wordBreak: "break-word" }}>{m.text}</span>
                  <span className="t-item c-mute">{m.at}</span>
                </div>
              </div>
            </div>
          ),
        )}
        {chat.lost && (
          <p className="t-item" style={{ textAlign: "center", color: "var(--coral-deep)", margin: "10px 0" }}>
            연결이 끊겼어요. 다시 이어지면 새 말이 보여요.
          </p>
        )}
      </div>
      <div className="abs" style={{ left: 16, right: 16, bottom: 104, display: "flex", gap: 8 }}>
        {["반가워요", "고마워요", "좋아요"].map((q) => (
          <button key={q} className="btn btn-white" style={{ position: "relative", flex: 1, height: 52, padding: 0, fontSize: 18 }} onClick={() => send(q)} disabled={sending}>
            {q}
          </button>
        ))}
      </div>
      {warn && (
        <p className="abs t-caption" style={{ left: 24, right: 24, bottom: 84, color: "var(--ink)" }}>
          {warn}
        </p>
      )}
      <form
        className="abs"
        style={{ left: 16, right: 16, bottom: 24, display: "flex", gap: 8 }}
        onSubmit={(e) => {
          e.preventDefault();
          send(text);
        }}
      >
        <input
          className="textbox"
          style={{ flex: 1, height: 56, padding: "0 14px", fontSize: 18 }}
          maxLength={200}
          value={text}
          placeholder="여기에 쓰기"
          onChange={(e) => setText(e.target.value)}
          aria-label="여기에 쓰기"
        />
        <button type="submit" className="btn btn-primary" style={{ position: "relative", width: 86, height: 56, justifyContent: "center", padding: 0 }} disabled={!text.trim() || sending} aria-label={sending ? "보내는 중" : "보내기"}>
          보내기
        </button>
      </form>

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
                    return (
                      <div key={n} className="row" style={{ marginTop: 8, minHeight: 52, boxShadow: "none", background: "var(--soft)" }}>
                        <span className="main t-answer">
                          {n}
                          {n === chat.myNick && menu === "people" ? " (나)" : ""}
                          {isBlocked && menu === "people" ? " · 차단함" : ""}
                        </span>
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
                            disabled={isBlocked}
                            style={{ opacity: isBlocked ? 0.4 : 1 }}
                            onClick={() => {
                              setMenu(null);
                              chat.block(n);
                            }}
                          >
                            {isBlocked ? "차단함" : "차단"}
                          </button>
                        )}
                      </div>
                    );
                  })}
                </div>
                <p className="t-caption c-mute pre" style={{ marginTop: 12 }}>
                  {menu === "block" ? "차단하면 그 사람의 말이 내 화면에서 보이지 않아요." : "신고하면 운영자가 대화를 살펴봐요.\n누가 신고했는지는 알리지 않아요."}
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
