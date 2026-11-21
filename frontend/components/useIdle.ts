"use client";

import { useEffect, useState } from "react";
import { hasPose } from "@/lib/poses";
import { later } from "@/lib/pause";

/** 담고 제자리 움직임 (11_FRONTEND_SPEC 15절, 4-animation 4-2) */
const REST: Record<string, number> = { s1: 4200, home: 4200, loc: 3600, near: 3800, gu: 3400, st: 3500, body: 3800, time: 4000, q1: 3400, fb: 3600, last: 3800, mine: 3800 };
export const WAG = new Set(["find", "wait", "kwait", "ask", "ask2", "fill", "cut"]);

export function useIdle(base: string, enabled: boolean): { key: string; blink: boolean } {
  const [key, setKey] = useState(base);
  const [blink, setBlink] = useState(false);
  const can = enabled && hasPose(base + "i") && hasPose(base + "t");

  useEffect(() => {
    setKey(base);
    setBlink(false);
    if (!can) return;
    let alive = true;
    const ts: (() => void)[] = [];
    const at = (ms: number, fn: () => void) => ts.push(later(ms, () => alive && fn())); // 배지 축하 중에는 멈춰요
    const rest = REST[base] ?? 3800;
    function loop() {
      const k = Math.random() < 0.2 ? 1.8 + Math.random() * 1.4 : 0.6 + Math.random() * 1.3;
      at(rest * k, () => {
        const act = Math.floor(Math.random() * 4);
        let t = 0;
        if (act === 0) {
          setKey(base + "i");
          t = 900;
        } else if (act === 1) {
          setKey(base + "t");
          t = 900;
        } else if (act === 2) {
          setKey(base + "i");
          at(650, () => setKey(base + "t"));
          t = 1500;
        } else {
          setBlink(true);
          at(120, () => setBlink(false));
          at(300, () => setBlink(true));
          at(420, () => setBlink(false));
          t = 500;
        }
        at(t, () => {
          setKey(base);
          loop();
        });
      });
    }
    loop();
    return () => {
      alive = false;
      ts.forEach((cancel) => cancel());
    };
  }, [base, can]);

  return { key: can ? key : base, blink };
}
