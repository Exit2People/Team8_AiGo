"use client";

import { useEffect, useRef, useState } from "react";
import { MicIcon } from "./Icons";

/* 말로 쓰기 (11_FRONTEND_SPEC 14절) — 브라우저 음성 인식, 키 · 서버 없음 */

type Rec = {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  maxAlternatives: number;
  start(): void;
  stop(): void;
  abort(): void;
  onresult: ((e: { resultIndex: number; results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }> }) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
};

function getCtor(): (new () => Rec) | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as { SpeechRecognition?: new () => Rec; webkitSpeechRecognition?: new () => Rec };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

const isIOS = () =>
  typeof navigator !== "undefined" &&
  !/Android/i.test(navigator.userAgent) &&
  (/iPhone|iPod|iPad/.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1));

let shared: Rec | null = null;
function recognizer(fresh = false): Rec | null {
  const C = getCtor();
  if (!C) return null;
  if (fresh && shared && !isIOS()) {
    try {
      shared.abort();
    } catch {
      /* */
    }
    shared = null;
  }
  if (!shared || fresh) {
    shared = new C();
    shared.lang = "ko-KR";
    shared.interimResults = true;
    shared.continuous = false;
    shared.maxAlternatives = 1;
  }
  return shared;
}

const ERR: Record<string, string> = {
  "not-allowed": "마이크를 쓸 수 있게 허락해 주세요",
  "service-not-allowed": "마이크를 쓸 수 있게 허락해 주세요",
  "no-speech": "말씀이 들리지 않았어요. 다시 눌러 주세요",
  "audio-capture": "마이크를 찾지 못했어요",
  network: "인터넷 연결을 확인해 주세요",
};

export const cleanName = (s: string) => s.replace(/[.,!?。]/g, "").trim();
export const cleanNick = (s: string) => s.replace(/[^가-힣ㄱ-ㅎㅏ-ㅣa-zA-Z0-9]/g, "");

export default function Mic({
  value,
  onText,
  replace,
  pause = 2000,
  max = 200,
  clean,
}: {
  value: string;
  onText: (v: string) => void;
  replace?: boolean;
  pause?: number;
  max?: number;
  clean?: (s: string) => string;
}) {
  const [ok, setOk] = useState(false);
  const [on, setOn] = useState(false);
  const [heard, setHeard] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const base = useRef("");
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  const ended = useRef(true);

  useEffect(() => setOk(!!getCtor()), []);
  useEffect(() => () => timers.current.forEach(clearTimeout), []);

  function clear() {
    timers.current.forEach(clearTimeout);
    timers.current = [];
  }

  function finish(msg?: string) {
    if (ended.current) return;
    ended.current = true;
    clear();
    setOn(false);
    if (msg) {
      setErr(msg);
      setTimeout(() => setErr(null), 4000);
    }
    const r = shared;
    if (r) {
      r.onresult = null;
      r.onerror = null;
      r.onend = null;
      if (!isIOS()) {
        try {
          r.stop();
        } catch {
          /* */
        }
      }
    }
  }

  function put(said: string) {
    let v = replace ? said : base.current ? `${base.current} ${said}` : said;
    if (clean) v = clean(v);
    onText(v.slice(0, max));
  }

  function start() {
    const r = recognizer();
    if (!r) return;
    base.current = value.trim();
    ended.current = false;
    setHeard(false);
    setErr(null);
    setOn(true);
    let gotAny = false;
    const armPause = () => {
      clear();
      timers.current.push(setTimeout(() => finish(), pause));
      timers.current.push(setTimeout(() => finish(), 20000));
    };
    timers.current.push(
      setTimeout(() => {
        if (!gotAny) {
          finish("말씀이 들리지 않았어요. 다시 눌러 주세요");
          recognizer(true);
        }
      }, 7000),
    );
    timers.current.push(setTimeout(() => finish(), 20000));
    r.onresult = (e) => {
      let said = "";
      for (let i = 0; i < e.results.length; i++) said += e.results[i][0].transcript;
      said = said.trim();
      if (!said) return;
      gotAny = true;
      setHeard(true);
      put(said);
      armPause();
    };
    r.onerror = (e) => {
      if (e.error === "aborted") return;
      if (e.error === "no-speech" && gotAny) return;
      finish(ERR[e.error] ?? "잘 듣지 못했어요. 다시 눌러 주세요");
    };
    r.onend = () => finish();
    const go = () => {
      try {
        r.start();
      } catch {
        /* 이미 듣는 중이면 이어 붙어요 */
      }
    };
    const ae = document.activeElement as HTMLElement | null;
    if (ae && (ae.tagName === "INPUT" || ae.tagName === "TEXTAREA")) {
      ae.blur();
      setTimeout(go, 400);
    } else go();
  }

  if (!ok) return null;
  return (
    <div style={{ position: "relative" }}>
      <button
        type="button"
        onClick={() => (on ? finish() : start())}
        aria-label={on ? "듣고 있어요. 누르면 멈춰요" : "말로 쓰기"}
        style={{
          width: 48,
          height: 48,
          borderRadius: 24,
          background: on ? "var(--coral)" : "var(--soft)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <MicIcon on={on} />
      </button>
      {(on || err) && (
        <div
          role="status"
          className="t-caption"
          style={{
            position: "absolute",
            right: 0,
            top: 54,
            whiteSpace: "nowrap",
            background: "var(--ink)",
            color: "var(--white)",
            borderRadius: 12,
            padding: "8px 12px",
            zIndex: 5,
          }}
        >
          {err ?? (heard ? "다 하셨으면 눌러 주세요" : "듣고 있어요 · 말씀하세요")}
        </div>
      )}
    </div>
  );
}
