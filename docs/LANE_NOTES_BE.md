# 서버 줄 메모 (backend/)

> 2026-11-21 서버 줄(S3~S11)이 남기는 메모예요. 화면 줄 · 메인이 알아야 할 것만 적었어요.

## 1. 결과

| 단계 | 상태 | 비고 |
|---|---|---|
| S3 뼈대 · 조건 묶음 · 역 · 구동 · DB 모듈 | ✅ | `/districts` 25, `/stations/nearby` 가까운 순 4곳, `DATABASE_URL` 없이 `/health` ok |
| S4 질문 흐름 (A안) | ✅ | 키 없이 질문 0 → 몸 · 시간 → 하고 싶은 것 → 질문 4 → 질문 5 → done |
| S5 규칙 추천 | ✅ | 키 없이 3곳, 비 오면 바깥 장소 빠짐 |
| S6 AI 추천 · Jev · 말 넓히기 | ✅ | 한 번 호출 실측 **4.49초** (`by: ai`). 추천 에이전트 실측 **7.98초** (`by: agent`, 도구 1번) |
| S7 도착 예정 · 톡방 · 방명록 | ✅ | |
| S8 쿠키 · 세션 · 카카오 | ✅ | |
| S9 탈퇴 보관 · 되살리기 · 밴 | ✅ | |
| S10 게임 랭킹 | ✅ | 밴 · 탈퇴 회원 줄은 빼요 (07_AUTH 9절 💡) |
| S11 이메일 가입 | ✅ | |

- 테스트 144개 (`uv run pytest -q`), 키 · DB 없이 돌아요. DB 쓰는 테스트는 `tests/fakedb.py`(SQL 앞 `/*이름*/`로 알아봄).
- 서버 SQL 전체(소셜 · 카카오 가입 · 내 정보 · 게임 · 탈퇴 · 되살리기 · 이메일)를 **로컬 임시 Postgres**(`schema.sql` 적용)에서 실제 psycopg로 한 바퀴 돌려 봤어요. 운영 Neon에는 아무것도 쓰지 않았어요.

## 2. 에이전트 (10:05에 되살림) · 뺀 것

| 무엇 | 동작 | 실측 (실제 키 1번씩) |
|---|---|---|
| 질문 에이전트 (`question/agent.py`, LangGraph) | 조건 묶음만 온 `/questions/next` · `/questions/ai`의 첫 시도. 6초 · 도구 2번 → 코드 검사 → Jev 2개(`AIGO_QUESTION_JEV`). 실패 · 늦음이면 발전 질문 → 은행 → fallback (에이전트를 못 썼을 때만 Claude 한 번). `AIGO_QUESTION_AGENT=0`이면 끔 | **3.92초**, 도구 0번, `source: agent` |
| 추천 에이전트 (`recommend/agent/`, LangGraph) | `AIGO_AGENT=1`일 때. 전체를 화면 대기 20초 − 1초 안에 끝내려고 에이전트에 `min(30초, 남은 시간 − 8초)`(대략 10초)만 줘요. 실패 · 늦음이면 Claude 한 번(6초) → 규칙. `/health.agent`가 이 스위치를 그대로 보여요 | **7.98초**, 도구 1번, 3곳 냈고 이유 검사에서 2곳이 빠져 규칙으로 채움 |
| 매일 장소 DB 받기(sync) | 뺐어요. 스냅숏 고정 (`/data/status`는 동작) | — |

- ⚠️ 추천 에이전트는 `effort: low`로 불러요 (06_AI_PROMPTS 0절은 안 넘김 = high). 20초 안에 끝내려고 바꿨어요.

## 3. 계약과 다른 점 (모두 칸을 **더한** 것, 뺀 칸 없음)

| 곳 | 다른 점 |
|---|---|
| `/questions/next` (조건 묶음만) | AI · 은행 질문에 `source`(`ai` · `fixed` · `lead`), 은행 질문에 `id`가 더 붙어요 |
| `/recommend` | 이동 범위 안에 0곳이면 상한 +20분으로 한 번 넓혀 찾고, 그때만 맨 위에 `"relaxed": true` (P04 5번 "넓히고 표시") |
| `/questions/open/forget` | `next`는 `next_step(조건, [0])` (지운 칸을 다시 물어요) |

## 4. 배포에 필요한 것

- 새 환경 변수 없음. 이미 넣은 것 중 꼭 맞아야 하는 것:
  - `AIGO_PUBLIC_URL` = 화면 주소 `https://ai-go-team8.vercel.app` (카카오 `redirect_uri`와 쿠키 `Secure`가 이 값으로 정해져요)
  - `AIGO_CORS_ORIGINS`에 화면 주소 (기본 정규식은 `aigo-final…`만 맞아서 `ai-go-team8`은 이 값으로만 통과해요)
  - `AIGO_SESSION_SECRET` (없으면 로그인 API 503)
- 서버 배포 폴더에 `data/`(reference · snapshot)가 있어야 장소가 나와요 (`08_DEPLOY.md` 9절).
- 의존성은 바꾸지 않았어요 → `backend/requirements.txt` 그대로.
- 로컬 서버 포트는 8010.
