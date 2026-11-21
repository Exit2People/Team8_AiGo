"use client";

import type { FlowApi } from "../Flow";
import { CheckIcon, KakaoIcon } from "../Icons";
import { Caption, Secondary, Sheet, Sub, Title } from "../ui";
import { KAKAO_START, isMock } from "@/lib/api";

/** 로그인 · 회원가입 (4.1 login) */
export default function Login({ f }: { f: FlowApi }) {
  const guest = () => {
    if (f.backTo.current) {
      f.backTo.current = null;
      f.back();
    } else f.go({ k: "origin" });
  };
  return (
    <div className="content">
      <Title y={112}>{"카카오로\n시작해요"}</Title>
      <Sub y={196}>{"처음이면 가입,\n다음부터는 로그인이에요"}</Sub>
      <Sheet y={452} />
      {["다녀온 곳마다 우표를 모아요", "휴대폰을 바꿔도 이어서 봐요"].map((t, i) => (
        <div
          key={t}
          className="abs"
          style={{ left: 24, top: 476 + i * 46, width: 345, height: 46, display: "flex", alignItems: "center", gap: 16, borderBottom: "1.5px solid var(--soft)" }}
        >
          <CheckIcon />
          <span className="t-body">{t}</span>
        </div>
      ))}
      <button
        className="btn btn-kakao"
        style={{ left: 24, top: 586, width: 345, borderRadius: 12, justifyContent: "center", gap: 10 }}
        onClick={() => {
          if (isMock()) {
            // 가짜 응답: 카카오 대신 처음 가입처럼 돌아와요
            try {
              sessionStorage.setItem("aigo.mock.signup", "1");
            } catch {
              /* */
            }
            location.href = "/?signup=1";
            return;
          }
          location.href = KAKAO_START;
        }}
      >
        <KakaoIcon />
        <span>카카오로 시작하기</span>
      </button>
      <Secondary y={658} onClick={() => f.go({ k: "elogin" })}>
        이메일로 시작하기
      </Secondary>
      <Caption y={744} onClick={guest} dark>
        로그인 없이 쓸게요
      </Caption>
      <Caption y={800} dark>
        가입하면 이용약관과 개인정보 처리방침에 동의하게 돼요
      </Caption>
    </div>
  );
}
