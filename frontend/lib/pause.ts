// 화면 일시정지: 업적 배지 축하 화면이 떠 있는 동안 그 뒤 화면의 시간을 멈춰요.
// 축하 화면을 닫으면 멈췄던 자리에서 이어서 움직여요(처음부터 다시 하지 않아요).
//
// - 화면 순서를 넘기는 타이머(티켓 출력 · 질문 등장 · 가방 담기 · 담고 움직임 …)는 setTimeout 대신 `later`를 써요.
//   멈춘 동안 흐른 시간은 세지 않아요.
// - CSS 애니메이션은 .app.paused 로 멈춰요(globals.css).
// - 게임처럼 매 프레임 움직이는 것은 `isPaused()`를 보고 그 프레임을 건너뛰어요.

type Listener = (paused: boolean) => void;
let paused = false;
const listeners = new Set<Listener>();

export const isPaused = () => paused;

export function setPaused(v: boolean) {
  if (paused === v) return;
  paused = v;
  [...listeners].forEach((l) => l(v));
}

export function onPause(l: Listener): () => void {
  listeners.add(l);
  return () => {
    listeners.delete(l);
  };
}

/** 멈출 수 있는 setTimeout. 돌려주는 함수를 부르면 취소돼요(clearTimeout 대신) */
export function later(ms: number, fn: () => void): () => void {
  let left = Math.max(0, ms);
  let started = 0;
  let id: ReturnType<typeof setTimeout> | null = null;
  let over = false;
  const run = () => {
    if (over || id !== null) return;
    started = performance.now();
    id = setTimeout(() => {
      id = null;
      over = true;
      off();
      fn();
    }, left);
  };
  const stop = () => {
    if (id === null) return;
    clearTimeout(id);
    id = null;
    left = Math.max(0, left - (performance.now() - started));
  };
  const off = onPause((p) => (p ? stop() : run()));
  if (!paused) run();
  return () => {
    over = true;
    stop();
    off();
  };
}
