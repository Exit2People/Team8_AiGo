"""AI에 보내기 전 개인정보처럼 보이는 말을 "[지움]"으로 바꿔요."""

import re

MASK = "[지움]"

# 순서가 중요해요: 주민번호 → 휴대폰 → 유선 → 메일 → 도로명 주소
_RULES = [re.compile(p) for p in [
    r"\d{6}\s?-?\s?[1-4]\d{6}",
    r"01[016789][\s.\-]?\d{3,4}[\s.\-]?\d{4}",
    r"0\d{1,2}[\s.\-]\d{3,4}[\s.\-]\d{4}",
    r"[\w.+\-]+@[\w\-]+\.[\w.\-]+",
    # 숫자 뒤 '가'는 지명이라 남겨요 (종로3가 · 을지로 3가)
    r"\S+(?:로|길)\s?\d+(?:-\d+)?(?![\d가])(?:번길)?(?:\s\d+호)?",
]]


def scrub_pii(text: str | None) -> str | None:
    if not text:
        return text
    for r in _RULES:
        text = r.sub(MASK, text)
    return text
