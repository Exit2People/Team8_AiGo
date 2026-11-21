"""닉네임 검사: 형식 → 금지어(갈래별 이유) → Jev(켜졌을 때). 막으면 왜 안 되는지 한 문장으로 알려 줘요.

어떤 낱말 때문인지는 알려 주지 않아요 (피해 가는 표현을 찾지 않게). 갈래만 알려 줘요.
"""

import re
import unicodedata

from app import chat_safety, config

MIN_LEN, MAX_LEN = 2, 8
JEV_TIMEOUT = 1.5
JEV_BLOCK = 0.35

MSG = {
    "empty": "닉네임을 적어 주세요",
    "length": f"닉네임은 {MIN_LEN} ~ {MAX_LEN}자로 지어 주세요",
    "emoji": "이모티콘은 닉네임에 쓸 수 없어요. 한글 · 영어 · 숫자로 지어 주세요",
    "symbol": "기호나 띄어쓰기는 닉네임에 쓸 수 없어요. 한글 · 영어 · 숫자로 지어 주세요",
    "jamo": "완전한 단어로 닉네임을 설정해 주세요 (ㅋ · ㅎ · ㅏ 같은 낱자는 안 돼요)",
    "digits": "숫자만으로는 닉네임을 만들 수 없어요. 글자를 함께 넣어 주세요",
    "욕설": "욕설이나 비방이 감지되어 사용할 수 없는 닉네임이에요",
    "성적": "성적인 표현이 감지되어 사용할 수 없는 닉네임이에요",
    "범죄": "범죄 · 불법과 관련된 말이 감지되어 사용할 수 없는 닉네임이에요",
    "정치": "정치와 관련된 말은 닉네임에 쓸 수 없어요",
    "staff": "운영자로 오해할 수 있는 닉네임은 쓸 수 없어요",
    "jev": "부적절한 뜻으로 읽힐 수 있는 닉네임이에요. 다른 이름을 지어 주세요",
}

_STAFF = ("운영자", "관리자", "운영진", "관리인", "admin", "aigo", "아이고공식", "공식계정")
_EN_SEXUAL = {"pussy", "penis", "vagina", "boobs", "tits", "nipple", "porn", "nude", "naked", "sexy", "milf", "horny", "slut", "whore"}
# 톡방에서는 평범한 말(시발점 · 시발역)이지만 닉네임으로는 우회 표현이라 막아요. 사전 · korcen 둘 다 놓치는 낮춤말도 여기에
_NICK_SWEAR = ("시발", "씨발", "시빨", "등신", "찐따", "애미", "애비", "니미")
# korcen(오픈소스, Apache-2.0) 갈래 → 우리 이유 갈래
_KORCEN_GROUP = {"sexual": "성적", "politics": "정치", "general": "욕설", "minor": "욕설", "belittle": "욕설",
                 "race": "욕설", "parent": "욕설"}
_JAMO = re.compile(r"[ㄱ-ㅎㅏ-ㅣ]")
_OK_CHARS = re.compile(r"[가-힣A-Za-z0-9]+")

JEV_QUESTION = (
    "어르신들이 쓰는 나들이 앱의 닉네임이에요. 이 닉네임이 욕설 · 비하 · 혐오, 성적인 뜻이나 신체 부위, "
    "범죄 · 마약 · 도박, 정치인 · 정당 · 이념을 가리키거나 돌려 말하나요? 초성 · 숫자 섞기 · 한영 키 오타 · 은어로 숨겨도 같은 뜻이면 '예'예요. "
    "평범한 이름 · 별명 · 사물 · 동물 · 꽃 · 동네 이름처럼 흔한 닉네임은 '아니오'예요."
)


def _is_emoji(ch: str) -> bool:
    cp = ord(ch)
    return (unicodedata.category(ch) == "So" or 0x1F000 <= cp <= 0x1FAFF or 0x2600 <= cp <= 0x27BF
            or cp in (0x200D, 0xFE0F))


def _group(text: str) -> str:
    """금지어에 걸린 닉네임의 갈래. 모르면 욕설."""
    t = chat_safety.clean(text)
    cands = {re.sub(r"[\s\W_]+", "", x.lower()) for x in (t, re.sub(r"\d", "", t))}
    for chunk in re.findall(r"[A-Za-z]{3,}", t):
        cands.add(re.sub(r"[\s\W_]+", "", chat_safety.ko_from_keys(chunk)))
    for name in ("성적", "범죄", "정치", "욕설"):
        if any(w in c for c in cands for w in chat_safety.WORD_GROUPS[name]):
            return name
    low = re.sub(r"[^a-z]", "", t.lower().translate(chat_safety._LEET))
    if any(w in low for w in _EN_SEXUAL):
        return "성적"
    return "욕설"


def check_rules(nickname: str | None) -> tuple[str, str] | None:
    """규칙만으로 검사해요. 괜찮으면 None, 막으면 (이유 코드, 안내 문장)."""
    t = chat_safety.clean(nickname or "").strip()
    if not t:
        return "empty", MSG["empty"]
    if any(_is_emoji(ch) for ch in t):
        return "emoji", MSG["emoji"]
    if _JAMO.search(t):
        # 초성 욕(ㅅㅂ · ㅄ …)이면 낱자보다 욕설이 진짜 이유예요
        if any(ch in t for ch in chat_safety._CHOSEONG):
            return "욕설", MSG["욕설"]
        return "jamo", MSG["jamo"]
    if not _OK_CHARS.fullmatch(t):
        return "symbol", MSG["symbol"]
    if not MIN_LEN <= len(t) <= MAX_LEN:
        return "length", MSG["length"]
    if t.isdigit():
        return "digits", MSG["digits"]
    if chat_safety.has_banned_word(t) or any(w in t for w in _NICK_SWEAR):
        g = _group(t)
        return g, MSG[g]
    k = _korcen_group(t)
    if k:
        return k, MSG[k]
    if any(w in t.lower() for w in _STAFF):
        return "staff", MSG["staff"]
    return None


def _korcen_group(t: str) -> str | None:
    """우리 사전이 놓친 것을 korcen으로 한 번 더 봐요 (보지털 · 자지왕 · 개년 …). 없거나 오류면 건너뛰어요."""
    k = _korcen()
    if k is None:
        return None
    for level, group in _KORCEN_GROUP.items():
        try:
            if getattr(k, level)(t):
                return group
        except Exception:
            return None
    return None


_KORCEN: list = []


def _korcen():
    if not _KORCEN:
        try:
            import warnings

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")  # 라이브러리 안의 정규식 경고 숨기기
                from korcen import korcen as k
            _KORCEN.append(k)
        except Exception:
            _KORCEN.append(None)
    return _KORCEN[0]


def check_sync(nickname: str | None) -> tuple[str, str] | None:
    """동기 라우터(스레드에서 돌아요)에서 부를 때."""
    import asyncio

    return asyncio.run(check(nickname))


async def check(nickname: str | None) -> tuple[str, str] | None:
    """규칙 → Jev. Jev가 꺼졌거나 늦거나 실패하면 규칙 결과만 써요 (가입 · 수정이 멈추지 않게)."""
    hit = check_rules(nickname)
    if hit:
        return hit
    if not (config.has_jev_key() and config.nickname_jev_on()):
        return None
    from app.llm import jev

    p = await jev.ask_yes({"닉네임": chat_safety.for_jev(nickname or "")}, JEV_QUESTION, JEV_TIMEOUT)
    if p is not None and p >= JEV_BLOCK:
        return "jev", MSG["jev"]
    return None
