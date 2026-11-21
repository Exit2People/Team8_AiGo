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
