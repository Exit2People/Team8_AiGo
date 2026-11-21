// 화면 일시정지: 업적 배지 축하 화면이 떠 있는 동안 게임처럼 매 프레임 움직이는 것을 멈춰요.
// 축하 화면을 닫으면 멈췄던 자리에서 이어서 움직여요(처음부터 다시 하지 않아요).
// 게임은 `isPaused()`를 보고 그 프레임을 건너뛰어요.

let paused = false;

export const isPaused = () => paused;

export function setPaused(v: boolean) {
  paused = v;
}
