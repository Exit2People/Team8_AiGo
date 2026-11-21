"""외부 HTTP 호출 공통. 오류는 502, 키 없음은 503. 공급자 오류 본문 · 키는 내보내지 않아요."""

import logging

import httpx
from fastapi import HTTPException

from app import config

log = logging.getLogger("aigo.external")

EXTERNAL_FAIL = "외부 서비스에 연결하지 못했어요. 잠시 후 다시 시도해 주세요."
NO_KEY = "해당 서비스의 API 키가 설정되지 않았어요"


def key(name: str) -> str:
    v = config.env(name)
    if not v:
        raise HTTPException(503, NO_KEY)
    return v


def request(method: str, url: str, *, timeout: float = 4.0, fail_detail: str = EXTERNAL_FAIL, **kw) -> dict:
    try:
        with httpx.Client(timeout=timeout) as c:
            r = c.request(method, url, **kw)
        r.raise_for_status()
        data = r.json()
    except httpx.HTTPStatusError as e:
        log.warning("외부 API 상태 %s", e.response.status_code)
        raise HTTPException(502, fail_detail)
    except (httpx.HTTPError, ValueError) as e:
        log.warning("외부 API 오류: %s", type(e).__name__)
        raise HTTPException(502, fail_detail)
    if not isinstance(data, dict):
        raise HTTPException(502, fail_detail)
    return data
