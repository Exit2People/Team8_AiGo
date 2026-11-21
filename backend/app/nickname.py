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
    "비하": "사람이나 집단을 낮춰 부르는 말이 감지되어 사용할 수 없는 닉네임이에요",
    "staff": "운영자로 오해할 수 있는 닉네임은 쓸 수 없어요",
    "jev": "부적절한 뜻으로 읽힐 수 있는 닉네임이에요. 다른 이름을 지어 주세요",
}

_STAFF = ("운영자", "관리자", "운영진", "관리인", "admin", "aigo", "아이고공식", "공식계정")
_EN_SEXUAL = {"pussy", "penis", "vagina", "boobs", "tits", "nipple", "porn", "nude", "naked", "sexy", "milf", "horny", "slut", "whore"}
# 닉네임 전용 은어 · 낮춤말. 톡방 사전보다 엄격해요 (닉네임은 짧은 낱말 하나로 뜻을 담기 쉬워서).
# 톡방에서는 평범한 말(시발점 · 고추 사러 가요)이라 막지 않는 것도 닉네임에서는 막아요.
NICK_SLANG = {
    "욕설": ("시발", "씨발", "시빨", "시팔", "씨팔", "씨바", "시바", "졸라", "존나", "존니", "좆", "개새", "개색", "개년", "개놈",
             "개같", "개소리", "개빡", "미친", "미췬", "돌아이", "또라이", "병신", "븅", "빙신", "등신", "멍청이", "찐따",
             "지랄", "염병", "호로", "후레", "썅", "쌍놈", "쌍년", "닥쳐", "꺼져", "뒤져", "뒈져", "디져", "죽어", "죽일",
             "애미", "애비", "에미", "에비", "니미", "느금", "엠창", "니애", "느개", "섀끼", "새끼", "쉐끼", "색기", "싸가지",
             "양아치", "쓰레기", "개쓰레기", "엿먹", "꼴통"),
    "성적": ("고추", "꼬추", "잠지", "꼬툭", "보지", "보짓", "자지", "젖", "꼭지", "빨통", "거근", "떡치", "떡방", "섹", "쎅",
             "야동", "야사", "야짤", "음란", "변태", "꼴리", "꼴림", "흥분", "오르가", "정액", "질싸", "노콘", "딸딸", "딸치",
             "자위", "몸캠", "조건만", "원나잇", "섹파", "오피녀", "키스방", "육변기", "걸레", "창녀", "창년", "허벌", "헐벗",
             "알몸", "나체", "누드", "가슴큰", "엉밑", "빠구리", "따먹", "69"),
    "비하": ("한남", "한녀", "김치녀", "된장녀", "맘충", "급식충", "틀딱", "노인네", "늙다리", "꼰대", "홍어", "전라디언",
             "쪽바리", "짱깨", "깜둥", "흑형", "튀기", "장애인", "정신병", "벙어리", "절름발", "난쟁이", "호모", "게이",
             "레즈", "트랜스젠더", "똥꼬충", "급식이", "잼민", "개독", "땡중"),
    "범죄": ("마약", "대마", "필로폰", "히로뽕", "코카인", "도박", "토토", "카지노", "바카라", "슬롯", "사기꾼", "보이스피싱",
             "대포", "살인", "강간", "성폭", "몰카", "조폭", "깡패", "총기", "폭탄", "테러", "납치", "유괴", "작업대출", "리딩방"),
    "정치": ("일베", "메갈", "워마드", "대깨", "개딸", "좌좀", "수꼴", "빨갱", "종북", "토착왜구", "태극기부대", "탄핵",
             "대통령", "국회의원", "민주당", "국힘", "국민의힘", "정의당", "진보당", "좌파", "우파", "극우", "극좌"),
}
# 은어가 들어 있어도 분명히 평범한 낱말은 예외로 둬요 (먼저 지우고 남은 글을 봐요)
NICK_OK = ("고추잠자리", "고추장", "고추밭", "고추꽃", "고춧가루", "풋고추", "청양고추", "홍고추", "꽈리고추", "오이고추",
           "고추전", "고추냉이", "시바견", "시바이누", "수도꼭지", "젖소", "섹션", "슬롯머신", "대포항", "미친듯",
           "토토로", "토토리", "꼭지점", "꼭짓점", "도박사의", "대마도", "개새우", "정액제", "젖병",
           "꼰대리", "게이트", "게이지", "섹터", "색소폰", "호로록", "후레쉬", "새끼고양이",
           "새끼강아지", "새끼오리", "호모사피엔스", "마약김밥", "마약떡볶이")
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
    if chat_safety.has_banned_word(t):
        g = _group(t)
        return g, MSG[g]
    g = slang_group(t)
    if g:
        return g, MSG[g]
    rest = t
    for ok in NICK_OK:
        rest = rest.replace(ok, "")
    k = _korcen_group(rest) if rest else None  # 예외 낱말(새끼고양이 …)은 지우고 korcen에 넘겨요
    if k:
        return k, MSG[k]
    if any(w in t.lower() for w in _STAFF):
        return "staff", MSG["staff"]
    return None


def _forms(t: str) -> set[str]:
    """숫자 끼우기(고1추) · 한영 키 오타(rhcn) · 대소문자를 풀어 같은 글 여러 모양으로 봐요."""
    low = t.lower()
    out = {low, re.sub(r"\d", "", low)}
    for chunk in re.findall(r"[a-z]{2,}", low):
        out.add(re.sub(r"[a-z]{2,}", chat_safety.ko_from_keys(chunk), low, count=1))
    return out


def slang_group(t: str) -> str | None:
    for form in _forms(t):
        rest = form
        for ok in NICK_OK:
            rest = rest.replace(ok, "")
        for name in ("성적", "범죄", "정치", "비하", "욕설"):
            if any(w in rest for w in NICK_SLANG[name]):
                return name
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
