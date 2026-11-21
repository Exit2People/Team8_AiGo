"use client";

import { useEffect, useState } from "react";
import * as api from "@/lib/api";

/** 사는 곳 고르기 판 (4.5) — 구 · 동 목록은 서버에서 받아요 */
export default function HomePicker({ onPick, onClose }: { onPick: (v: string) => void; onClose: () => void }) {
  const [gus, setGus] = useState<string[] | null>(null);
  const [gu, setGu] = useState<string | null>(null);
  const [dongs, setDongs] = useState<{ id: string; name: string }[] | null>(null);
  const [err, setErr] = useState(false);
  const [n, setN] = useState(0);

  useEffect(() => {
    let ok = true;
    setErr(false);
    (gu ? api.districtDongs(gu) : api.districts()).then(
      (r) => {
        if (!ok) return;
        if (gu) setDongs(r as { id: string; name: string }[]);
        else setGus(r as string[]);
      },
      () => ok && setErr(true),
    );
    return () => {
      ok = false;
    };
  }, [gu, n]);

  const list = gu ? dongs : gus;
  return (
    <div className="modal-bg" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" style={{ maxHeight: "86%", display: "flex", flexDirection: "column" }}>
        <h2 className="t-tile">{gu ? `${gu}의 동` : "어느 구에 사세요?"}</h2>
        <div className="scroll" style={{ marginTop: 14, flex: 1, minHeight: 0 }}>
          {err ? (
            <div>
              <p className="t-sub c-sub">목록을 받지 못했어요. 인터넷 연결을 확인해 주세요.</p>
              <button className="btn btn-secondary" onClick={() => setN(n + 1)}>
                다시 시도
              </button>
            </div>
          ) : !list ? (
            <p className="t-sub c-mute">불러오고 있어요…</p>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: gu ? "1fr 1fr" : "repeat(3, 1fr)", gap: 8 }}>
              {list.map((x) => {
                const name = typeof x === "string" ? x : x.name;
                return (
                  <button
                    key={name}
                    className="pick"
                    style={{ background: "var(--soft)", boxShadow: "none", fontSize: name.length > 6 ? 15 : 17 }}
                    onClick={() => {
                      if (!gu) {
                        setDongs(null);
                        setGu(name);
                      } else onPick(`${gu} ${name}`);
                    }}
                  >
                    {name}
                  </button>
                );
              })}
            </div>
          )}
        </div>
        {gu ? (
          <button className="btn btn-white" style={{ border: "2px solid var(--soft)" }} onClick={() => setGu(null)}>
            다른 구 고르기
          </button>
        ) : (
          <button className="btn btn-white" style={{ border: "2px solid var(--soft)" }} onClick={onClose}>
            닫기
          </button>
        )}
      </div>
    </div>
  );
}
