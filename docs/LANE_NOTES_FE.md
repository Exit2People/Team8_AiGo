# LANE_NOTES_FE — 화면 줄 메모 (2026-11-21)

## 가짜 응답 스위치 (합치기 I1에서 볼 것)

| 켜는 법 | 동작 |
|---|---|
| `NEXT_PUBLIC_MOCK=1` (빌드 · dev 시작 때) | 모든 서버 호출을 `lib/mock.ts`의 가짜 응답으로 바꿔요 |
| 주소에 `?mock=1` | 이 탭(sessionStorage `aigo.mock`)에서만 가짜 응답. `?mock=0`이면 꺼요 |
| 둘 다 없음 (기본) | **진짜 서버**를 불러요 (`NEXT_PUBLIC_API_BASE`, 로그인 · 게임은 `/api/...`) |

- 그래서 합칠 때 **코드에서 바꿀 것은 없어요.** `NEXT_PUBLIC_MOCK`을 Vercel · `.env.local`에 넣지만 않으면 돼요.
- 가짜 응답 시험용 추가 주소 꼬리: `?mock=1&mockslow=1`(질문 9초 → 8초 뒤 기본 질문), `?mock=1&mocknone=1`(추천 0곳 → 찾지 못했어요 화면).
- 가짜 응답의 카카오 로그인은 진짜 카카오 대신 `/?signup=1`로 돌아와 동의 → 사는 곳 → 가입을 흉내 내요.

## 계약(03_API_CONTRACT)과 다르게 읽은 곳 · 확인할 곳

| 곳 | 내용 |
|---|---|
| `/questions/next` | 화면은 **조건 묶음만** 보내요 (A안). `done` → 확인, `fallback:true` → 화면 기본 질문, `needsAi`+`fallback{…}` → 그 질문을 기본 질문으로, `question`+`choices` → AI 질문. `slot`이 `want·walk·inout`이면 `basic`에, 아니면 `ai[]`에 넣어요 |
| `/questions/open` | 응답의 `filled`에 든 칸만 써요. `next`는 쓰지 않고 빈 칸 순서(몸 → 시간 → 질문)를 화면이 정해요 |
| 결과 티켓 | 00_RULES A7에 맞춰 티켓 칸 이름을 `도보` → `걷기`, `환승` → `갈아타기`로 바꿨어요 (11_FRONTEND_SPEC 부록 B와 다름) |
| `route.legs[].direction` · `fastCar` | 계약에 없어요. 있으면 쓰고 없으면 안 써요 (가는 길 "N번 칸" 알약) |
| 랭킹 | `NEXT_PUBLIC_RANKING_SOURCE=api`일 때만 서버(`/api/game/*`). 없으면 기기 저장 + 예시 기록 8개 |

## 만든 것 · 뺀 것

- next.config: `cacheComponents` · `partialPrefetching` · `allowedDevOrigins` 모두 빌드 통과 ✅
- 뺀 것: 시작 화면 `말로 하기`(voice) 화면, 아이폰 바닥색 읽기 · 가짜 스크롤, STT `?sttdebug` 진단, 배지 축하 중 타이머 일시정지(`later` 멈춤), 다크 테마(11_FRONTEND_SPEC 1절은 `colorScheme: only light`)
- 그림: `public/aigo` · `public/icons` · `app/icon.svg` · `app/apple-icon.png` 모두 200 (자리표시 파일 안 씀)

## 테스트 중 진짜 서버 호출 (알림)

- 연결 끊김 시험을 하다가 로컬 서버(8010)에 `/questions/next` 2번 · `/recommend` 2번이 실제로 나갔어요 (브라우저 차단 설정이 듣지 않았어요). 그 뒤로는 가짜 응답으로만 시험했어요.
