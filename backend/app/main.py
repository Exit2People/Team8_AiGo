import logging
from contextlib import asynccontextmanager

from fastapi import Body, FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from app import config
from app.schemas import Conditions, ForgetRequest, NextRequest, OpenRequest, RecommendRequest
from app.data import external_api, loader, stations_api, sync, weather
from app.routers import auth, game, social

logging.basicConfig(level=logging.INFO)
# httpx는 INFO에서 요청 주소 전체를 찍어요. 기상청 · 서울시 키가 쿼리에 있어서 로그에 키가 남아요 (09_ACCEPTANCE 7.6)
for _noisy in ("httpx", "httpcore"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)



@asynccontextmanager
async def _lifespan(_app):
    # 첫 요청이 AI 라이브러리 불러오기(이 컴퓨터에서 12초 넘게)에 막히지 않게 뒤에서 미리 불러요 (app/llm/warm.py)
    if config.has_ai():
        from app.llm import warm

        warm.start()
    yield


app = FastAPI(title="AI GO", lifespan=_lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins(),
    allow_origin_regex=config.cors_regex() or None,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type"],
    allow_credentials=False,
)

app.include_router(auth.router)
app.include_router(stations_api.router)
app.include_router(external_api.router)
app.include_router(social.router)
app.include_router(game.router)


@app.get("/health")
def health():
    return {
        "ok": True,
        "ai": config.has_ai(),
        "jev": config.has_jev(),
        "model": config.model(),
        "question": config.question_mode(),
        "agent": config.agent_on(),
        "now": config.now().strftime("%Y-%m-%d %H:%M"),
        "weather": weather.current()["weather"],
    }


@app.post("/questions/next")
async def questions_next(body: dict = Body(...)):
    from app.question import flow, service

    try:
        if "conditions" in body:
            req = NextRequest.model_validate(body)
            return flow.next_step(req.conditions, req.answered)
        cond = Conditions.model_validate(body)
    except ValidationError as e:
        raise RequestValidationError(e.errors())
    return await service.next_ai(cond)


@app.post("/questions/open")
async def questions_open(req: OpenRequest):
    from app.question import flow, opening

    cond, filled = await opening.parse_open(req.conditions, req.text)
    return {"conditions": cond.model_dump(), "filled": filled, "heard": opening.heard(cond, filled),
            "next": flow.next_step(cond, [0])}


@app.post("/questions/open/forget")
def questions_forget(req: ForgetRequest):
    from app.question import flow, opening

    cond = opening.forget(req.conditions, req.key, req.value)
    return {"conditions": cond.model_dump(), "heard": opening.heard(cond, cond.filled),
            "next": flow.next_step(cond, [0])}


@app.post("/questions/ai")
async def questions_ai(cond: Conditions):
    from app.question import service

    return await service.ask_ai(cond)


@app.post("/recommend")
async def recommend(req: RecommendRequest):
    from app.recommend.service import recommend as run

    return await run(req.conditions, req.visited, req.shown)


@app.get("/data/status")
def data_status():
    return sync.status()


@app.get("/places/{place_id}/open")
def place_open(place_id: str):
    from app.data.filter_places import open_info

    p = loader.place_by_id(place_id)
    if p is None:
        raise HTTPException(404, "장소를 찾을 수 없어요")
    info = open_info(p, config.now())
    return {"open": info["ok"], "today": info["today"], "lastEntry": info.get("lastEntry")}
