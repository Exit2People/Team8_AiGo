"use client";

import { useEffect, useState, type ReactNode } from "react";
import type { FlowApi } from "../Flow";
import { ChevronIcon, DamgoFace } from "../Icons";
import { Caption, Primary, Sub, Title } from "../ui";
import Mic, { cleanName, cleanNick } from "../Mic";
import HomePicker from "./HomePicker";
import * as api from "@/lib/api";
import { backupDevice, drop, load, readBlocked, readStamps, readVisits, save } from "@/lib/device";
import { BADGES, badgeImg, recOf } from "@/lib/badges";
import { THEMES } from "@/lib/theme";
import { fmtNum } from "@/lib/format";

function Group({ y, children }: { y?: number; children: ReactNode }) {
  return (
    <div style={{ background: "var(--white)", borderRadius: 24, boxShadow: "var(--sh-row)", padding: "4px 0", marginTop: y ?? 14 }}>
      {children}
    </div>
  );
}

function Line({ label, value, onClick, danger, disabled }: { label: string; value?: string; onClick?: () => void; danger?: boolean; disabled?: boolean }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{ display: "flex", width: "100%", alignItems: "center", minHeight: 54, padding: "0 16px 0 20px", gap: 8, borderBottom: "1.5px solid var(--soft)", textAlign: "left" }}
    >
      <span className="t-answer" style={{ flex: 1, color: danger ? "var(--coral-deep)" : undefined, fontSize: 17 }}>
        {label}
      </span>
      {value != null && (
        <span className="t-sub c-mute" style={{ maxWidth: 170, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {value}
        </span>
      )}
      {!disabled && !danger && <ChevronIcon />}
    </button>
  );
}

export function gameBest(uid?: string | null): number {
  return load<number>(uid ? `aigo.game.best.${uid}` : "aigo.game.best", 0);
}

/** 내 정보 (4.5 my) */
export function My({ f }: { f: FlowApi }) {
  const u = f.s.user;
  const [ask, setAsk] = useState(false);
  const [busy, setBusy] = useState(false);
  const [stats, setStats] = useState({ stamps: 0, visits: 0, blocked: 0, best: 0, got: [] as string[] });
  useEffect(() => {
    const st = readStamps();
    const vs = readVisits();
    const got = u ? Object.entries(recOf(u.id).got).sort((a, b) => b[1] - a[1]).map(([id]) => id) : [];
    setStats({ stamps: Object.keys(st).length, visits: vs.length, blocked: readBlocked().length, best: gameBest(u?.id), got });
  }, [u]);
  const theme = THEMES.find((t) => t.color === f.s.coral)?.name ?? "코랄";
  const unrecorded = Math.max(0, stats.visits - stats.stamps);
  const recent = stats.got.slice(0, 3).map((id) => BADGES.find((b) => b.id === id)!).filter(Boolean);

  return (
    <div className="content">
      <div className="abs scroll" style={{ left: 24, right: 24, top: 100, bottom: 0, paddingBottom: 40 }}>
        <button
          style={{ display: "flex", width: "100%", alignItems: "center", gap: 16, background: "var(--white)", borderRadius: 24, padding: 16, boxShadow: "var(--sh-row)", textAlign: "left" }}
          onClick={() => !u && f.go({ k: "login" })}
          disabled={!!u}
        >
          <span style={{ width: 52, height: 52, borderRadius: 26, background: "var(--coral)", flex: "none" }}>
            <DamgoFace />
          </span>
          <span>
            <span className="t-answer" style={{ display: "block" }}>
              {u ? u.nickname || "닉네임 없음" : "로그인하지 않았어요"}
            </span>
            <span className="t-caption c-mute" style={{ display: "block", marginTop: 6 }}>
              {u ? (u.provider === "kakao" ? "카카오로 로그인했어요" : u.email) : "카카오나 이메일로 시작할 수 있어요"}
            </span>
          </span>
        </button>

        <button
          style={{ display: "flex", width: "100%", alignItems: "center", gap: 14, background: "var(--ink)", color: "#fff", borderRadius: 24, padding: "20px 16px", marginTop: 14, textAlign: "left" }}
          onClick={() => f.go({ k: "mine" })}
        >
          <span style={{ flex: 1 }}>
            <span className="t-answer" style={{ display: "block" }}>
              {u ? `우표 ${stats.stamps}장을 모았어요` : `다녀온 곳 ${stats.visits}곳`}
            </span>
            <span className="t-caption" style={{ display: "block", marginTop: 6, color: "var(--gray)" }}>
              {u ? `다녀온 곳 ${stats.visits}곳${unrecorded ? ` · ${unrecorded}곳은 기록 전` : ""}` : "로그인하면 다녀온 곳마다 우표를 모아요"}
            </span>
          </span>
          <span className="chip" style={{ background: "#fff", color: "var(--ink)" }}>
            보기
          </span>
        </button>

        <button
          style={{ display: "flex", width: "100%", alignItems: "center", gap: 12, background: "var(--white)", borderRadius: 24, padding: "16px", marginTop: 14, textAlign: "left", boxShadow: "var(--sh-row)" }}
          onClick={() => f.go(u ? { k: "badges" } : { k: "login" })}
        >
          <span style={{ display: "flex" }}>
            {(recent.length ? recent : [null]).map((b, i) => (
              // eslint-disable-next-line @next/next/no-img-element
              <img key={i} src={b ? badgeImg(b, true) : "/aigo/badges/_hidden.svg"} alt="" width={44} height={44} style={{ marginLeft: i ? -12 : 0 }} />
            ))}
          </span>
          <span style={{ flex: 1 }}>
            <span className="t-answer" style={{ display: "block" }}>
              {u ? `업적 ${stats.got.length}개를 모았어요` : "업적 배지"}
            </span>
            <span className="t-caption c-mute" style={{ display: "block", marginTop: 6 }}>
              {u ? `${recent[0] ? `최근: ${recent[0].name}` : "첫 나들이를 하면 배지가 생겨요"} · 전체 30개` : "로그인하면 나들이마다 배지를 모아요"}
            </span>
          </span>
          <span className="chip chip-soft">{u ? "보기" : "시작"}</span>
        </button>

        <button
          style={{ display: "flex", width: "100%", alignItems: "center", gap: 12, background: "var(--white)", borderRadius: 24, padding: "16px 16px 16px 20px", marginTop: 14, textAlign: "left", boxShadow: "var(--sh-row)" }}
          onClick={() => f.go({ k: "game" })}
        >
          <span style={{ flex: 1 }}>
            <span className="t-answer" style={{ display: "block" }}>
              담고 달리기
            </span>
            <span className="t-caption c-mute" style={{ display: "block", marginTop: 6 }}>
              {stats.best ? `최고 ${fmtNum(stats.best)}걸음 · 한 판 더 할까요?` : "쉬는 틈에 폴짝폴짝 한 판"}
            </span>
          </span>
          <span className="chip">시작</span>
        </button>

        {u && (
          <Group>
            <Line label="이름" value={u.name || "아직 없어요"} onClick={() => f.go({ k: "myedit", field: "name" })} />
            <Line label="닉네임" value={u.nickname || "아직 없어요"} onClick={() => f.go({ k: "myedit", field: "nickname" })} />
            <Line label="나이" value={u.age ? `${u.age}세` : "아직 없어요"} onClick={() => f.go({ k: "myedit", field: "age" })} />
            {u.provider === "email" && (
              <>
                <Line label="이메일" value={u.email} disabled />
                <Line label="비밀번호 바꾸기" onClick={() => f.note("비밀번호 바꾸기는 아직 준비 중이에요")} />
              </>
            )}
          </Group>
        )}
        <Group>
          {u && <Line label="사는 곳" value={u.homeDong1 || "아직 없어요"} onClick={() => f.go({ k: "myedit", field: "home1" })} />}
          <Line label="테마 색" value={theme} onClick={() => f.go({ k: "theme" })} />
          <Line label="차단한 사람" value={stats.blocked ? `${stats.blocked}명` : "없어요"} onClick={() => f.go({ k: "blocked" })} />
        </Group>
        {u && (
          <Group>
            <Line
              label="로그아웃"
              onClick={async () => {
                try {
                  await api.logout();
                } catch {
                  /* 실패해도 기기에서는 로그아웃 */
                }
                f.setUser(null);
                f.landHome("로그아웃했어요");
              }}
            />
            <Line label="계정 지우기" danger onClick={() => setAsk(true)} />
          </Group>
        )}
      </div>
      {ask && u && (
        <div className="modal-bg" onClick={() => setAsk(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
            <h2 className="t-title pre">{"계정을\n지울까요?"}</h2>
            <p className="t-sub c-mute pre" style={{ marginTop: 10 }}>
              {"3개월 동안 보관했다가 완전히 지워요.\n그 안에 다시 가입하면 되살릴 수 있어요.\n게임 기록은 바로 영구 삭제돼요"}
            </p>
            <button className="btn btn-secondary" style={{ marginTop: 18 }} onClick={() => setAsk(false)}>
              그만둘래요
            </button>
            <button
              className="btn btn-primary"
              style={{ justifyContent: "center", background: "var(--coral-deep)" }}
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  await api.deleteAccount();
                  // 서버가 204를 준 뒤에만 기기 보관함으로
                  backupDevice(u.id);
                  drop("aigo.game.best");
                  drop(`aigo.game.best.${u.id}`);
                  drop("aigo.game.ranking");
                  save("aigo.blocked", null);
                  f.chat.reset();
                  f.setUser(null);
                  f.landHome("계정을 지웠어요");
                } catch (e) {
                  f.note(api.errText(e));
                  setBusy(false);
                }
              }}
            >
              계정 지우기
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

const FIELDS = {
  name: { label: "이름", desc: "실제 이름을 적어 주세요", ph: "예) 김영자", max: 20 },
  nickname: { label: "닉네임", desc: "우표 · 한 줄 · 톡방에서 보이는 이름이에요", ph: "2 ~ 8자 · 한글 · 영어 · 숫자", max: 8 },
  age: { label: "나이", desc: "숫자만 적어 주세요", ph: "예) 68", max: 3 },
  home1: { label: "사는 곳", desc: "비워도 돼요 · 구와 동까지만 받아요", ph: "", max: 40 },
};

/** 내 정보 고치기 (4.5 myedit) */
export function MyEdit({ f, field }: { f: FlowApi; field: keyof typeof FIELDS }) {
  const u = f.s.user;
  const cfg = FIELDS[field];
  const init = u ? (field === "name" ? u.name : field === "nickname" ? u.nickname : field === "age" ? u.age : u.homeDong1 ?? "") : "";
  const [v, setV] = useState(init || "");
  const [pick, setPick] = useState(false);
  const [busy, setBusy] = useState(false);
  async function saveIt() {
    const t = v.trim();
    if (field === "name" && !t) return f.note("이름을 적어 주세요");
    if (field === "nickname" && !/^[가-힣A-Za-z0-9]{2,8}$/.test(t)) return f.note("닉네임은 2 ~ 8자, 한글 · 영어 · 숫자만 돼요");
    if (field === "age" && !(/^\d+$/.test(t) && +t >= 14 && +t <= 120)) return f.note("나이를 숫자로 적어 주세요");
    setBusy(true);
    try {
      const key = field === "home1" ? "homeDong1" : field;
      const m = await api.patchProfile({ [key]: t });
      if (m.loggedIn) f.setUser(m);
      f.backWith("저장했어요");
    } catch (e) {
      f.note(api.errText(e));
      setBusy(false);
    }
  }
  return (
    <div className="content">
      <Title y={112}>{cfg.label}</Title>
      <Sub y={160}>{cfg.desc}</Sub>
      <div className="abs" style={{ left: 24, top: 230, width: 345 }}>
        {field === "home1" ? (
          <div className="row" style={{ minHeight: 64 }}>
            <span className="main t-answer">{v || "아직 없어요"}</span>
            <button className="chip chip-soft" onClick={() => setPick(true)}>
              {v ? "바꾸기" : "고르기"}
            </button>
          </div>
        ) : (
          <div style={{ position: "relative" }}>
            <input
              className="textbox"
              style={{ height: 62, paddingRight: 70 }}
              value={v}
              maxLength={cfg.max}
              inputMode={field === "age" ? "numeric" : "text"}
              placeholder={cfg.ph}
              onChange={(e) => setV(e.target.value)}
              aria-label={cfg.label}
            />
            {(field === "name" || field === "nickname") && (
              <div style={{ position: "absolute", right: 7, top: 7 }}>
                <Mic value={v} replace pause={1200} max={cfg.max} clean={field === "nickname" ? cleanNick : cleanName} onText={setV} />
              </div>
            )}
          </div>
        )}
        {field === "home1" && v && (
          <button className="btn btn-white" style={{ position: "relative", width: "100%", marginTop: 12 }} onClick={() => setV("")}>
            사는 곳 비우기
          </button>
        )}
      </div>
      <Primary y={636} disabled={busy} onClick={saveIt}>
        저장하기
      </Primary>
      {pick && (
        <HomePicker
          onClose={() => setPick(false)}
          onPick={(x) => {
            setV(x);
            setPick(false);
          }}
        />
      )}
    </div>
  );
}

/** 테마 색 (4.5 theme, 13절) */
export function Theme({ f }: { f: FlowApi }) {
  const [n, setN] = useState(0);
  useEffect(() => setN(readVisits().length), []);
  return (
    <div className="content">
      <Title y={112}>테마 색</Title>
      <Sub y={160}>{"화면 색을\n골라 보세요"}</Sub>
      <div className="card" style={{ top: 240 }}>
        <p className="t-answer">테마 색</p>
        <p className="t-caption c-mute" style={{ marginTop: 4 }}>
          누르면 바로 바뀌어요
        </p>
        <div role="radiogroup" aria-label="테마 색" style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginTop: 14 }}>
          {THEMES.map((t) => {
            const on = f.s.coral === t.color;
            return (
              <button
                key={t.id}
                role="radio"
                aria-checked={on}
                aria-label={t.name}
                onClick={() => {
                  f.set({ coral: t.color });
                  if (t.id === "A") drop("aigo.theme");
                  else save("aigo.theme", t.id);
                }}
                style={{ height: 64, borderRadius: 18, background: t.color, color: "#fff", fontSize: 24, fontWeight: 900, outline: on ? "3px solid var(--ink)" : "none", outlineOffset: 2 }}
              >
                {on ? "✓" : ""}
              </button>
            );
          })}
        </div>
      </div>
      <div className="card" style={{ top: 470 }}>
        <p className="t-answer">다녀온 곳 {n}곳</p>
        <p className="t-caption c-mute" style={{ marginTop: 6, lineHeight: 1.45 }}>
          이 기기에만 30일 동안 기억해요. 같은 곳을 또 추천하지 않으려고요.
        </p>
      </div>
      <Caption y={760} dark>
        이름 · 전화번호 · 위치는 남기지 않아요
      </Caption>
    </div>
  );
}

/** 차단한 사람 (4.5 blocked) */
export function Blocked({ f }: { f: FlowApi }) {
  const list = f.chat.blocked;
  return (
    <div className="content">
      <Title y={112}>{list.length ? `${list.length}명을 차단했어요` : "차단한 사람이\n없어요"}</Title>
      <div className="card" style={{ top: 230 }}>
        <p className="t-answer">톡방에서 차단한 사람</p>
        <p className="t-caption c-mute" style={{ marginTop: 4 }}>
          차단을 풀면 그 사람의 말이 다시 보여요
        </p>
        {list.length === 0 ? (
          <p className="t-sub c-mute pre" style={{ marginTop: 16 }}>
            {"톡방 메뉴의 차단하기에서\n차단한 사람이 여기에 모여요"}
          </p>
        ) : (
          list.map((n) => (
            <div key={n} style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 12 }}>
              <span style={{ width: 40, height: 40, borderRadius: 20, background: "var(--soft)", textAlign: "center", lineHeight: "40px", fontWeight: 800 }}>{n.slice(0, 1)}</span>
              <span className="t-answer" style={{ flex: 1 }}>
                {n}
              </span>
              <button className="chip" aria-label={`${n} 님 차단 풀기`} onClick={() => f.chat.unblock(n)}>
                차단 풀기
              </button>
            </div>
          ))
        )}
      </div>
      <Caption y={760} dark>
        차단은 이 기기에만 남고, 상대에게 알리지 않아요
      </Caption>
    </div>
  );
}
