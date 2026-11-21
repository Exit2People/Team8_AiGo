"""라우터: 가까운 역, 구 · 동 목록. 좌표는 계산에만 쓰고 버려요."""

from fastapi import APIRouter, HTTPException, Query

from app.data import geo, loader
from app.schemas import NearbyRequest

router = APIRouter()


@router.post("/stations/nearby")
def nearby_post(body: NearbyRequest):
    return geo.nearby_stations(body.lat, body.lng)


@router.get("/stations/nearby")
def nearby_get(lat: float = Query(...), lng: float = Query(...)):
    return geo.nearby_stations(lat, lng)


@router.get("/districts")
def districts():
    return [d["gu"] for d in loader.districts()]


@router.get("/districts/{gu}/dongs")
def dongs(gu: str):
    for d in loader.districts():
        if d["gu"] == gu:
            return [{"id": x["id"], "name": x["name"]} for x in d["dongs"]]
    raise HTTPException(404, "구를 찾을 수 없어요")


@router.get("/dongs/{dong_id}/stations")
def dong_stations(dong_id: str):
    hit = loader.dong_by_id(dong_id)
    if not hit:
        raise HTTPException(404, "동을 찾을 수 없어요")
    _, dong = hit
    return geo.nearby_stations(dong["lat"], dong["lng"])
