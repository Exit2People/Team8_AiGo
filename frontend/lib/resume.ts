/**
 * 로그인하고 돌아오기.
 * 카카오 로그인은 페이지를 통째로 다시 불러와서, 화면 흐름(고른 장소 · 도착 시각 · 화면 순서)이 사라져요.
 * 카카오로 넘어가기 직전에 지금 흐름을 이 탭(sessionStorage)에 잠깐 남겨 두고, 돌아오면 그 자리로 이어 가요.
 * 기기에 오래 남기지 않아요: 한 번 읽으면 지우고, 30분이 지나면 쓰지 않아요.
 */
import type { FlowState, Step } from "./flow";

const KEY = "aigo.resume";
const TTL = 30 * 60_000;

/** 되살릴 흐름 값 (로그인 · 테마 · 잠깐 뜨는 알림은 빼요) */
type Saved = { at: number; stack: Step[]; state: Partial<FlowState> };

export function saveResume(stack: Step[], s: FlowState) {
  const { user: _u, coral: _c, busy: _b, note: _n, tearing: _t, preparing: _p, qNotice: _q, stack: _s, ...state } = s;
  void [_u, _c, _b, _n, _t, _p, _q, _s];
  try {
    sessionStorage.setItem(KEY, JSON.stringify({ at: Date.now(), stack, state } satisfies Saved));
  } catch {
    /* 남기지 못하면 예전처럼 처음으로 가요 */
  }
}

/** 남겨 둔 흐름을 꺼내요(꺼내면 지워요) */
export function takeResume(): { stack: Step[]; state: Partial<FlowState> } | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    sessionStorage.removeItem(KEY);
    if (!raw) return null;
    const v = JSON.parse(raw) as Saved;
    if (!v || !Array.isArray(v.stack) || !v.stack.length || Date.now() - v.at > TTL) return null;
    return { stack: v.stack, state: v.state ?? {} };
  } catch {
    return null;
  }
}
