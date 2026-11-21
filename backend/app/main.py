import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app import config
from app.data import external_api, loader, stations_api, sync, weather
from app.routers import auth, game, social

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="AI GO")

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
