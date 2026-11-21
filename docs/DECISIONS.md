# DECISIONS — 당일 결정 기록

| 날짜 | 항목 | 결정 | 근거 |
|---|---|---|---|
| 2026-11-21 | 질문 흐름 | **(A) 리허설 그대로** — 질문 0(대화) → 비어 있는 고정 칸(몸 · 시간) → `/questions/next` AI 질문 최대 3개, 2초 안내 · 8초 은행 | START_HERE 1절, 사용자 답 |
| 2026-11-21 | `AIGO_QUESTION_START` | `open` | (A)안 |
| 2026-11-21 | 바뀐 숫자 | 없음 (`04_CONSTANTS.md` 그대로) | (A)안 |
| 2026-11-21 | 저장소 | `https://github.com/Exit2People/Team8_AiGo.git` (`~/Desktop/Team8_AiGo`) | 사용자가 알려 줌 |
| 2026-11-21 | Vercel | 화면 `aigo-final` · 서버 `aigo-final-api` | START_HERE 2.0 본선 기본값 |
| 2026-11-21 | DB | `secrets.env`의 `DATABASE_URL` 그대로, `schema.sql` 다시 적용. 운영 DB에 시험 쓰기 금지 | START_HERE 2.0 |
| 2026-11-21 | 서버 실행 | `uv`, 배포용 `requirements.txt`는 `uv export --no-hashes --no-dev --no-emit-project` | START_HERE 2.0 |
| 2026-11-21 | 로컬 서버 포트 | **8010** (8000은 다른 프로세스가 쓰는 중). `frontend/.env.local`도 8010 | 로컬 전용 |
| 2026-11-21 | CORS 정규식 기본 | `https://aigo-final[a-z0-9-]*\.vercel\.app` | 02_ARCHITECTURE 6절 ⚠️ 대회 이름에 맞춤 |
| 2026-11-21 | 명세 폴더 위치 | `/Users/kimsangjin/Desktop/PROMPTS` (문서의 `2026_YOUTH_HACKATHON/PROMPTS`를 이 경로로 읽음) | 실제 위치 |
| 2026-11-21 | 제출 주소 | 화면 `https://ai-go-team8.vercel.app` · 서버 `https://ai-go-api.vercel.app` | 사용자 요청 "URL은 AI-GO" (`ai-go.vercel.app`은 남이 써서 사용자가 `ai-go-team8` 고름) |
| 2026-11-21 | 카카오 리다이렉트 | `https://ai-go-team8.vercel.app/api/auth/kakao/callback` (사용자가 콘솔에 등록) | 07_AUTH 10.1 |
| 2026-11-21 | 커밋 단위 | **기능별로** 나눠 커밋 | 사용자 요청 |
| 2026-11-21 | `secrets.env` 넣기 | zsh `source`가 `DATABASE_URL`의 `&`에서 깨져서, 값을 찍지 않는 파이썬 읽기(`dotenv_values`) → 파이프로 넣음 | 08_DEPLOY 6.1 |
| 2026-11-21 | 두 줄 나누기 시점 | 화면 줄(F0~)을 S3와 **동시에** 시작 (가짜 응답으로 먼저 만들기 때문에 S3를 기다릴 필요 없음) | 시간 절약 |
| 2026-11-21 | 커밋 주체 | 사용자 요청(기능별 커밋)에 맞춰 각 줄의 하위 에이전트가 **자기 폴더만** `git commit -- <폴더>`로 기능마다 커밋. push는 메인만 | START_HERE 2.2 "커밋은 메인만"을 바꿈 |
| 2026-11-21 | 화면 자료 위치 | `frontend/data/` (dongs · badges · poses) | 11_FRONTEND_SPEC 0절 |
| 2026-11-21 | 운영 `AIGO_AGENT` | **0** (추천은 Claude 한 번 `PICK_SYSTEM` → 규칙). 에이전트 코드는 남겨 둠, 켜려면 Vercel 값만 1로 | 실측 한 번 호출 4.5초 vs 에이전트 8.0초 · 최악 17~19초(화면 한도 20초). START_HERE 4.3 |
| 2026-11-21 | 질문 에이전트 | 켜 둠 (실측 3.9초, 6.0초 한도, 실패면 발전 → 은행) | 서버 줄 보고 |
| 2026-11-21 | 화면 작업 브랜치 | 원격 `FE` 브랜치 (10:12, `cead40c`에서). FE팀(사람)과 화면 줄 에이전트가 같이 작업. 메인 에이전트가 사람 커밋을 받아 합치고 push. 배포 기준은 `main` → 합치기(I1) 때 `FE`를 `main`으로 | 사용자 요청 |
| 2026-11-21 | **브랜치 작업 방식 (10:30~)** | `main` = 김상진 · BE팀 (서버 · 배포). `FE`와 그 뒤 생기는 화면 브랜치 = FE팀. FE팀이 끝냈다고 알리면 사용자가 지시 → 에이전트가 그 브랜치를 `main`에 합치고 화면 · 서버 다시 배포 (지속 배포). `main`에서는 `frontend/`를 고치지 않아요 (합칠 때 충돌 방지). 화면 쪽 문제는 FE팀에 넘겨요 | 사용자 결정 |
| 2026-11-21 | 화면 수정 반영 | 에이전트가 `frontend/`를 고치면 **`FE` 브랜치에도 push** (FE에서 고쳐 push → `main`에 합쳐 배포). 서버 · 문서만 고친 것은 `main`에만 | 사용자 요청 |
| 2026-11-21 | 운영 DB 비우기 (10:50) | 사용자 지시로 톡방 · 멤버 · 신고 · 도착 예정 · 만료 확인 숫자 · **회원 전부**(동의 · 세션 · 게임 점수는 cascade) 삭제. 남은 줄 0 | 사용자 지시 |
| 2026-11-21 | 날짜가 바뀌면 톡방 지우기 | Vercel Cron이 매일 **00:00 KST**(`0 15 * * *` UTC)에 `/cron/daily-cleanup` 호출 → 어제까지의 톡방 · 멤버 · 신고 · 도착 예정 삭제. `CRON_SECRET`(Vercel 환경 변수)으로만 부를 수 있음. 앞으로 서버 배포는 `$CFG/vercel.json` 대신 **`backend/vercel.json`**(지역 icn1 + crons)을 써요 | 사용자 요청 |
