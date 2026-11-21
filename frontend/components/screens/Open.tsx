"use client";

import { useState } from "react";
import type { FlowApi } from "../Flow";
import { Dots, Primary, Progress, Secondary, Sheet, Sub, Title } from "../ui";
import Mic from "../Mic";

/** 질문 0 (4.3 open) */
export default function Open({ f }: { f: FlowApi }) {
  const [text, setText] = useState(f.s.openText);
  const listening = !!f.s.busy?.startsWith("질문 0");
  if (listening) {
    return (
      <div className="content" role="status">
        <Progress on={1} text="첫 질문" right />
        <Sheet y={852} />
        <Title y={572} align="center" size="m">{"말씀을\n듣고 있어요"}</Title>
        <Sub y={664} align="center">{"들은 것만 골라서\n남은 것만 여쭤볼게요"}</Sub>
        <Dots y={728} />
      </div>
    );
  }
  return (
    <div className="content">
      <Progress on={1} text="첫 질문" />
      <Title y={112}>{"오늘 어떤\n하루 보내고\n싶으세요?"}</Title>
      <Sub y={226}>{"편하게 말씀해 주세요.\n안 써도 괜찮아요"}</Sub>
      <Sheet y={420} />
      <p className="abs t-label c-deep" style={{ left: 24, top: 448 }}>
        하고 싶은 것 · 가고 싶은 곳 · 같이 갈 사람
      </p>
      <div className="abs" style={{ left: 24, top: 470, width: 345 }}>
        <textarea
          className="textbox"
          rows={2}
          maxLength={200}
          value={text}
          placeholder="예) 손주랑 한강 가고 싶어요"
          aria-label="하고 싶은 것 · 가고 싶은 곳 · 같이 갈 사람"
          onChange={(e) => {
            setText(e.target.value);
            f.set({ openText: e.target.value });
          }}
          style={{ paddingRight: 64 }}
        />
        <div style={{ position: "absolute", right: 10, top: 14 }}>
          <Mic
            value={text}
            pause={2500}
            max={200}
            onText={(v) => {
              setText(v);
              f.set({ openText: v });
            }}
          />
        </div>
      </div>
      <Primary y={636} disabled={!text.trim()} onClick={() => f.submitOpen(text)}>
        이렇게 말할게요
      </Primary>
      <Secondary y={708} onClick={() => f.submitOpen(null)}>
        잘 모르겠어요 · 하나씩 물어봐 주세요
      </Secondary>
    </div>
  );
}
