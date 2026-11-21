"use client";

import { useEffect, useRef, useState } from "react";
import type { FlowApi } from "../Flow";
import { Primary, Secondary, Sheet, Sub, Title } from "../ui";
import Mic from "../Mic";
import * as api from "@/lib/api";
import { readStamps, readVisits, removeStamp, saveStamp, today, type Stamp, type Visit } from "@/lib/device";
import { photoIll } from "@/lib/illust";
import { badgeStates, type BadgeState } from "@/lib/badges";
import { BadgeBoard, BadgeSheet } from "../Badges";
import type { ReviewsResp } from "@/lib/types";

const TAGS = ["걷기 편해요", "경치가 좋아요", "쉴 곳이 많아요", "사람이 많아요"];

/** 업로드 · 한 줄 사이에서 이어지는 값 */
const pending = { photo: "", text: "" };

function md(d: string) {
  return `${+d.slice(5, 7)}월 ${+d.slice(8, 10)}일`;
}

function StampPic({ src, w, h, tilt = 0 }: { src: string; w: number; h: number; tilt?: number }) {
  return (
    <span
      style={{
        display: "inline-block",
        width: w,
        height: h,
        background: "#fff",
        padding: 3,
        transform: `rotate(${tilt}deg)`,
        boxShadow: "var(--sh-ticket)",
        borderRadius: 2,
        outline: "2px dotted rgba(17,17,17,.15)",
        outlineOffset: -2,
      }}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={src} alt="" style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }} />
    </span>
  );
}

function useDevice() {
  const [visits, setVisits] = useState<Visit[]>([]);
  const [stamps, setStamps] = useState<Record<string, Stamp>>({});
  useEffect(() => {
    setVisits(readVisits());
    setStamps(readStamps());
  }, []);
  return { visits, stamps };
}

/** 다녀온 곳 (4.5 mine) */
export function Mine({ f }: { f: FlowApi }) {
  const { visits, stamps } = useDevice();
  const n = Object.keys(stamps).length;
  const left = visits.filter((v) => !stamps[`${v.id}@${v.date}`]).length;
  const now = new Date();
  // 달력 달 옮기기: 0 = 이번 달, -1 = 지난달, 1 = 다음 달 … (기록이 없는 달도 자유롭게 옮겨 봐요)
  const [mo, setMo] = useState(0);
  const shown = new Date(now.getFullYear(), now.getMonth() + mo, 1);
  const y = shown.getFullYear();
  const m = shown.getMonth();
  const thisMonth = mo === 0;
  const moveMonth = (d: number) => setMo((x) => x + d);
  const swipe = useRef<number | null>(null);
  const first = new Date(y, m, 1).getDay();
  const days = new Date(y, m + 1, 0).getDate();
  const ym = `${y}-${String(m + 1).padStart(2, "0")}`;
  const byDay: Record<number, Stamp | Visit> = {};
  visits.filter((v) => v.date.startsWith(ym)).forEach((v) => (byDay[+v.date.slice(8)] = stamps[`${v.id}@${v.date}`] ?? v));
  const monthStamps = Object.values(stamps).filter((s) => s.date.startsWith(ym)).length;

  return (
    <div className="content">
      <Title y={104}>다녀온 곳</Title>
      <Sub y={150}>{`우표 ${n}장${left ? ` · ${left}곳은 아직 기록 전` : "을 모았어요"}`}</Sub>
      {/* 스크롤 틀(높이 300) 안에 높이를 정하지 않은 grid를 둬요: 가장 긴 칸(이름이 두 줄 등)의 글자 높이에 맞춰
          모든 칸이 같은 높이로 함께 커져요. 칸에 min-height를 주면 grid가 그 값만 보고 글자를 무시해서 .main에 줘요 */}
      <div className="list" style={{ top: 196, height: 300 }}>
        <div style={{ display: "grid", gridAutoRows: "1fr", gap: 8, flex: "none" }}>
          {visits.length === 0 && <p className="t-sub c-sub">아직 다녀온 곳이 없어요. 오늘 첫 나들이를 찾아봐요</p>}
          {visits.map((v) => {
            const key = `${v.id}@${v.date}`;
            const st = stamps[key];
            return (
              <button
                key={key}
                className="row"
                style={{ minHeight: "auto", alignItems: "stretch", padding: "12px 12px 12px 16px" }}
                onClick={() => {
                  if (st) return f.go({ k: "sdetail", key });
                  if (!f.s.user) {
                    f.note("우표는 로그인하면 모을 수 있어요");
                    return f.go({ k: "login" });
                  }
                  pending.photo = "";
                  pending.text = "";
                  f.go({ k: "upload", key });
                }}
              >
                <span className="main" style={{ minHeight: 74, display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
                  <span className="chip" style={{ alignSelf: "flex-start", background: v.date === today() ? "var(--coral)" : "var(--chip)", color: v.date === today() ? "#fff" : "var(--ink)" }}>
                    {md(v.date)}
                    {v.date === today() ? " · 오늘" : ""}
                  </span>
                  <span className="t-answer" style={{ margin: "6px 0 4px", lineHeight: 1.2, wordBreak: "keep-all" }}>
                    {v.name}
                  </span>
                  <span className="t-item c-mute">{v.from ? `${v.from}에서 ${v.min}분` : v.kind}</span>
                </span>
                <span style={{ width: 88, borderRadius: 14, background: "var(--soft)", display: "flex", alignItems: "center", justifyContent: "center", flexDirection: "column", gap: 4 }}>
                  {st ? (
                    <StampPic src={st.photo} w={50} h={60} tilt={-3} />
                  ) : (
                    <>
                      <span style={{ width: 26, height: 26, borderRadius: 13, background: "var(--coral)", color: "#fff", lineHeight: "26px", fontWeight: 900, textAlign: "center" }}>+</span>
                      <span className="t-label">기록 남기기</span>
                    </>
                  )}
                </span>
              </button>
            );
          })}
        </div>
      </div>
      <Sheet y={512} />
      <div className="abs" style={{ left: 24, right: 24, top: 526, display: "flex", alignItems: "center", gap: 6 }}>
        <button className="cal-nav" onClick={() => moveMonth(-1)} aria-label="지난달">
          ‹
        </button>
        <span className="t-label c-mute">{y}</span>
        <span className="t-tvalue" style={{ minWidth: 44, textAlign: "center" }}>
          {m + 1}월
        </span>
        <button className="cal-nav" onClick={() => moveMonth(1)} aria-label="다음 달">
          ›
        </button>
        <span className="t-count" style={{ marginLeft: "auto" }}>
          {thisMonth ? "이번" : "이"} 달 우표 {monthStamps}장
        </span>
      </div>
      {/* 달력을 옆으로 밀어도 달이 바뀌어요 (왼쪽으로 밀면 다음 달) */}
      <div
        key={`${y}-${m}`}
        className="abs cal-grid"
        style={{ left: 24, right: 24, top: 566, display: "grid", gridTemplateColumns: "repeat(7, 1fr)", rowGap: 4, textAlign: "center", touchAction: "pan-y" }}
        onPointerDown={(e) => (swipe.current = e.clientX)}
        onPointerUp={(e) => {
          const x0 = swipe.current;
          swipe.current = null;
          if (x0 == null || Math.abs(e.clientX - x0) < 50) return;
          moveMonth(e.clientX < x0 ? 1 : -1);
        }}
      >
        {"일월화수목금토".split("").map((d) => (
          <span key={d} className="t-label c-mute" style={{ paddingBottom: 6 }}>
            {d}
          </span>
        ))}
        {Array.from({ length: first }).map((_, i) => (
          <span key={`e${i}`} />
        ))}
        {Array.from({ length: days }).map((_, i) => {
          const d = i + 1;
          const x = byDay[d];
          return (
            <span key={d} style={{ height: 36, position: "relative", display: "flex", alignItems: "center", justifyContent: "center" }}>
              {x && "photo" in x ? (
                <StampPic src={x.photo} w={24} h={30} tilt={d % 2 ? -4 : 4} />
              ) : (
                <span className="t-tmeta" style={{ color: x ? "var(--coral-deep)" : thisMonth && d === now.getDate() ? "var(--ink)" : "var(--mute)", fontWeight: x || (thisMonth && d === now.getDate()) ? 900 : 600 }}>
                  {d}
                </span>
              )}
            </span>
          );
        })}
      </div>
    </div>
  );
}

function shrink(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      const k = Math.min(1, 480 / Math.max(img.width, img.height));
      const c = document.createElement("canvas");
      c.width = Math.round(img.width * k);
      c.height = Math.round(img.height * k);
      c.getContext("2d")!.drawImage(img, 0, 0, c.width, c.height);
      URL.revokeObjectURL(url);
      resolve(c.toDataURL("image/jpeg", 0.82));
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("open"));
    };
    img.src = url;
  });
}

function visitOf(key: string): Visit | undefined {
  return readVisits().find((v) => `${v.id}@${v.date}` === key);
}

/** 사진 고르기 (4.5 upload) */
export function Upload({ f, stepKey }: { f: FlowApi; stepKey: string }) {
  const v = visitOf(stepKey);
  const [text, setText] = useState(pending.text);
  const cam = useRef<HTMLInputElement>(null);
  const alb = useRef<HTMLInputElement>(null);
  async function picked(file?: File) {
    if (!file) return;
    try {
      pending.photo = await shrink(file);
      pending.text = text.slice(0, 60);
      f.replaceTop({ k: "cut", key: stepKey });
    } catch {
      f.note("사진을 열지 못했어요. 다른 사진을 골라 주세요.");
    }
  }
  return (
    <div className="content">
      <Title y={104}>다녀온 곳</Title>
      <Sub y={150}>사진 한 장이 우표가 돼요</Sub>
      <div className="card" style={{ top: 236, padding: 20 }}>
        <p className="t-tile pre">{`${v?.name ?? "이곳"},\n어떠셨어요?`}</p>
        <div style={{ display: "flex", gap: 14, marginTop: 14, alignItems: "flex-start" }}>
          <span style={{ width: 90, height: 108, border: "2px dashed var(--mute)", borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", flex: "none" }} className="t-label c-mute">
            우표 자리
          </span>
          <div style={{ flex: 1, position: "relative" }}>
            <textarea
              className="textbox"
              rows={3}
              maxLength={60}
              value={text}
              onChange={(e) => {
                setText(e.target.value);
                pending.text = e.target.value;
              }}
              placeholder="예) 단풍이 곱고 길이 완만했어요"
              aria-label="한 줄 남기기 · 비워도 돼요"
              style={{ "--in-base": "16px", paddingRight: 56 } as React.CSSProperties}
            />
            <div style={{ position: "absolute", right: 6, bottom: 10 }}>
              <Mic value={text} max={60} onText={(x) => { setText(x); pending.text = x; }} />
            </div>
            <p className="t-item c-mute" style={{ marginTop: 6 }}>
              한 줄 남기기 · 비워도 돼요
            </p>
          </div>
        </div>
      </div>
      <input ref={cam} type="file" accept="image/*" capture="environment" hidden onChange={(e) => picked(e.target.files?.[0])} />
      <input ref={alb} type="file" accept="image/*" hidden onChange={(e) => picked(e.target.files?.[0])} />
      <Primary y={556} onClick={() => cam.current?.click()}>
        사진 찍기
      </Primary>
      <Secondary y={628} white onClick={() => alb.current?.click()}>
        앨범에서 고르기
      </Secondary>
      <Secondary y={700} onClick={f.back}>
        다음에 할게요
      </Secondary>
    </div>
  );
}

/** 우표로 자르는 중 (4.5 cut) */
export function Cut({ f, stepKey }: { f: FlowApi; stepKey: string }) {
  useEffect(() => {
    const t = setTimeout(() => {
      const v = visitOf(stepKey);
      const ok =
        !!v &&
        !!pending.photo &&
        saveStamp({ id: v.id, name: v.name, date: v.date, photo: pending.photo, text: pending.text.trim().slice(0, 60), tags: [], at: Date.now() });
      if (!ok) {
        f.note("우표를 저장하지 못했어요. 사진을 다시 골라 주세요.");
        f.back();
        return;
      }
      window.dispatchEvent(new CustomEvent("aigo:badge", { detail: { ev: "photo" } }));
      f.replaceTop({ k: "stamped", key: stepKey });
    }, f.still ? 300 : 1400);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return (
    <div className="content" role="status">
      <div className="abs" style={{ left: 101, top: 300, animation: "fadeIn .6s ease both" }}>
        <StampPic src={pending.photo || "/aigo/ill/photo_forest.svg"} w={190} h={230} />
      </div>
      <Title y={580} align="center" size="m">{"우표로\n자르고 있어요"}</Title>
      <Sub y={672} align="center">잠시만 기다려 주세요</Sub>
      <p className="abs center-x t-caption c-sub" style={{ top: 712 }}>
        사진은 우표 안에만 남아요
      </p>
    </div>
  );
}

/** 우표 붙이기 (4.5 stamped) */
export function Stamped({ f, stepKey }: { f: FlowApi; stepKey: string }) {
  const st = readStamps()[stepKey];
  useEffect(() => {
    const t = setTimeout(() => f.replaceTop({ k: "review", key: stepKey }), f.still ? 300 : 1600);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const d = st?.date ?? today();
  return (
    <div className="content" role="status">
      <div className="abs" style={{ left: 101, top: 330 }}>
        <StampPic src={st?.photo ?? "/aigo/ill/photo_forest.svg"} w={190} h={230} tilt={-4} />
        <span
          style={{
            position: "absolute",
            right: -30,
            top: -20,
            width: 110,
            height: 110,
            borderRadius: 55,
            border: "3px solid var(--coral-deep)",
            color: "var(--coral-deep)",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            transform: "rotate(12deg)",
            fontWeight: 900,
            background: "rgba(255,255,255,.4)",
          }}
        >
          <span style={{ fontSize: "calc(15px * var(--fs))" }}>{(st?.name ?? "").slice(0, 4)}</span>
          <span style={{ fontSize: "calc(12px * var(--fs))", fontFamily: "var(--mono)" }}>{d.replace(/-/g, ".")}</span>
        </span>
      </div>
      <Title y={600} align="center" size="m">{`${st?.name ?? ""} 우표를\n붙였어요`}</Title>
      <Sub y={692} align="center">{"다녀온 곳에 기록했어요\n잠시 뒤 한 줄 남기기로 넘어가요"}</Sub>
    </div>
  );
}

/** 한 줄 남기기 (4.5 review) */
export function Review({ f, stepKey, edit }: { f: FlowApi; stepKey: string; edit?: boolean }) {
  const st = readStamps()[stepKey];
  const [text, setText] = useState(edit ? st?.text ?? "" : pending.text);
  const [tags, setTags] = useState<string[]>(edit ? st?.tags ?? [] : []);
  if (!st) return null;
  const name = st.name;
  const done = () => {
    const t = text.trim().slice(0, 60);
    saveStamp({ ...st, text: t, tags });
    if (!edit && (t || tags.length)) window.dispatchEvent(new CustomEvent("aigo:badge", { detail: { ev: "review" } }));
    f.backWith(edit ? "한 줄을 고쳤어요" : `${name} 우표를 다녀온 곳에 붙였어요`);
  };
  return (
    <div className="content">
      <div className="abs" style={{ left: 24, top: 100, display: "flex", gap: 12, alignItems: "center" }}>
        <StampPic src={st.photo} w={50} h={60} tilt={-3} />
        <span className="chip" style={{ background: "var(--white)", color: "var(--coral-deep)" }}>
          {st.date.slice(5).replace("-", ".")}
        </span>
      </div>
      <div className="card" style={{ top: 186 }}>
        <h1 className="t-tile" tabIndex={-1}>
          한 줄 남겨 볼까요?
        </h1>
        <p className="t-caption c-mute" style={{ marginTop: 6 }}>
          {name}은(는) 어땠나요? 고르기만 해도 돼요
        </p>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 14 }}>
          {TAGS.map((t) => {
            const on = tags.includes(t);
            return (
              <button
                key={t}
                className="chip"
                aria-pressed={on}
                style={{ height: 40, lineHeight: "40px", borderRadius: 20, fontSize: "calc(16px * var(--fs))", padding: "0 16px", background: on ? "var(--ink)" : "var(--soft)", color: on ? "#fff" : "var(--ink)" }}
                onClick={() => setTags(on ? tags.filter((x) => x !== t) : [...tags, t])}
              >
                {t}
              </button>
            );
          })}
        </div>
        <p className="t-label c-deep" style={{ marginTop: 16 }}>
          직접 쓰기
        </p>
        <div style={{ position: "relative", marginTop: 6 }}>
          <textarea className="textbox" rows={2} maxLength={60} value={text} onChange={(e) => setText(e.target.value)} style={{ "--in-base": "17px", paddingRight: 60 } as React.CSSProperties} aria-label="직접 쓰기" />
          <div style={{ position: "absolute", right: 6, top: 8 }}>
            <Mic value={text} max={60} onText={setText} />
          </div>
        </div>
        <p className="t-item c-mute" style={{ marginTop: 6, textAlign: "right" }}>
          {text.length} / 60
        </p>
      </div>
      <p className="abs t-caption c-sub pre" style={{ left: 24, right: 24, top: 560 }}>
        {"닉네임과 함께 다른 사람에게도 보여요\n전화번호 · 주소처럼 나를 알 수 있는 말은 빼 주세요"}
      </p>
      <Primary y={636} onClick={done}>
        {edit ? "고치기" : "남기기"}
      </Primary>
      <Secondary y={708} white onClick={f.back}>
        {edit ? "그만둘래요" : "건너뛰기"}
      </Secondary>
    </div>
  );
}

/** 우표 자세히 (4.5 sdetail) */
export function Sdetail({ f, stepKey }: { f: FlowApi; stepKey: string }) {
  const st = readStamps()[stepKey];
  const v = visitOf(stepKey);
  const id = stepKey.split("@")[0];
  const [rv, setRv] = useState<ReviewsResp | null>(null);
  useEffect(() => {
    api.reviews(id, 1).then(setRv, () => setRv({ total: 0, page: 1, pages: 1, items: [] }));
  }, [id]);
  const date = stepKey.split("@")[1] ?? "";
  return (
    <div className="content">
      <Title y={104}>{st?.name ?? v?.name ?? ""}</Title>
      <Sub y={150}>{`${date ? md(date) : ""}${v?.from ? ` · ${v.from}에서 ${v.min}분` : ""}`}</Sub>
      <div className="abs scroll" style={{ left: 24, right: 24, top: 196, bottom: 120 }}>
        {st ? (
          <div className="card" style={{ position: "relative", left: 0, width: "100%", display: "flex", gap: 14 }}>
            <StampPic src={st.photo} w={80} h={96} tilt={-3} />
            <div style={{ flex: 1 }}>
              <p className="t-label c-deep">내가 남긴 한 줄</p>
              <p className="t-answer" style={{ marginTop: 8, lineHeight: 1.35 }}>
                {st.text || "아직 한 줄이 없어요"}
              </p>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 8 }}>
                {st.tags.map((t) => (
                  <span key={t} className="chip chip-soft">
                    {t}
                  </span>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <p className="t-sub c-sub">아직 우표가 없어요.</p>
        )}
        <div className="card" style={{ position: "relative", left: 0, width: "100%", marginTop: 14 }}>
          <p className="t-answer">
            다녀온 사람들의 방명록 <span className="c-deep">{rv?.total ?? 0}개</span>
          </p>
          {rv && rv.items.length === 0 && (
            <p className="t-sub c-mute" style={{ marginTop: 8 }}>
              아직 방명록이 비어 있어요
            </p>
          )}
          {rv?.items.map((r) => (
            <div key={r.id} style={{ marginTop: 12, borderTop: "1.5px solid var(--soft)", paddingTop: 10 }}>
              <p className="t-answer" style={{ fontSize: "calc(16px * var(--fs))", lineHeight: 1.35 }}>
                {r.text}
              </p>
              <p className="t-item c-mute" style={{ marginTop: 4 }}>
                {r.tag ? `#${r.tag} ` : ""}— {r.nick} · {r.date}
              </p>
            </div>
          ))}
        </div>
      </div>
      {st && (
        <>
          <Secondary y={756} w={166} white onClick={() => f.go({ k: "review", key: stepKey, edit: true })}>
            고치기
          </Secondary>
          <button
            className="btn btn-primary"
            style={{ left: 203, top: 756, width: 166, justifyContent: "center", background: "var(--coral-deep)" }}
            onClick={() => {
              removeStamp(stepKey);
              f.backWith(`${st.name} 우표를 지웠어요`);
            }}
          >
            지우기
          </button>
        </>
      )}
    </div>
  );
}

/** 업적 (4.5 badges, 11.4) */
export function Badges({ f }: { f: FlowApi }) {
  const u = f.s.user;
  const [open, setOpen] = useState<BadgeState | null>(null);
  if (!u) {
    return (
      <div className="content">
        <Title y={104}>업적</Title>
        <Sub y={150}>로그인하면 나들이마다 배지를 모아요</Sub>
        <Primary y={636} onClick={() => f.replaceTop({ k: "login" })}>
          로그인하러 가기
        </Primary>
      </div>
    );
  }
  const states = badgeStates(u.id, !!u.homeDong1);
  const gotN = states.filter((s) => s.earnedAt).length;
  return (
    <div className="content">
      <Title y={104}>업적</Title>
      <Sub y={150}>{`${states.length}개 중 ${gotN}개를 모았어요`}</Sub>
      <div className="abs scroll" style={{ left: 24, right: 24, top: 196, bottom: 0, paddingBottom: 30 }}>
        <BadgeBoard states={states} onPick={setOpen} />
      </div>
      {open && <BadgeSheet state={states.find((s) => s.def.id === open.def.id) ?? open} onClose={() => setOpen(null)} />}
    </div>
  );
}
