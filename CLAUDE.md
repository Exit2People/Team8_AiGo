# CLAUDE.md — AI GO 저장소

> 이 파일은 `PROMPTS/CONTEST_CLAUDE.md`를 저장소 맨 위에 `CLAUDE.md`로 복사한 거예요. **아래 설정 칸만 사람이 저장소마다 채워요.**

## 설정 (사람이 채워요 — 에이전트는 묻지 않고 이 값을 써요)

| 항목 | 값 | 기본값 (비어 있으면) |
|---|---|---|
| 저장소 주소 | https://github.com/Exit2People/Team8_AiGo.git | `https://github.com/Exit2People/FinalDestination.git` |
| 이 저장소는 | 본선 | — |
| Vercel 화면 프로젝트 | aigo-final | `aigo-final` |
| Vercel 서버 프로젝트 | aigo-final-api | `aigo-final-api` |

- 이름이 이미 쓰이면 에이전트가 `-2`를 붙이고 실제 주소를 이 표 아래에 적어요.
- **실제 주소 (2026-11-21):** 화면 `https://ai-go-team8.vercel.app` (프로젝트 `aigo-final`, 보조 `aigo-final-phi.vercel.app`) · 서버 `https://ai-go-api.vercel.app` (프로젝트 `aigo-final-api`, 보조 `aigo-final-api.vercel.app`). 사용자 요청으로 `ai-go` 이름을 썼어요 (`ai-go.vercel.app`은 남이 씀)

- 명세 폴더(PROMPTS)의 실제 위치: `/Users/kimsangjin/Desktop/PROMPTS` (문서 속 `2026_YOUTH_HACKATHON/PROMPTS` 경로는 이 위치로 읽어요)

## 시작

모든 작업은 @/Users/kimsangjin/Desktop/PROMPTS/START_HERE.md 를 먼저 읽고 따라요.
사용자가 "구현해줘"라고 하면 START_HERE 1절(질문 하나)부터 4절까지 끝까지 진행해요.

## 권한 (사용자 승인 2026-11-20)

- 이 저장소에서 "구현해줘"는 **커밋 · push · Vercel 프로젝트 만들기 · 환경 변수 넣기 · 배포를 묻지 않고 맡긴다**는 뜻이에요.
- 그래도 절대 안 해요: `secrets.env` · `.env*` 커밋, force push, 브랜치 지우기, 운영 DB(`secrets.env`의 `DATABASE_URL`)에 시험 데이터 쓰기.

## 늘 지킬 것

1. 키 · DB 주소 · 비밀번호를 출력 · 커밋하지 않아요. 값은 `PROMPTS/SHARED/config/secrets.env`에서 `backend/.env` · Vercel 환경 변수로만 옮겨요 (`.env*`는 `.gitignore`).
2. 화면 글은 한국어 존댓말 "~요", 짧은 문장, 쉬운 말 (어르신 UX, `PROMPTS/SHARED/01_PRODUCT.md` 2절).
3. Next.js는 16이에요. 화면 코드를 쓰기 전에 `frontend/node_modules/next/dist/docs/`의 안내를 먼저 읽어요 (`frontend/AGENTS.md`).
4. **브랜치 (2026-11-21 15:08 사용자 결정, 코드 프리즈 직전):** 원격 브랜치는 `main` 하나뿐이에요. **모든 팀원이 `main`에서 바로 작업**해요 (BE · FE 모두). 새 브랜치를 만들지 않아요. 배포는 `origin/main` 기준이에요: 사용자가 배포를 지시하면 `git pull --ff-only` → `npm run build` · `pytest` · 키 유출 검사 → 서버 · 화면 배포 → `PROMPTS/SHARED/08_DEPLOY.md` 7절. push 전에는 늘 `git pull --ff-only`부터 해요 (다른 팀원의 커밋을 덮지 않게, force push 금지).
