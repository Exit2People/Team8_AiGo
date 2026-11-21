"use client";

import Stage from "@/components/Stage";
import { CheckIcon } from "@/components/Icons";
import { Primary, Sheet, Caption } from "@/components/ui";

export default function Page() {
  return (
    <Stage poseKey="s1" coral="#FF5A4F">
      <div className="content">
        <div className="topbar-right"><span className="chip">로그인 · 회원가입</span></div>
        <h1 className="abs center-x t-display" style={{ top: 186 }}>AI GO</h1>
        <p className="abs center-x t-lead" style={{ top: 262 }}>오늘, 어디 가지?</p>
        <Sheet y={566} />
        {["글을 쓰지 않아도 돼요", "가입 없이도 쓸 수 있어요", "가는 길까지 알려 드려요"].map((t, i) => (
          <div key={t} className="abs" style={{ left: 24, top: 582 + i * 46, width: 345, height: 46, display: "flex", alignItems: "center", gap: 16, borderBottom: "1.5px solid var(--soft)" }}>
            <CheckIcon />
            <span className="t-body">{t}</span>
          </div>
        ))}
        <Primary y={732}>시작하기</Primary>
        <Caption y={806} dark>몇 번만 누르면 오늘 갈 곳이 정해져요</Caption>
      </div>
    </Stage>
  );
}
