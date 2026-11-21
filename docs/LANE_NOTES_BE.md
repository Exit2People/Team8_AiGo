# 서버 줄 메모 (backend/)

> 2026-11-21 서버 줄(S3~S11)이 남기는 메모예요. 화면 줄 · 메인이 알아야 할 것만 적었어요.

## 1. 결과

| 단계 | 상태 | 비고 |
|---|---|---|
| S3 뼈대 · 조건 묶음 · 역 · 구동 · DB 모듈 | ✅ | `/districts` 25, `/stations/nearby` 가까운 순 4곳, `DATABASE_URL` 없이 `/health` ok |
| S4 질문 흐름 (A안) | ✅ | 키 없이 질문 0 → 몸 · 시간 → 하고 싶은 것 → 질문 4 → 질문 5 → done |
| S5 규칙 추천 | ✅ | 키 없이 3곳, 비 오면 바깥 장소 빠짐 |
| S6 AI 추천 · Jev · 말 넓히기 | ✅ (에이전트 빼고) | 실제 키 1번: **4.49초**, `by: ai`, 3곳 모두 서울시 실제 길 |
| S7 도착 예정 · 톡방 · 방명록 | ✅ | |
| S8 쿠키 · 세션 · 카카오 | ✅ | |
| S9 탈퇴 보관 · 되살리기 · 밴 | ✅ | |
| S10 게임 랭킹 | ✅ | 밴 · 탈퇴 회원 줄은 빼요 (07_AUTH 9절 💡) |
| S11 이메일 가입 | ✅ | |

- 테스트 144개 (`uv run pytest -q`), 키 · DB 없이 돌아요. DB 쓰는 테스트는 `tests/fakedb.py`(SQL 앞 `/*이름*/`로 알아봄).
- 서버 SQL 전체(소셜 · 카카오 가입 · 내 정보 · 게임 · 탈퇴 · 되살리기 · 이메일)를 **로컬 임시 Postgres**(`schema.sql` 적용)에서 실제 psycopg로 한 바퀴 돌려 봤어요. 운영 Neon에는 아무것도 쓰지 않았어요.

## 2. 뺀 것 (START_HERE 4.1)

| 뺀 것 | 대신 | 영향 |
|---|---|---|
| 추천 에이전트(LangGraph, `AIGO_AGENT=1`) | `AIGO_AGENT`가 켜져 있어도 Claude 한 번(`PICK_SYSTEM`) → 실패면 규칙 | `/health`의 `agent`는 늘 `false`. 추천은 8초 안 (실측 4.5초) |
| 질문 에이전트(LangGraph) | 조건 묶음만 온 `/questions/next`: 발전 질문 → Claude 한 번(`AI_QUESTION_SYSTEM`, 3.5초) → 가장 잘 나누는 은행 질문 → `fallback` | 계약 모양은 같아요 |
| 매일 장소 DB 받기(sync) | 스냅숏 `data/snapshot/aigo.db` 고정 (`/data/status`는 동작) | `AIGO_SYNC_FREEZE`와 같은 동작 |

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
