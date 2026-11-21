"use client";

import { Dots, Sub, Title, Sheet } from "../ui";
import { Printer } from "../Icons";

/** 기다림 화면 (4.0) */
export default function Busy({ text }: { text: string }) {
  if (text.startsWith("가까운")) {
    return (
      <div className="content" role="status">
        <Sheet y={852} />
        <Title y={520} align="center" size="m">{"가까운 동을\n찾고 있어요"}</Title>
        <Sub y={612} align="center">위치는 동을 찾는 데만 써요</Sub>
        <Dots y={660} />
      </div>
    );
  }
  const slow = text.startsWith("조금만");
  return (
    <div className="content" role="status">
      <Title y={372} align="center" size="m">{"갈 곳을\n찾고 있어요"}</Title>
      <Sub y={456} align="center">{"날씨, 문 여는 시간,\n가는 길까지 살펴봐요"}</Sub>
      <Dots y={520} />
      <div className="card" style={{ top: 556, opacity: slow ? 1 : 0, transition: "opacity .5s" }} aria-hidden={!slow}>
        <p className="t-lead">조금만 더 기다려 주세요</p>
        <p className="t-caption c-mute" style={{ marginTop: 8 }}>
          길을 꼼꼼히 살펴보느라 조금 걸려요
        </p>
      </div>
      <div className="abs" style={{ left: 24, top: 672, filter: "drop-shadow(0 14px 26px rgba(89,20,15,.45))" }}>
        <Printer />
      </div>
    </div>
  );
}
