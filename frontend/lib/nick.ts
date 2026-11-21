/**
 * 닉네임을 비워 두고 가입했을 때 지어 주는 이름.
 * 가입 규칙(2 ~ 8자, 한글 · 영어 · 숫자)에 맞게 '꾸밈말(3자) + 이름(2자) + 숫자 2자리' = 7자로 만들어요. 예: 포근한햇살27
 */
const ADJ = ["포근한", "씩씩한", "느긋한", "상냥한", "다정한", "산뜻한", "든든한", "명랑한", "향긋한", "말랑한"];
const NOUN = ["햇살", "솔잎", "바람", "구름", "꽃잎", "나비", "들꽃", "단풍", "노을", "산새", "물결", "별빛"];

const pick = <T,>(a: T[]) => a[Math.floor(Math.random() * a.length)];

export function randomNick(): string {
  return `${pick(ADJ)}${pick(NOUN)}${String(Math.floor(Math.random() * 90) + 10)}`;
}

/** 가입 규칙에 맞는 닉네임인지 */
export const isNick = (s: string) => /^[가-힣A-Za-z0-9]{2,8}$/.test(s);

/**
 * 형식 문제를 입력하는 동안 바로 알려 줘요 (서버 app/nickname.py와 같은 문장).
 * 욕설 · 성적 · 범죄 · 정치 같은 내용은 서버가 검사해서 이유를 돌려줘요 (`nicknameCheck` · 저장할 때).
 * 괜찮으면 null.
 */
export function nickProblem(raw: string): string | null {
  const s = raw.trim();
  if (!s) return "닉네임을 적어 주세요";
  if (/\p{Extended_Pictographic}|‍|️/u.test(s)) return "이모티콘은 닉네임에 쓸 수 없어요. 한글 · 영어 · 숫자로 지어 주세요";
  if (/[ㄱ-ㅎㅏ-ㅣ]/.test(s)) return "완전한 단어로 닉네임을 설정해 주세요 (ㅋ · ㅎ · ㅏ 같은 낱자는 안 돼요)";
  if (!/^[가-힣A-Za-z0-9]+$/.test(s)) return "기호나 띄어쓰기는 닉네임에 쓸 수 없어요. 한글 · 영어 · 숫자로 지어 주세요";
  if (s.length < 2 || s.length > 8) return "닉네임은 2 ~ 8자로 지어 주세요";
  if (/^\d+$/.test(s)) return "숫자만으로는 닉네임을 만들 수 없어요. 글자를 함께 넣어 주세요";
  return null;
}
