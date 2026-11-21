"use client";

import type { FlowApi } from "../Flow";
import { Primary, Secondary, Sheet, Sub, Title } from "../ui";

/** 실패 화면 3가지 (4.4 notFound) */
export default function NotFound({ f, why }: { f: FlowApi; why: "offline" | "timeout" | "none" }) {
  const title = why === "offline" ? "인터넷이\n끊겼어요" : "갈 곳을\n찾지 못했어요";
  const sub = why === "offline" ? "연결을 확인하고\n다시 찾아 주세요" : why === "timeout" ? "찾는 데 시간이\n오래 걸렸어요" : "조건에 맞고 지금 문을 연 곳이\n없어요";
  return (
    <div className="content">
      <Sheet y={852} />
      <Title y={540} align="center" size="m">
        {title}
      </Title>
      <Sub y={632} align="center">
        {sub}
      </Sub>
      <Primary y={694} onClick={() => f.search("stay")}>
        다시 찾기
      </Primary>
      <Secondary y={764} white onClick={f.home}>
        처음으로
      </Secondary>
    </div>
  );
}
