# Team8_AiGo — AI GO (아이고)

서울 어르신에게 오늘 나들이 장소 한 곳을 골라 드리는 웹앱이에요.

| 구분 | 주소 |
|---|---|
| 화면 (제출용) | https://ai-go-team8.vercel.app |
| 서버 | https://ai-go-api.vercel.app |

## 구조

```
휴대폰 브라우저 → Next.js 16 (Vercel, 화면) → FastAPI (Vercel 서버리스, 서버) → Claude · 서울시 · TMAP · 카카오 API
                                  └ /api/* (로그인 · 게임) 는 화면 주소로 받아 서버로 넘겨요 (쿠키)
```

## 기술 스택

| 부분 | 쓰는 것 |
|---|---|
| 화면 | Next.js 16, React 19, TypeScript |
| 서버 | Python 3.12, FastAPI, uv |
| AI | Claude (질문 · 추천 · 첫 말 읽기), TypeSafe Jev (추천 이유 · 톡방 글 확인) |
| LangGraph | **질문 에이전트**: 운영에서 켬. **추천 에이전트**: 코드는 있지만 꺼 둠 (`AIGO_AGENT=0`) — 실측 한 번 호출 4.5초 vs 에이전트 8.0초라 운영 추천은 Claude 한 번 → 검증 → 실패면 규칙 점수 |
| DB | PostgreSQL (Neon: 계정 · 톡방 · 방명록 · 랭킹), 장소는 SQLite 스냅숏 |

## 장소 자료 (시연 기준 하나)

`data/snapshot/aigo.db` — **650곳** (공원 110 · 박물관 154 · 미술관 37 · 시장 144 · 행사 205), 2026-11-18 수집.
원본 공원 132곳 가운데 역에서 가깝고 좌표가 맞는 110곳을 써요. 행사 수는 날마다 바뀌어요.

## 실행

```
cd backend && uv sync && uv run uvicorn app.main:app --port 8010
cd backend && uv run pytest -q
cd frontend && npm ci && npm run dev
```

결정 기록은 `docs/DECISIONS.md`에 있어요.
