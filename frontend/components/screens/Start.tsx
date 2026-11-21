"use client";

import type { FlowApi } from "../Flow";
import { CheckIcon } from "../Icons";
import { Caption, Primary, Sheet } from "../ui";
import { readStamps, readVisits } from "@/lib/device";
import { photoIll } from "@/lib/illust";
import { useEffect, useState } from "react";
import type { Visit } from "@/lib/device";

export default function Start({ f }: { f: FlowApi }) {
  const { s } = f;
  const user = s.user;
  const [visits, setVisits] = useState<Visit[]>([]);
  const [stampN, setStampN] = useState(0);
  useEffect(() => {
    setVisits(readVisits());
    setStampN(Object.keys(readStamps()).length);
  }, [user]);

  return (
    <div className="content">
      <h1 className="abs center-x t-display" style={{ top: 186 }} tabIndex={-1}>
        AI GO
      </h1>
      <p className="abs center-x t-lead" style={{ top: 262 }}>
        오늘, 어디 가지?
      </p>
      <Sheet y={566} />
      {user ? (
        <button className="abs" style={{ left: 24, top: 586, width: 345, textAlign: "left" }} onClick={() => f.go({ k: "mine" })}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span className="t-answer">다녀온 곳</span>
            <span className="t-caption c-mute">
              우표 {stampN}장 · 모두 보기 ›
            </span>
          </div>
          {visits.length ? (
            <div style={{ display: "flex", gap: 10, marginTop: 12 }}>
              {visits.slice(0, 3).map((v) => (
                <div key={v.id + v.date} style={{ width: 108 }}>
                  <img src={photoIll(v.kind, v.name)} alt="" width={108} height={70} style={{ objectFit: "cover", borderRadius: 12, display: "block", background: "var(--soft)" }} />
                  <p className="t-item" style={{ marginTop: 6, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {v.name}
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <p className="t-sub c-mute" style={{ marginTop: 10 }}>
              아직 다녀온 곳이 없어요. 오늘 첫 나들이를 찾아봐요
            </p>
          )}
        </button>
      ) : (
        ["글을 쓰지 않아도 돼요", "가입 없이도 쓸 수 있어요", "가는 길까지 알려 드려요"].map((t, i) => (
          <div
            key={t}
            className="abs"
            style={{ left: 24, top: 582 + i * 46, width: 345, height: 46, display: "flex", alignItems: "center", gap: 16, borderBottom: "1.5px solid var(--soft)" }}
          >
            <CheckIcon />
            <span className="t-body">{t}</span>
          </div>
        ))
      )}
      <Primary y={732} onClick={() => f.go(user ? { k: "origin" } : { k: "login" })}>
        시작하기
      </Primary>
      <Caption y={806} dark>
        {user ? (user.provider === "kakao" ? "카카오로 로그인했어요" : "이메일로 로그인했어요") : "몇 번만 누르면 오늘 갈 곳이 정해져요"}
      </Caption>
    </div>
  );
}
