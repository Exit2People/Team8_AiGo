"""장소 DB 상태. 대회 당일은 스냅숏을 쓰고 새로 받지 않아요 (AIGO_SYNC_FREEZE, Vercel은 파일을 못 써요)."""

from app import config
from app.data import places_db


def status() -> dict:
    m = places_db.meta()
    fetched = m.get("fetchedAt")
    stale = True
    if isinstance(fetched, str) and len(fetched) >= 10:
        stale = fetched[:10] != config.now().strftime("%Y-%m-%d")
    return {
        "db": places_db.kind(),
        "fetchedAt": fetched,
        "builtAt": m.get("builtAt"),
        "counts": m.get("counts") or {},
        "inoutBy": m.get("inoutBy") or {},
        "stale": stale,
        "frozen": config.sync_frozen(),
    }


def refresh_in_background() -> None:
    """오늘은 새로 받지 않아요 (자료 고정). 자리만 둬요."""
    return None
