"""라우터: 날씨 · 카카오 장소 검색 · 문화행사 · 도보 경로 · 지도 설정."""

from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app import config
from app.data import external, weather

router = APIRouter()

KAKAO_SEARCH = "https://dapi.kakao.com/v2/local/search/keyword.json"
TMAP_WALK = "https://apis.openapi.sk.com/tmap/routes/pedestrian?version=1"


@router.get("/weather")
def get_weather(lat: float = Query(37.5665, ge=33, le=39), lng: float = Query(126.978, ge=124, le=132)):
    return weather.current(lat, lng)


@router.get("/places/search")
def places_search(query: str = Query(..., min_length=1, max_length=100), page: int = Query(1, ge=1, le=45)):
    k = external.key("KAKAO_REST_API_KEY")
    data = external.request(
        "GET", KAKAO_SEARCH, params={"query": query, "page": page, "size": 15},
        headers={"Authorization": f"KakaoAK {k}"}, fail_detail="장소 검색 응답을 확인할 수 없어요",
    )
    if not isinstance(data.get("documents"), list) or not isinstance(data.get("meta"), dict):
        raise HTTPException(502, "장소 검색 응답을 확인할 수 없어요")
    return {"places": data["documents"], "meta": data["meta"], "source": "kakao"}


@router.get("/events")
def events(start: int = Query(1, ge=1, le=100000), size: int = Query(20, ge=1, le=100)):
    k = external.key("SEOUL_OPENAPI_KEY")
    fail = "서울시 문화행사 정보를 가져오지 못했어요"
    url = f"http://openapi.seoul.go.kr:8088/{quote(k, safe='')}/json/culturalEventInfo/{start}/{start + size - 1}/"
    data = external.request("GET", url, timeout=4.0, fail_detail=fail)
    body = data.get("culturalEventInfo")
    if body is None:
        code = (data.get("RESULT") or {}).get("CODE")
        if code == "INFO-200":
            return {"events": [], "total": 0, "source": "seoul"}
        raise HTTPException(502, fail)
    code = (body.get("RESULT") or {}).get("CODE")
    if code == "INFO-200":
        return {"events": [], "total": 0, "source": "seoul"}
    if code != "INFO-000":
        raise HTTPException(502, fail)
    return {"events": body.get("row") or [], "total": body.get("list_total_count") or 0, "source": "seoul"}


class Point(BaseModel):
    lat: float = Field(ge=33, le=39)
    lng: float = Field(ge=124, le=132)


class WalkRequest(BaseModel):
    start: Point
    end: Point


@router.post("/routes/walking")
def walking(body: WalkRequest):
    k = external.key("TMAP_APP_KEY")
    fail = "도보 경로를 찾지 못했어요"
    payload = {
        "startX": body.start.lng, "startY": body.start.lat, "endX": body.end.lng, "endY": body.end.lat,
        "startName": quote("출발"), "endName": quote("도착"),
        "reqCoordType": "WGS84GEO", "resCoordType": "WGS84GEO", "searchOption": "0",
    }
    data = external.request("POST", TMAP_WALK, json=payload, headers={"appKey": k}, fail_detail=fail)
    feats = data.get("features")
    try:
        props = feats[0]["properties"]
        return {
            "distanceM": int(props["totalDistance"]), "totalSeconds": int(props["totalTime"]),
            "features": feats, "source": "tmap",
        }
    except (TypeError, KeyError, IndexError, ValueError):
        raise HTTPException(502, fail)


@router.get("/maps/config")
def maps_config():
    js = config.env("KAKAO_JS_KEY")
    if not js:
        return {"enabled": False, "sdkUrl": None}
    return {"enabled": True, "sdkUrl": f"https://dapi.kakao.com/v2/maps/sdk.js?appkey={js}&autoload=false"}
