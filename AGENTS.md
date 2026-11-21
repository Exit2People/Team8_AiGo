# AGENTS.md — AI GO 저장소 (Codex · Gemini · 모든 코딩 에이전트 공통)

> `CLAUDE.md`와 같은 규칙이에요. Claude가 아닌 에이전트도 이 파일을 따라요.
> 하위 폴더에 `AGENTS.md`가 또 있으면 (예: `frontend/AGENTS.md`) 그 폴더에서는 둘 다 따라요.

## 무엇인가요
- AI GO(아이고): 어르신이 "오늘 어디 갈지"를 질문 몇 개로 정하면, 서울의 갈 곳 한 곳을 추천 티켓으로 보여 주는 서비스예요.
- `backend/` FastAPI (Python, `uv`), `frontend/` Next.js 16, `data/` 장소 스냅숏 · 기준 자료, `docs/` 결정 · 메모.
- 지금까지 정한 것은 `docs/DECISIONS.md`, 서버 · 화면 줄 메모는 `docs/LANE_NOTES_BE.md` · `docs/LANE_NOTES_FE.md`에 있어요. 작업 전에 읽어요.

## 절대 안 해요
1. 키 · DB 주소 · 비밀번호를 출력하거나 커밋하지 않아요. `.env*` 파일은 커밋하지 않아요 (`.env.example`만 예외).
2. 운영 DB(`aigo-testton`, `DATABASE_URL`)에 시험 데이터를 쓰지 않아요. 테스트는 `backend/tests/fakedb.py`를 써요.
3. force push, 브랜치 지우기를 하지 않아요. **push는 하지 않아요** (메인 담당이 합치고 push해요).
4. 자기에게 맡겨진 폴더 · 브랜치 밖의 파일을 고치지 않아요.
5. `TASK.md`는 커밋하지 않아요 (작업 지시서예요).

## 늘 지킬 것
1. 화면 글과 AI가 어르신에게 하는 말은 한국어 존댓말 "~요", 짧은 문장, 쉬운 말이에요.
2. 화면과 서버 사이의 모양(API 응답 칸)은 **칸을 더하는 것만** 돼요. 칸을 빼거나 이름을 바꾸지 않아요.
3. AI가 늦거나 실패해도 응답은 늘 나와야 해요 (규칙 · 기본 질문으로 대신).
4. AI에는 좌표 · 동 주소를 보내지 않아요. 출발지는 이름만 보내요.
5. 커밋은 기능별로 나눠요. 메시지는 `feat(backend): …` 처럼 한국어로 짧게.

## 서버 실행 · 시험
```bash
cd backend
uv sync
uv run pytest -q                       # 키 · DB 없이 돌아요
uv run uvicorn app.main:app --port 8010 # 로컬 서버
```
- 키가 없으면 AI 부분은 규칙 · 기본 질문으로 돌아가요. 키는 `backend/.env`에만 넣어요 (`backend/.env.example` 참고).
