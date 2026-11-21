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
