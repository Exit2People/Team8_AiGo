"use client";

/* 넓은 화면(PC 웹)에서만 쓰는 '내 정보' 옆 패널과 가운데 창.
   화면 흐름(stack)은 폰과 똑같이 두고, 그리는 방법만 바꿔요.
   - [..., 첫 화면, my]            → 첫 화면은 흐리게 · 어둡게, 내 정보는 왼쪽에서 밀려 나오는 패널
   - [..., 첫 화면, my, badges ...] → 패널은 그대로, 남은 오른쪽 자리에 업적 · 게임 같은 창
   - [..., 결과, badges]           → 패널 없이 가운데 창만
   그래서 뒤로 가기 · 처음으로 · 로그인 복귀가 폰과 똑같이 움직여요. */

import { useEffect, useState } from "react";
import type { FlowApi } from "./Flow";
import type { Step } from "@/lib/flow";
import { poseOf } from "@/lib/flow";
import { bgFor } from "@/lib/poses";
import Screen from "./screens";
import { My } from "./screens/My";

/** 내 정보에서 이어지는 화면들 (넓은 화면에서는 패널 · 창으로 떠요) */
const FAMILY = new Set<Step["k"]>(["my", "myedit", "theme", "blocked", "mine", "upload", "cut", "stamped", "review", "sdetail", "badges", "game", "rank"]);
/** 로그인 · 가입 화면: 위 화면들에서 이어서 열렸을 때만 같은 창 안에 떠요 (첫 화면의 '시작하기'로 열면 폰처럼 전체 화면) */
const AUTH = new Set<Step["k"]>(["login", "elogin", "kwait", "agree", "addr", "restore", "signup", "welcome"]);
const inLayer = (k: Step["k"]) => FAMILY.has(k) || AUTH.has(k);

/** 무대 기본 크기 (Stage.tsx와 같아요) */
const W = 393;
const H = 852;
/** 넓은 화면으로 볼 최소 폭 (무대 칸 기준) — 패널(400) + 창(354) + 여백이 들어가는 폭 */
const MIN_UNITS = 900;

export type Layer = {
  /** 흐리게 깔리는 화면이 몇 번째(1부터)인지 = 그 화면이 맨 위였을 때 stack 길이 */
  baseAt: number;
  /** 내 정보 패널이 있으면 stack에서 my의 자리 (없으면 -1) */
  myAt: number;
  /** 가운데 창에 뜨는 첫 화면의 자리 */
  modalFrom: number;
};

/** 지금 stack을 넓은 화면에서 어떻게 그릴지 */
export function layerOf(stack: Step[], wide: boolean): Layer | null {
  if (!wide) return null;
  let j = stack.length;
  while (j > 1 && inLayer(stack[j - 1].k)) j--;
  if (j >= stack.length || !FAMILY.has(stack[j].k)) return null;
  const drawer = stack[j].k === "my";
  return { baseAt: j, myAt: drawer ? j : -1, modalFrom: drawer ? j + 1 : j };
}

/** PC처럼 옆이 넓은 화면인지 (마우스가 있거나 폭이 1024px 이상인 가로 화면). 폰 가로 화면은 빼요 */
export function useWide() {
  const [wide, setWide] = useState(false);
  useEffect(() => {
    const fine = window.matchMedia?.("(hover: hover) and (pointer: fine)");
    const check = () => {
      const w = document.documentElement.clientWidth;
      const h = Math.min(window.innerHeight, window.visualViewport?.height ?? window.innerHeight);
      if (!(w > 0) || !(h > 0)) return;
      const units = w / Math.min(w / W, h / H);
      setWide(units >= MIN_UNITS && (!!fine?.matches || w >= 1024));
    };
    check();
    window.addEventListener("resize", check);
    fine?.addEventListener?.("change", check);
    return () => {
      window.removeEventListener("resize", check);
      fine?.removeEventListener?.("change", check);
    };
  }, []);
  return wide;
}

/** 값이 사라져도 닫히는 움직임이 끝날 때까지 잠깐 붙잡아 둬요 */
function useLinger<T>(v: T | null, ms: number, same: (a: T, b: T) => boolean) {
  const [kept, setKept] = useState<T | null>(v);
  if (v !== null && (kept === null || !same(v, kept))) setKept(v);
  const leaving = v === null && kept !== null;
  useEffect(() => {
    if (!leaving) return;
    const t = setTimeout(() => setKept(null), ms);
    return () => clearTimeout(t);
  }, [leaving, ms]);
  return { value: v ?? kept, leaving };
}

const sameStep = (a: Step, b: Step) => JSON.stringify(a) === JSON.stringify(b);

/** 패널에서 지금 열린 창을 표시할 이름 (예: myedit-age) */
function navKey(step: Step | undefined) {
  if (!step) return undefined;
  return step.k === "myedit" ? `myedit-${step.field}` : step.k;
}

const EDIT_TITLE = { nickname: "닉네임", age: "나이", home1: "사는 곳" } as const;

type Shown = { step: Step; at: number };

export default function WideLayers({ f, layer, frozen }: { f: FlowApi; layer: Layer | null; frozen: boolean }) {
  const stack = f.s.stack;
  const hasDrawer = !!layer && layer.myAt >= 0;
  const modalNow: Shown | null = layer && stack.length > layer.modalFrom ? { step: stack[stack.length - 1], at: stack.length } : null;

  const dim = useLinger(layer ? true : null, 320, () => true);
  const drawer = useLinger(hasDrawer ? true : null, 340, () => true);
  const modal = useLinger(modalNow, 260, (a, b) => a.at === b.at && a.step === b.step);
  // 창이 닫히는 동안에도 패널 옆 자리(오른쪽)에 머물러요
  const [withDrawer, setWithDrawer] = useState(hasDrawer);
  if (modalNow && withDrawer !== hasDrawer) setWithDrawer(hasDrawer);

  /** 창만 닫고 내 정보 패널로 (패널이 없으면 모두 닫아요) */
  const closeModal = () => {
    if (!layer) return;
    if (stack.length > layer.modalFrom) f.popTo(layer.modalFrom);
    else f.popTo(layer.baseAt);
  };
  const closeAll = () => layer && f.popTo(layer.baseAt);

  // Esc: 맨 위 하나를 닫아요 (창 안에 작은 확인 창이 떠 있으면 그 창이 먼저예요)
  useEffect(() => {
    if (!layer || frozen) return;
    function onKey(e: KeyboardEvent) {
      if (e.key !== "Escape" || e.defaultPrevented) return;
      if (document.querySelector(".lyModal [role=dialog], .lyDrawer [role=dialog][aria-modal=true]")) return;
      e.preventDefault();
      closeModal();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  // 패널 안에서 누른 화면은 창으로 열어요. 이미 창이 열려 있으면 그 창을 바꿔요(겹겹이 쌓지 않아요)
  const drawerF: FlowApi = {
    ...f,
    go: (step: Step) => {
      const st = f.sRef.current.stack;
      const myAt = st.findIndex((x) => x.k === "my");
      if (myAt < 0 || st.length <= myAt + 1 || !inLayer(step.k)) return f.go(step);
      if (st.length === myAt + 2) {
        if (sameStep(st[myAt + 1], step)) return;
        return f.replaceTop(step);
      }
      f.replaceFrom(myAt + 1, step);
    },
  };

  const shown = modal.value;
  const modalTop = !!shown && !modal.leaving;
  const depth = layer && modalNow ? stack.length - layer.modalFrom : 1;
  const active = hasDrawer && layer ? navKey(stack[layer.myAt + 1]) : undefined;
  const mbg = shown ? bgFor(poseOf(shown.step, f.s)) : null;
  const hideHead = shown && ["cut", "stamped", "kwait", "welcome"].includes(shown.step.k);
  const title = shown?.step.k === "myedit" ? `${EDIT_TITLE[shown.step.field]} 고치기` : shown?.step.k === "blocked" ? "차단한 사람" : null;

  if (!dim.value) return null;
  return (
    <>
      <div className={`lyDim${dim.leaving ? " leaving" : ""}`} onClick={closeModal} aria-hidden="true" />

      {drawer.value && (
        <aside
          className={`lyDrawer${drawer.leaving ? " leaving" : ""}`}
          role="dialog"
          aria-modal={!modalTop || undefined}
          aria-labelledby="lyDrawerTitle"
          data-top={(!modalTop && !drawer.leaving) || undefined}
          inert={frozen || drawer.leaving || undefined}
        >
          <div className="lyBg" style={{ transform: `translateY(${bgFor("my").coralY}px)` }} />
          <h1 id="lyDrawerTitle" className="lyTitle t-title-s" tabIndex={-1}>
            마이메뉴
          </h1>
          <button className="chip lyClose" onClick={closeAll}>
            닫기
          </button>
          <My f={drawerF} active={active} />
        </aside>
      )}

      {shown && mbg && (
        <section
          className={`lyModal${withDrawer ? " side" : ""}${modal.leaving ? " leaving" : ""}`}
          role="dialog"
          aria-modal="true"
          aria-label={title ?? "창"}
          data-top={modalTop || undefined}
          inert={frozen || modal.leaving || undefined}
        >
          <div className="lyBg" style={{ transform: `translateY(${mbg.coralY}px)` }} />
          <div className="lyBg deep" style={{ opacity: mbg.deep }} />
          <Screen f={f} step={shown.step} at={shown.at} />
          {!hideHead && (
            <>
              {depth > 1 && (
                <button className="topbar-back" onClick={f.back} aria-label="뒤로">
                  ‹ 뒤로
                </button>
              )}
              {title && <div className="topbar-title">{title}</div>}
              <div className="topbar-right">
                <button className="chip" onClick={closeModal}>
                  닫기
                </button>
              </div>
            </>
          )}
        </section>
      )}
    </>
  );
}
