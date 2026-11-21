"use client";

import { useEffect, useRef, useState } from "react";
import type { FlowApi } from "../Flow";
import { CheckIcon } from "../Icons";
import { Caption, Dots, Primary, Secondary, Sheet, Sub, Title } from "../ui";
import Mic, { cleanName, cleanNick } from "../Mic";
import HomePicker from "./HomePicker";
import * as api from "@/lib/api";
import { discardDevice, restoreDevice } from "@/lib/device";
import { isNick, randomNick } from "@/lib/nick";

/** 이메일 가입 중인 값 (화면 사이에서 이어져요, 기기에 남기지 않아요) */
const draft = { email: "", pw: "", pw2: "", code: "", name: "", nick: "", age: "", home: "" as string, provider: "kakao" as "kakao" | "email" };
function resetDraft() {
  Object.assign(draft, { email: "", pw: "", pw2: "", code: "", name: "", nick: "", age: "", home: "", provider: "email" });
}

/** 카카오에서 확인 중 (4.1 kwait) */
export function Kwait({ f }: { f: FlowApi }) {
  const once = useRef(false);
  useEffect(() => {
    if (once.current) return;
    once.current = true;
    api.me().then(
      (m) => {
        if (!m.loggedIn && m.restorePending) return f.replaceTop({ k: "restore" });
        if (!m.loggedIn && m.signupPending) {
          draft.provider = "kakao";
          return f.replaceTop({ k: "agree" });
        }
        if (m.loggedIn) {
          f.setUser(m);
          return f.landAuthed("카카오로 로그인했어요");
        }
        f.backWith("카카오 로그인을 하지 못했어요. 다시 해 주세요.");
      },
      () => f.backWith("카카오 로그인을 하지 못했어요. 다시 해 주세요."),
    );
  }, [f]);
  return (
    <div className="content" role="status">
      <Sheet y={852} />
      <Title y={520} align="center" size="m">{"카카오에서\n확인하고 있어요"}</Title>
      <Sub y={612} align="center">{"카카오 화면에서 로그인하면\n저절로 돌아와요"}</Sub>
      <Dots y={680} />
    </div>
  );
}

function Bullets({ y, items }: { y: number; items: string[] }) {
  return (
    <div className="abs" style={{ left: 24, top: y, width: 345 }}>
      {items.map((t) => (
        <div key={t} style={{ display: "flex", gap: 10, alignItems: "flex-start", padding: "7px 0", borderBottom: "1.5px solid var(--soft)" }}>
          <span style={{ flex: "none", marginTop: 1 }}>
            <CheckIcon size={22} />
          </span>
          <span className="t-answer" style={{ lineHeight: 1.35, fontSize: "calc(16px * var(--fs))" }}>
            {t}
          </span>
        </div>
      ))}
    </div>
  );
}

/** 처음이면 동의 (4.1 agree) */
export function Agree({ f }: { f: FlowApi }) {
  return (
    <div className="content">
      <Title y={112}>{"처음이시네요\n이것만 남겨요"}</Title>
      <Sub y={196}>가입은 이 한 번이에요</Sub>
      <Sheet y={330} />
      <p className="abs t-label c-deep" style={{ left: 24, top: 352 }}>
        남기는 것
      </p>
      <Bullets
        y={366}
        items={[
          "다녀온 곳 (여기로 갈게요를 누른 곳)",
          "올린 우표 사진과 한 줄",
          "카카오 회원 번호",
          "내 정보에 적은 이름 · 닉네임 · 나이",
          "탈퇴하면 3개월 보관 뒤 완전히 지워요 (게임 기록은 바로 지워요)",
        ]}
      />
      <p className="abs t-label c-deep" style={{ left: 24, top: 640 }}>
        남기지 않는 것 · 위치 · 몸 상태
      </p>
      <Primary y={672} onClick={() => f.go({ k: "addr" })}>
        동의하고 시작하기
      </Primary>
      <Caption y={762} dark onClick={() => f.landHome("가입하지 않았어요. 로그인 없이도 쓸 수 있어요.")}>
        동의하지 않아요
      </Caption>
    </div>
  );
}

function HomeRow({ y, value, onPick }: { y: number; value: string; onPick: () => void }) {
  return (
    <div className="row abs" style={{ left: 24, top: y, minHeight: 64 }}>
      <span className="main">
        <span className="t-item c-mute" style={{ display: "block" }}>
          사는 곳 · 비워도 돼요
        </span>
        <span className="t-answer" style={{ display: "block", marginTop: 6 }}>
          {value || "아직 없어요"}
        </span>
      </span>
      <button className="chip chip-soft" onClick={onPick}>
        {value ? "바꾸기" : "고르기"}
      </button>
    </div>
  );
}

/** 사는 곳 (4.1 addr) */
export function Addr({ f }: { f: FlowApi }) {
  const [home, setHome] = useState(draft.home);
  const [pick, setPick] = useState(false);
  const [busy, setBusy] = useState(false);
  return (
    <div className="content">
      <Title y={112}>{"사는 곳을\n알려 주세요"}</Title>
      <Sub y={196}>구와 동까지만 받아요</Sub>
      <Sheet y={430} />
      <HomeRow y={460} value={home} onPick={() => setPick(true)} />
      <p className="abs t-caption c-mute" style={{ left: 24, top: 540 }}>
        상세 주소와 위치는 받지 않아요 · 서울에 살지 않으면 비워 두세요
      </p>
      <Primary
        y={672}
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          try {
            await api.signup(home || null);
            const u = await f.refreshMe();
            if (!u) throw new Error();
            f.landAuthed("가입했어요. 반가워요!");
          } catch (e) {
            f.note(api.errText(e, "처음부터 다시 해 주세요"));
          } finally {
            setBusy(false);
          }
        }}
      >
        다 됐어요
      </Primary>
      <Caption y={762} dark>
        내 정보에서 다시 바꿀 수 있어요
      </Caption>
      {pick && (
        <HomePicker
          onClose={() => setPick(false)}
          onPick={(v) => {
            setHome(v);
            draft.home = v;
            setPick(false);
          }}
        />
      )}
    </div>
  );
}

/** 전에 쓰던 기록 (4.1 restore) */
export function Restore({ f }: { f: FlowApi }) {
  const [info, setInfo] = useState<Awaited<ReturnType<typeof api.restoreInfo>> | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    api.restoreInfo().then(setInfo, (e) => f.landHome(api.errText(e, "처음부터 다시 해 주세요")));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const off = !info || busy;
  return (
    <div className="content">
      <Title y={112}>{"전에 쓰던 기록이\n남아 있어요"}</Title>
      <Sub y={196}>{info ? `${info.deletedAt}에 탈퇴했어요.\n${info.purgeAfter}까지 보관해요` : "확인하고 있어요"}</Sub>
      <Sheet y={330} />
      <p className="abs t-label c-deep" style={{ left: 24, top: 352 }}>
        불러오면 돌아오는 것
      </p>
      <Bullets y={366} items={[info?.nickname ? `내 정보 (닉네임 ${info.nickname})` : "내 정보 (이름 · 닉네임 · 나이 · 사는 곳)", "이 폰에 남긴 다녀온 곳 · 우표 · 업적"]} />
      <p className="abs t-label c-deep" style={{ left: 24, top: 470 }}>
        돌아오지 않는 것
      </p>
      <Bullets y={484} items={["게임 기록 (탈퇴할 때 지워졌어요)"]} />
      <Primary
        y={636}
        disabled={off}
        onClick={async () => {
          if (!info) return;
          setBusy(true);
          try {
            await api.restoreChoose("restore");
            restoreDevice(info.id);
            const u = await f.refreshMe();
            if (!u) f.note("다시 로그인해 주세요");
            else f.landAuthed("전에 쓰던 기록을 불러왔어요");
          } catch (e) {
            f.note(api.errText(e));
          } finally {
            setBusy(false);
          }
        }}
      >
        이전 기록 불러올게요
      </Primary>
      <Secondary
        y={708}
        disabled={off}
        onClick={async () => {
          if (!info) return;
          setBusy(true);
          try {
            await api.restoreChoose("fresh");
            discardDevice(info.id);
            if (info.provider === "kakao") f.replaceTop({ k: "agree" });
            else f.replaceTop({ k: "signup", i: 3 });
          } catch (e) {
            f.note(api.errText(e));
          } finally {
            setBusy(false);
          }
        }}
      >
        새로 시작할게요
      </Secondary>
    </div>
  );
}

function Field({
  label, value, onChange, type = "text", mode, max, placeholder, onEnter,
}: { label: string; value: string; onChange: (v: string) => void; type?: string; mode?: "email" | "numeric" | "text"; max?: number; placeholder?: string; onEnter?: () => void }) {
  return (
    <label style={{ display: "block", marginTop: 14 }}>
      <span className="t-label c-deep">{label}</span>
      <input
        className="textbox"
        style={{ marginTop: 6, height: 58 }}
        type={type}
        inputMode={mode}
        maxLength={max}
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") onEnter?.();
        }}
        autoComplete={type === "password" ? "current-password" : type === "email" ? "email" : "off"}
      />
    </label>
  );
}

/** 이메일로 로그인 (4.1 elogin) */
export function Elogin({ f }: { f: FlowApi }) {
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const [busy, setBusy] = useState(false);
  async function login() {
    if (busy) return;
    setBusy(true);
    try {
      await api.emailLogin(email.trim(), pw);
      const u = await f.refreshMe();
      f.landAuthed(`${u?.nickname || "회원"}님, 다시 만나서 반가워요`);
    } catch (e) {
      f.note(api.errText(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="content">
      <Title y={112}>{"이메일로\n로그인해요"}</Title>
      <Sub y={196}>{"가입할 때 쓴\n이메일이에요"}</Sub>
      <Sheet y={440} />
      <div className="abs" style={{ left: 24, top: 446, width: 345 }}>
        <Field label="이메일" type="email" mode="email" value={email} onChange={setEmail} placeholder="damgo@aigo.kr" />
        <Field label="비밀번호" type="password" value={pw} onChange={setPw} onEnter={login} />
      </div>
      <Primary y={636} disabled={busy || !email || !pw} onClick={login}>
        로그인
      </Primary>
      <Secondary
        y={708}
        onClick={() => {
          resetDraft();
          f.go({ k: "signup", i: 0 });
        }}
      >
        처음이에요 · 가입하기
      </Secondary>
      <Caption y={796} dark onClick={() => f.note("비밀번호 다시 정하기는 아직 준비 중이에요")}>
        비밀번호를 잊었어요
      </Caption>
    </div>
  );
}

const STEPS = [
  { name: "이메일", desc: "로그인할 때 써요" },
  { name: "비밀번호", desc: "8자 이상, 글자와 숫자를 섞어요" },
  { name: "이메일 확인", desc: "메일로 보낸 숫자 6자리를 넣어 주세요\n(메일이 안 보이면 스팸함도 봐 주세요)" },
  { name: "이름", desc: "실제 이름을 적어 주세요" },
  { name: "닉네임", desc: "한 줄 · 톡방 · 랭킹에서 보이는 이름이에요\n비워 두면 예쁜 이름을 지어 드려요" },
  { name: "나이", desc: "숫자만 적어 주세요" },
  { name: "사는 곳", desc: "골라도 되고 비워도 돼요 · 구와 동까지만 받아요" },
];

/** 이메일 가입 (4.1.1) */
export function Signup({ f, i }: { f: FlowApi; i: number }) {
  const [v, setV] = useState(() => [draft.email, draft.pw, draft.code, draft.name, draft.nick, draft.age, draft.home][i]);
  const [pw2, setPw2] = useState(draft.pw2);
  const [pick, setPick] = useState(false);
  const [busy, setBusy] = useState(false);
  const st = STEPS[i];

  function store(x: string) {
    setV(x);
    if (i === 0) draft.email = x;
    if (i === 1) draft.pw = x;
    if (i === 2) draft.code = x;
    if (i === 3) draft.name = x;
    if (i === 4) draft.nick = x;
    if (i === 5) draft.age = x;
    if (i === 6) draft.home = x;
  }

  /** 확인 숫자 다시 받기: 서버에 다시 보내 달라고 해요 */
  async function resend() {
    if (busy) return;
    setBusy(true);
    try {
      await api.emailStart(draft.email.trim(), draft.pw);
      draft.code = "";
      setV("");
      f.note("숫자를 다시 보냈어요");
    } catch (e) {
      f.note(api.errText(e, "다시 보내지 못했어요"));
    } finally {
      setBusy(false);
    }
  }

  async function next() {
    if (busy) return;
    const t = v.trim();
    if (i === 0 && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(t)) return f.note("이메일을 다시 확인해 주세요");
    if (i === 1) {
      if (!(v.length >= 8 && /[A-Za-z가-힣]/.test(v) && /\d/.test(v))) return f.note("비밀번호는 8자 이상, 글자와 숫자를 섞어 주세요");
      if (v !== pw2) return f.note("두 비밀번호가 달라요. 다시 확인해 주세요");
    }
    if (i === 3 && !t) return f.note("이름을 적어 주세요");
    if (i === 4 && !t) {
      // 비워 두면 이름을 지어 줘요(가입 규칙 2 ~ 8자에 맞아요)
      const made = randomNick();
      store(made);
      f.note(`닉네임을 '${made}'(으)로 지어 드렸어요. 내 정보에서 바꿀 수 있어요`);
    } else if (i === 4 && !isNick(t)) return f.note("닉네임은 2 ~ 8자, 한글 · 영어 · 숫자만 돼요");
    if (i === 5 && !(/^\d+$/.test(t) && +t >= 14 && +t <= 120)) return f.note("나이를 숫자로 적어 주세요");
    setBusy(true);
    try {
      if (i === 1) await api.emailStart(draft.email.trim(), draft.pw);
      if (i === 2) {
        const r = await api.emailVerify(t);
        if (r.restorable) return f.go({ k: "restore" });
      }
      if (i === 6) {
        await api.emailFinish({ name: draft.name.trim(), nickname: draft.nick.trim() || randomNick(), age: draft.age.trim(), homeDong1: draft.home || null });
        await f.refreshMe();
        f.set({ stack: [{ k: "start" }, { k: "welcome" }] });
        return;
      }
      f.go({ k: "signup", i: i + 1 });
    } catch (e) {
      f.note(api.errText(e));
    } finally {
      setBusy(false);
    }
  }

  const input =
    i === 6 ? (
      <HomeRow y={0} value={v} onPick={() => setPick(true)} />
    ) : (
      <div style={{ position: "relative" }}>
        <input
          className="textbox"
          style={{ height: 62, paddingRight: i === 3 || i === 4 ? 70 : 60 }}
          type={i === 1 ? "password" : i === 0 ? "email" : "text"}
          inputMode={i === 0 ? "email" : i === 2 || i === 5 ? "numeric" : "text"}
          maxLength={i === 2 ? 6 : i === 5 ? 3 : i === 4 ? 8 : i === 3 ? 20 : undefined}
          value={v}
          onChange={(e) => store(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && next()}
          aria-label={st.name}
          autoComplete={i === 1 ? "new-password" : i === 0 ? "email" : "off"}
        />
        {(i === 3 || i === 4) && (
          <div style={{ position: "absolute", right: 7, top: 7 }}>
            <Mic value={v} replace pause={1200} max={i === 4 ? 8 : 20} clean={i === 4 ? cleanNick : cleanName} onText={store} />
          </div>
        )}
      </div>
    );

  return (
    <div className="content">
      <Title y={112}>회원가입</Title>
      <Sub y={160}>{`일곱 가지 가운데 ${i + 1}번째`}</Sub>
      <Sheet y={240} />
      <div className="abs" style={{ left: 24, top: 266, width: 345 }}>
        <p className="t-tile">{st.name}</p>
        <p className="t-sub c-mute pre" style={{ marginTop: 6 }}>
          {st.desc}
        </p>
        <div style={{ marginTop: 18, position: "relative", minHeight: 64 }}>{input}</div>
        {i === 1 && (
          <>
            <input
              className="textbox"
              style={{ height: 62, marginTop: 10 }}
              type="password"
              placeholder="한 번 더 넣어 주세요"
              value={pw2}
              onChange={(e) => {
                setPw2(e.target.value);
                draft.pw2 = e.target.value;
              }}
              onKeyDown={(e) => e.key === "Enter" && next()}
              autoComplete="new-password"
              aria-label="한 번 더 넣어 주세요"
            />
            {pw2 && (
              <p className="t-caption" style={{ marginTop: 8, color: pw2 === v ? "var(--ink)" : "var(--coral-deep)" }}>
                {pw2 === v ? "✓ 두 비밀번호가 같아요" : "아직 두 비밀번호가 달라요"}
              </p>
            )}
          </>
        )}
        {i === 2 && (
          <button className="t-caption c-mute" style={{ marginTop: 10, textDecoration: "underline" }} onClick={resend} disabled={busy}>
            다시 받기
          </button>
        )}
      </div>
      <Primary y={636} disabled={busy} onClick={next} label={i === 6 ? "가입하기" : "다음"}>
        {i === 6 ? "가입하기" : "다음"}
      </Primary>
      <Caption y={726} dark>
        가입하면 이용약관과 개인정보 처리방침에 동의하게 돼요
      </Caption>
      {pick && (
        <HomePicker
          onClose={() => setPick(false)}
          onPick={(x) => {
            store(x);
            setPick(false);
          }}
        />
      )}
    </div>
  );
}

/** 환영 편지 (4.1 welcome) */
export function Welcome({ f }: { f: FlowApi }) {
  const nick = f.s.user?.nickname || "회원";
  return (
    <div className="content">
      <Title y={112}>{`${nick}님,\n반가워요!`}</Title>
      <Sub y={196}>AI GO 식구가 되셨어요</Sub>
      <div className="card" style={{ top: 300, padding: "24px 22px", background: "var(--g-paper)" }}>
        <p className="t-answer">{nick}님께</p>
        <p className="t-sub pre" style={{ marginTop: 12, lineHeight: 1.6 }}>
          {"오늘부터 다녀온 곳마다\n우표가 한 장씩 모여요.\n첫 우표는 제가 붙여 드렸어요.\n가까운 데부터 같이 가 봐요."}
        </p>
        <p className="t-answer" style={{ marginTop: 14, textAlign: "right" }}>
          — 담고 드림
        </p>
      </div>
      <Primary y={672} onClick={() => f.landAuthed()}>
        시작하기
      </Primary>
      <Caption y={762} dark>
        내 정보에서 다시 바꿀 수 있어요
      </Caption>
    </div>
  );
}
