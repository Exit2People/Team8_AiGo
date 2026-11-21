"use client";

import type { FlowApi } from "./Flow";
import type { Step } from "@/lib/flow";
import { TextSizeButton } from "./TextSize";

/** 상단 막대 (11_FRONTEND_SPEC 2.3) */
export default function TopBar({ f, step, depth }: { f: FlowApi; step: Step; depth?: number }) {
  const { s } = f;
  const n = depth ?? s.stack.length;
  const c = s.cands[s.idx];
  const name = c?.place.name ?? "";
  const titles: Partial<Record<Step["k"], string>> = {
    guestbook: `${name} 방명록`,
    chat: `${name} 톡방`,
    my: "내 정보",
    blocked: "차단한 사람",
  };
  let title = titles[step.k];
  if (step.k === "myedit") title = `${{ nickname: "닉네임", age: "나이", home1: "사는 곳" }[step.field]} 고치기`;
  const showResult =
    !!s.origin &&
    ((step.k === "body" && !step.edit) || (step.k === "time" && !step.edit) || (step.k === "flex" && !step.edit) || step.k === "open");
  const hide = ["kwait", "cut", "stamped", "welcome"].includes(step.k);
  if (hide) return null;
  return (
    <>
      {n >= 2 && (
        <button
          className="topbar-back"
          onClick={() => (step.k === "chat" ? window.dispatchEvent(new CustomEvent("aigo:chat-leave-ask")) : f.back())}
          aria-label="뒤로"
        >
          {step.k === "guestbook" ? "‹ 티켓" : "‹ 뒤로"}
        </button>
      )}
      {step.k === "start" && (
        <div className="topbar-left">
          <button className="chip" onClick={() => f.go({ k: "my" })}>
            내 정보
          </button>
        </div>
      )}
      {title && (
        <div className="topbar-title" aria-hidden={step.k === "guestbook"}>
          {title}
        </div>
      )}
      <div className="topbar-right">
        {step.k === "start" && (
          <TextSizeButton />
        )}
        {showResult && (
          <button className="chip" style={{ background: "var(--white)", color: "var(--ink)" }} onClick={f.skipToResult}>
            결과 보기
          </button>
        )}
        {step.k === "chat" && (
          <button className="chip" onClick={() => window.dispatchEvent(new CustomEvent("aigo:chat-menu"))} aria-label="톡방 메뉴">
            ⋯
          </button>
        )}
        {step.k !== "start" && step.k !== "chat" && (
          <button className="chip" onClick={f.home}>
            처음으로
          </button>
        )}
      </div>
    </>
  );
}
