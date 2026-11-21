"""조건 묶음(Conditions)과 요청 모양. 02_ARCHITECTURE 3절 · 03_API_CONTRACT 그대로."""

from typing import Literal

from pydantic import BaseModel, Field

WalkLevel = Literal["제한 없음", "많이", "보통", "조금만", "가장 적게"]


class Origin(BaseModel):
    id: str
    name: str
    type: str = "역"
    lat: float | None = None
    lng: float | None = None


class Range(BaseModel):
    oneWayMin: int = 20
    walk: WalkLevel = "조금만"
    avoid: list[str] = Field(default_factory=list)


class Basic(BaseModel):
    want: str | None = None
    walk: str | None = None
    inout: str | None = None


class AiAnswer(BaseModel):
    q: str
    choices: list[str] = Field(default_factory=list)
    a: str | None = None


class Extra(BaseModel):
    mood: str | None = None
    avoid: list[str] = Field(default_factory=list)
    place: str | None = None
    who: str | None = None
    wish: list[str] = Field(default_factory=list)
    expanded: list[str] = Field(default_factory=list)


class Conditions(BaseModel):
    mode: Literal["text", "voice"] = "text"
    origin: Origin
    body: str | None = None
    time: str | None = None
    range: Range = Field(default_factory=Range)
    basic: Basic = Field(default_factory=Basic)
    ai: list[AiAnswer] = Field(default_factory=list)
    freeText: str | None = None
    extra: Extra = Field(default_factory=Extra)
    filled: list[str] = Field(default_factory=list)
    fallback: bool = False
    exclude: list[str] = Field(default_factory=list)


class NearbyRequest(BaseModel):
    lat: float
    lng: float


class RecommendRequest(BaseModel):
    conditions: Conditions
    visited: list[str] = Field(default_factory=list)
    # 지난 며칠 동안 보여 줬지만 고르지 않은 곳 (화면이 기기에 모아 보내요, 없어도 돼요)
    shown: list[str] = Field(default_factory=list, max_length=60)


class NextRequest(BaseModel):
    conditions: Conditions
    answered: list[int] = Field(default_factory=list)


class OpenRequest(BaseModel):
    conditions: Conditions
    text: str = Field(default="", max_length=500)


class ForgetRequest(BaseModel):
    conditions: Conditions
    key: str
    value: str | None = None


def want_of(cond: Conditions) -> str | None:
    w = cond.basic.want
    return None if w in (None, "", "잘 모르겠어요") else w


def hints_for_ai(cond: Conditions) -> dict:
    out: dict = {}
    if cond.extra.place:
        out["가고 싶은 곳"] = cond.extra.place
    if cond.extra.who:
        out["같이 가는 사람"] = cond.extra.who
    if cond.extra.wish:
        out["하고 싶은 일"] = list(cond.extra.wish)
    if cond.extra.expanded:
        out["넓혀 찾은 말"] = list(cond.extra.expanded)
    return out


def strip_for_ai(cond: Conditions) -> dict:
    """AI로 보내는 유일한 모양. 좌표 · freeText · filled · exclude는 빼요."""
    out = {
        "출발역": cond.origin.name,
        "오늘 컨디션": cond.body,
        "다녀올 시간": cond.time,
        "이동 범위": {
            "편도 상한(분)": cond.range.oneWayMin,
            "걷기": cond.range.walk,
            "피할 것": list(cond.range.avoid),
        },
        "하고 싶은 것": want_of(cond),
        "걷기 답": cond.basic.walk,
        "실내 · 바깥": cond.basic.inout,
        "질문과 답": [{"질문": x.q, "답": x.a or "상관없어요"} for x in cond.ai],
    }
    out.update(hints_for_ai(cond))
    return out
