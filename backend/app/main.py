from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import config

app = FastAPI(title="AI GO")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins(),
    allow_origin_regex=config.cors_regex() or None,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type"],
    allow_credentials=False,
)


@app.get("/health")
def health():
    return {
        "ok": True,
        "ai": config.has_ai(),
        "jev": config.has_jev(),
        "model": config.model(),
        "question": config.env("AIGO_QUESTION", "graph"),
        "agent": config.flag("AIGO_AGENT"),
    }
