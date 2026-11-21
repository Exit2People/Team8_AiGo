"""톡방 글 안전 검사 (3겹): 글자 규칙 → Jev(켜졌을 때) → Jev 실패면 보냄. 글은 저장 · 로그하지 않아요."""

import re

from app import config

JEV_TIMEOUT = 1.5
JEV_BLOCK = 0.35

JEV_QUESTION = "어르신들이 처음 만나 쓰는 동네 나들이 톡방의 글이에요. 이 글이 아래 가운데 하나라도 하고 있나요? 직접 쓰지 않고 돌려 말하거나, 초성(ㅅㅂ 등) · 숫자나 기호 섞기 · 한영 키 오타(tlqkf 등) · 은어 · 비꼬기 · 암시로 말해도 같은 뜻이면 '예'예요. 성적인 은어 · 신체 부위 낱말(예: 야스 · 뷰지 · 유륜 · 빗치)은 하나만 써도 '예'예요. ① 욕설 · 모욕 · 비하(나이 · 성별 · 지역 · 장애 비하어 포함) ② 성희롱 · 성적인 말이나 암시, 단둘이 은밀한 만남 · 신체 · 속옷 이야기 ③ 마약 · 도박 · 불법 대출 · 투자 리딩방 · 고수익 권유 · 개인 연락처나 돈 요구 같은 사기성 권유 ④ 정치 이야기: 정당 · 정치인 · 대통령 · 이념을 두고 하는 의견 · 지지 · 반대 · 비하 · 선동, 투표 권유 (선거 날 길이 막힌다는 식의 담담한 사실은 아니에요) ⑤ 위협 · 폭력 암시, 범죄 · 불법(마약 · 도박 · 성매매 · 대포통장 · 사기) ⑥ 술(소주 · 맥주 · 막걸리 · 한잔 등)을 같이 마시자는 권유 ⑦ 따로 · 단둘이 만나자는 말, 데이트 신청, 데리러 가겠다는 말, 전화번호 · 카톡 아이디 등 연락처를 묻거나 주고받자는 말. 고추 · 꼬추 · 바나나처럼 남성 신체를 가리키는 은어로 쓴 말(예: 고추 크네요 · 큰 고추)도 성적인 말이에요. 다만 장 보기 · 요리 · 채소 이야기는 아니에요. ⑧ 자기 집으로 오라 · 놀러 오라는 초대 ⑨ 돈을 빌려 달라 · 보내 달라는 부탁, 송금 · 계좌 이야기. 평범한 일상 대화 · 길 안내 · 날씨 · 몸 상태 · 감정 표현 · 뉴스를 담담하게 말하는 것, '따로 앉을게요' · '먼저 갈게요'처럼 혼자 하겠다는 말, 버스 · 출구 번호를 묻는 말, '뉴스 보니 국회가 시끄럽던데요'처럼 편을 들지 않고 소식만 전하는 말, '바보같이 길을 잃었어요'처럼 자기 자신을 가볍게 탓하는 말, '엿 먹어 보세요 맛있어요'처럼 음식 이야기는 '아니오'예요."
JEV_CONTEXT_QUESTION = "'새 글'을 같은 사람이 바로 앞에 쓴 글들('내 앞 글')과 이어서 읽으면, 아래 부적절한 내용이 완성되거나 이어지나요? 글자 · 말을 나눠 쓴 것(앞 글 '씨' + 새 글 '발', 앞 글 '몸매가' + 새 글 '좋으시네요')도 포함해요. 욕설 · 비하, 성희롱 · 성적 암시(몸매 · 신체 평가 포함), 술 권유, 따로/단둘이 만남 · 데이트 · 연락처 요구, 불법 · 사기 권유, 정치 비하 · 선동 · 투표 권유, 위협. '다른 사람 앞 글'은 흐름을 이해하는 데만 쓰고, 그 사람이 한 말 때문에 '예'라고 하지 마세요. 앞 글과 이어 봐도 평범한 대화면 '아니오'예요."

_WORDS_TEXT = """씨발 씨빨 씨바 시벌 썅 좆 존나 병신 븅신 개새끼 개새기 지랄 미친놈 미친년 또라이 느금마 느금 느그엄마 느그애미 니애미 니애비 엠창 틀딱 한남충 김치녀 맘충 급식충 장애인새끼 애자새끼
씹새 씹년 씹놈 씹창 시부랄 시바새 니미럴 염병 썅년 썅놈 개놈 개새 병1신 븅딱 등신새 엿같 뒤져라 뒤질래 디져라 패버린 닥쳐 빗치 빗취 비치년 뷔치 쌍년 쌍놈 걸레년 화냥 창녀 갈보 보슬아치
섹스 야동 가슴사진 몸사진 알몸사진 뷰지 뷔지 뵤지 보g 봊 보짓 잦이 자g 좆물 꼬추 꼬툭 섹하 섹할 쎅스 떡치자 떡칠래 떡치고싶 응응하자 붕가붕가 유륜 젖꼭지 젖가슴 젖탱 젖통 젖소부인 노브라 브라끈 똥꼬 발기돼 발기했 질싸 자위하 딸딸이 딸치 따먹고싶 따먹자 박아줄 박고싶 박히고싶 꼴려 꼴리 만져줄 핥아줄 알몸 나체 누드사진 원나잇 조건만남 섹파 오피녀 키스방 모텔가자 모텔갈래 여관가자 야짤 음란 변태
대마초 필로폰 마약팝니다 토토사이트 불법도박 작업대출 리딩방 대포통장 대포폰 명의대여 명의빌려 통장대여 통장빌려 통장삽니다 통장팝니다 통장판매 보이스피싱 카지노사이트 바카라 슬롯사이트 사설토토 성매매 몸캠 출장안마 코카인 케타민 엑스터시 아이스팝니다 작대기팝니다 졸피뎀 총기판매 위조지폐 개인정보팝니다 해킹해드
빨갱이 수꼴 좌좀 토착왜구 민주당 더불어민주 국민의힘 국힘 조국혁신당 개혁신당 정의당 진보당 새누리 자유한국당 좌파 우파 종북 친일파 수구꼴통 극우 극좌 일베 대깨문 개딸 태극기부대 탄핵"""
_WORDS = _WORDS_TEXT.split()
# 줄마다 갈래가 달라요 (닉네임 거절 이유를 알려 줄 때 써요): 욕설 · 비하 2줄 → 성적 → 범죄 · 불법 → 정치
_LINES = [ln.split() for ln in _WORDS_TEXT.splitlines()]
WORD_GROUPS = {"욕설": _LINES[0] + _LINES[1], "성적": _LINES[2], "범죄": _LINES[3], "정치": _LINES[4]}
_EN = "fuck shit bitch biatch bastard pussy penis vagina boobs tits nipple porn nude naked sexy milf horny slut whore".split()
_EN_VARIANTS = ["fvck", "phuck", "fcuk", "fck", "btch"]
_CHOSEONG = ["ㅅㅂ", "ㅆㅂ", "ㅂㅅ", "ㅄ", "ㅈㄹ", "ㅈㄴ", "ㅁㅊ", "ㄲㅈ", "ㄴㄱㅁ", "ㅅㄲ", "ㄱㅅㄲ"]

_PATTERNS = [re.compile(p) for p in [
    r"(씨|쒸|ㅆ)[\W\d_a-z이으]*(발|빨|벌)",
    r"(몸매|가슴|엉덩이|허벅지|각선미)\s*(이|가|은|는|도)?\s*(참|정말|너무|진짜)?\s*(좋으|좋네|좋아요|예쁘|이쁘|착하|섹시|죽이|크시|크네|빵빵|탱탱|글래머)",
    r"시[\W\d_a-z]+(발|빨|벌)",
    r"(?<!\d)18\s*(놈|년|새|진짜|같|아|롬|련)",
    r"십팔\s*(놈|년|새)",
    r"(?<![ㄱ-ㅣ가-힣])ㅗ+(?![ㄱ-ㅣ가-힣])|🖕",
    r"dick(?!ens|inson)",
    r"기호\s*\d+\s*번",
    r"\d+\s*번\s*(을|를)?\s*(꼭|무조건|다|만)?\s*(찍어야|찍자|찍읍시다|찍으세요|뽑아야|뽑자|뽑읍시다|뽑으세요)",
    r"투표\s*(하세요|합시다|해야|해\s*주세요|꼭\s*하)",
    r"야스(?!쿠니)",
    r"(?<![ㄱ-ㅎ])ㅅㅅ(하|할|ㄱ)",
    r"(술|소주|맥주|막걸리|와인|양주|한잔|한병)\s*(을|를|이나|도|좀)?\s*(하러|마시러|먹으러|어때|어떠|해요|해용|할래|하실|가실|드실|하자|합시다|마셔요|마실래|마시자|땡기|콜|ㄱㄱ|고고|사\s*드릴|살게)",
    r"(단둘이|둘이서?만)\s*(만나|보|한잔|가)|따로\s*(만나|보자|봐요|볼래|데이트|연락|한잔)|데이트|데리러\s*(갈|가|올)",
    r"(전화번호|폰번호|핸드폰번호|휴대폰번호|연락처|카톡|카카오톡|아이디|라인\s*아이디|인스타)\s*(좀|를|을|이|는)?\s*(알려|주세요|줘|줄래|주실|뭐|교환|남겨|찍어|불러|있으세요|있어요\?|어떻게)",
    r"(번호|연락처)\s*(좀)?\s*(따|교환|주고받)",
    # 집으로 부르기 (어르신을 노린 만남 유도): '우리 집에 놀러 와요' · '제 집으로 오세요'. '집에 가서 쉴게요'는 통과
    r"(우리|제|내|저희)\s*집\s*(에|으로|에서)?\s*(한번|한 번|같이)?\s*(놀러|오세요|와요|와\s*요|오실래|올래|오셔|초대)",
    r"집에\s*(한번|한 번)?\s*놀러\s*(와|오|가자|갈래)",
    # 돈 빌려 달라 · 보내 달라 (사기): '돈 좀 빌려줄 수 있어요' · '5만 원만 보내 주세요' · '계좌번호 알려 드릴게요'
    r"(돈|현금|용돈|\d+\s*(만|천)\s*원|만\s*원|천\s*원)\s*(만|좀|이|을|를)?\s*(빌려|꿔|보내|부쳐|송금|입금)",
    r"(송금|입금)\s*(해|좀|부탁)|계좌\s*(번호|로)",
    r"(?<!버스\s)(?<!버스)(?<!출구\s)(?<!출구)(?<!노선\s)(?<!노선)(?<!몇\s)(?<!몇)(?<!방\s)(?<!방)(번호|연락처|010)\s*(좀|를|을)?\s*(알려|주세요|주시면|줘요|줄래|주실|남겨|드릴게|드려요)",
]]
_NUM_SOUND = [re.compile(p) for p in [
    r"(?<![\d가-힣])(씨|ㅆ|ㅅ)\s*8(?![\d분시층호번개명원살월일년초편권장곡쪽])",
    r"(?<![\d가-힣])시8(?=$|\s|[!?.~ㅋㅎ]|새|놈|년|진짜)",
    r"(?<!\d)10\s*(새끼|새기|새퀴|색기)",
    r"개18(?![\d마살개명세키]|kg)",
]]
_LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "8": "b", "@": "a", "$": "s", "!": "i"})
_INVISIBLE = re.compile("[​-‏⁠﻿­]")
_FOR_JEV = [("시발점", "출발점"), ("시발역", "출발역"), ("시발택시", "옛날 택시"), ("마약김밥", "꼬마김밥"),
            ("마약 김밥", "꼬마김밥"), ("마약옥수수", "버터옥수수"), ("마약 옥수수", "버터옥수수"),
            ("마약떡볶이", "떡볶이"), ("마약 떡볶이", "떡볶이"), ("마약빵", "빵"), ("마약 빵", "빵")]

# 두벌식 자판
_KEY = {"q": "ㅂ", "w": "ㅈ", "e": "ㄷ", "r": "ㄱ", "t": "ㅅ", "y": "ㅛ", "u": "ㅕ", "i": "ㅑ", "o": "ㅐ", "p": "ㅔ",
        "a": "ㅁ", "s": "ㄴ", "d": "ㅇ", "f": "ㄹ", "g": "ㅎ", "h": "ㅗ", "j": "ㅓ", "k": "ㅏ", "l": "ㅣ", "z": "ㅋ",
        "x": "ㅌ", "c": "ㅊ", "v": "ㅍ", "b": "ㅠ", "n": "ㅜ", "m": "ㅡ", "Q": "ㅃ", "W": "ㅉ", "E": "ㄸ", "R": "ㄲ",
        "T": "ㅆ", "O": "ㅒ", "P": "ㅖ"}
_CHO = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
_JUNG = ["ㅏ", "ㅐ", "ㅑ", "ㅒ", "ㅓ", "ㅔ", "ㅕ", "ㅖ", "ㅗ", "ㅘ", "ㅙ", "ㅚ", "ㅛ", "ㅜ", "ㅝ", "ㅞ", "ㅟ", "ㅠ", "ㅡ", "ㅢ", "ㅣ"]
_JONG = ["", "ㄱ", "ㄲ", "ㄳ", "ㄴ", "ㄵ", "ㄶ", "ㄷ", "ㄹ", "ㄺ", "ㄻ", "ㄼ", "ㄽ", "ㄾ", "ㄿ", "ㅀ", "ㅁ", "ㅂ", "ㅄ", "ㅅ", "ㅆ",
         "ㅇ", "ㅈ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ"]
_VV = {("ㅗ", "ㅏ"): "ㅘ", ("ㅗ", "ㅐ"): "ㅙ", ("ㅗ", "ㅣ"): "ㅚ", ("ㅜ", "ㅓ"): "ㅝ", ("ㅜ", "ㅔ"): "ㅞ", ("ㅜ", "ㅣ"): "ㅟ",
       ("ㅡ", "ㅣ"): "ㅢ"}
_CC = {("ㄱ", "ㅅ"): "ㄳ", ("ㄴ", "ㅈ"): "ㄵ", ("ㄴ", "ㅎ"): "ㄶ", ("ㄹ", "ㄱ"): "ㄺ", ("ㄹ", "ㅁ"): "ㄻ", ("ㄹ", "ㅂ"): "ㄼ",
       ("ㄹ", "ㅅ"): "ㄽ", ("ㄹ", "ㅌ"): "ㄾ", ("ㄹ", "ㅍ"): "ㄿ", ("ㄹ", "ㅎ"): "ㅀ", ("ㅂ", "ㅅ"): "ㅄ"}
_CC_SPLIT = {v: k for k, v in _CC.items()}


def _compose(jamos: list[str]) -> str:
    out = []
    cho = jung = jong = None

    def flush():
        nonlocal cho, jung, jong
        if cho and jung:
            out.append(chr(0xAC00 + (_CHO.index(cho) * 21 + _JUNG.index(jung)) * 28 + _JONG.index(jong or "")))
        else:
            out.extend(x for x in (cho, jung) if x)
        cho = jung = jong = None

    for j in jamos:
        is_v = j in _JUNG
        if not is_v:
            if cho and jung:
                if jong is None and j in _JONG:
                    jong = j
                elif jong and (jong, j) in _CC:
                    jong = _CC[(jong, j)]
                else:
                    flush(); cho = j
            elif cho and not jung:
                flush(); cho = j
            else:
                cho = j
        else:
            if cho and jung and jong:
                if jong in _CC_SPLIT:
                    a, b = _CC_SPLIT[jong]
                    jong = a; flush(); cho = b
                else:
                    nxt = jong; jong = None; flush(); cho = nxt
                jung = j
            elif cho and jung:
                if (jung, j) in _VV:
                    jung = _VV[(jung, j)]
                else:
                    flush(); out.append(j)
            elif cho:
                jung = j
            else:
                out.append(j)
    flush()
    return "".join(out)


def ko_from_keys(chunk: str) -> str:
    return _compose([_KEY.get(ch, _KEY.get(ch.lower(), ch)) for ch in chunk])


def clean(text: str) -> str:
    t = "".join(chr(ord(c) - 0xFEE0) if 0xFF01 <= ord(c) <= 0xFF5E else c for c in text or "")
    return _INVISIBLE.sub("", t)


def _squash(t: str) -> str:
    return re.sub(r"[\s\W_]+", "", t.lower())


# 톡방 은어 표: 닉네임 은어 표(app/nickname.py)에서 문장 속에서도 뜻이 하나뿐인 것만 골랐어요.
# 마약 · 도박 · 장애인 · 노인네 · 홍어 · 미친 · 꺼져처럼 평범한 문장에 흔한 말은 넣지 않아요 (Jev가 문맥으로 봐요)
CHAT_SLANG = {
    "성적": ("빨통", "육변기", "딸딸이", "딸치", "섹파", "섹시", "쎅시", "야짤", "꼴리", "꼴림", "질싸", "노콘", "정액",
             "거근", "따먹", "빠구리", "허벌", "보지털", "보짓", "자지털", "젖꼭지", "젖가슴", "오르가즘", "자위"),
    "욕설": ("졸라", "존니", "씨팔", "시팔", "개색", "개년", "호로새", "후레자식", "찐따", "등신", "싸가지", "섀끼", "쉐끼",
             "애미", "니미", "느개비", "개소리", "개빡"),
    "비하": ("한남", "한녀", "된장녀", "늙다리", "짱깨", "쪽바리", "깜둥", "잼민", "개독", "땡중", "똥꼬충", "정신병자"),
    "범죄": ("히로뽕", "작대기", "떨액", "대포폰", "보이스피싱"),
}
# 은어와 글자가 겹치는 평범한 말 (먼저 지우고 봐요)
CHAT_OK = ("등신대", "섹시하게 차려입", "자위대", "젖꼭지모양", "졸라맨", "작대기 하나", "작대기로", "한남동", "한남대교", "한남역",
           "한녀석", "애미야", "개색깔", "정액제", "정액권", "정액요금")


def _slang_hit(sq: str) -> bool:
    for ok in CHAT_OK:
        sq = sq.replace(ok.replace(" ", ""), "")
    return any(w in sq for ws in CHAT_SLANG.values() for w in ws)


# '고추'는 채소 이야기(고추 사러 가요 · 청양고추)가 흔해서 낱말로는 막지 않고, 은어로 쓴 꼴만 막아요
_ALONE = re.compile(r"(고추|꼬추)[ㅋㅎ]*")  # 그 말만 보낸 글
_GOCHU = [re.compile(p) for p in [
    r"(내|니|네|너|너의|당신|그쪽|오빠|아저씨|형님|자기)\s*(꺼|거|것)?\s*(고추|꼬추)",
    r"(고추|꼬추)\s*(가|를|는|좀|이|도)?\s*(섰|서\s*요|세웠|세워|만져|만지|보여|봐\s*줄|빨|꼴|딱딱|흔들|커졌|크게\s*해)",
]]


def _rule_hit(text: str) -> bool:
    low = text.lower()
    sq = _squash(text)
    if any(w in sq for w in _WORDS):
        return True
    if _ALONE.fullmatch(sq) or any(p.search(low) for p in _GOCHU) or _slang_hit(sq):
        return True
    for ch in _CHOSEONG:
        if re.search(rf"(?<![ㄱ-ㅎ]){ch}(?![ㄱ-ㅎ])", text):
            return True
    if any(p.search(low) for p in _PATTERNS):
        return True
    for chunk in re.findall(r"[A-Za-z]{3,}", text):
        ko = _squash(ko_from_keys(chunk))
        if any(w in ko for w in [*_WORDS, "시발", "시바", "ㅅㅂ"]) or _ALONE.fullmatch(ko):
            return True
    return False


def has_banned_word(text: str) -> bool:
    t = clean(text)
    if _rule_hit(t):
        return True
    if any(p.search(t) for p in _NUM_SOUND):
        return True
    sq = _squash(t)
    if re.search(r"\d", t):
        if _rule_hit(re.sub(r"\d", "", t)):
            return True
        leet = re.sub(r"[\s_]+", "", t.lower()).translate(_LEET)
        leet = re.sub(r"[^a-z]", "", leet)
        if any(w in leet for w in [*_EN, *_EN_VARIANTS]):
            return True
    if any(w in sq for w in [*_EN, *_EN_VARIANTS]):
        return True
    return False


def for_jev(text: str) -> str:
    t = clean(text)
    for a, b in _FOR_JEV:
        t = t.replace(a, b)
    if re.search(r"[가-힣a-zA-Z]\d+[가-힣a-zA-Z]", t):
        t += f" (숫자를 빼면: {re.sub(r'(?<=[가-힣a-zA-Z])\d+(?=[가-힣a-zA-Z])', '', t)})"
    return t


async def is_blocked(text: str, mine: list[str] | None = None, others: list[str] | None = None) -> bool:
    from app.llm import jev

    mine = (mine or [])[-3:]
    others = (others or [])[-3:]
    if has_banned_word(text):
        return True
    if mine and has_banned_word("".join([*mine, text])):
        return True
    if not (config.has_jev_key() and config.chat_jev_on()):
        return False
    if mine or others:
        state = {"내 앞 글": [for_jev(x) for x in mine], "다른 사람 앞 글": [for_jev(x) for x in others],
                 "새 글": for_jev(text)}
        qs = {"msg": JEV_QUESTION, "ctx": JEV_CONTEXT_QUESTION}
    else:
        state = {"채팅 글": for_jev(text)}
        qs = {"msg": JEV_QUESTION}
    res = await jev.ask_many(state, qs, JEV_TIMEOUT)
    if res is None:
        return False
    return max(res.values()) >= JEV_BLOCK
