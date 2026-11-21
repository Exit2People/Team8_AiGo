/** 사진 대체 일러스트 (11_FRONTEND_SPEC 15절) */
const WIDE: [string, string[]][] = [
  ["wide_park", ["공원", "숲"]],
  ["wide_palace", ["고궁", "궁"]],
  ["wide_museum", ["미술관", "박물관", "전시"]],
  ["wide_market", ["시장"]],
  ["wide_river", ["호수", "한강", "천"]],
  ["wide_garden", ["산책길"]],
  ["wide_mountain", ["둘레길", "산"]],
  ["wide_cafe", ["거리", "카페"]],
  ["wide_temple", ["마을", "한옥", "성당"]],
  ["wide_library", ["도서관"]],
];
const PHOTO: [string, string[]][] = [
  ["photo_palace", ["고궁", "궁", "마을", "한옥"]],
  ["photo_museum", ["미술관", "박물관", "전시", "성당"]],
  ["photo_market", ["시장", "거리", "백화점", "쇼핑", "상가"]],
  ["photo_river", ["호수", "한강", "천"]],
];

function pick(table: [string, string[]][], kind: string, name: string, dflt: string) {
  const s = `${kind} ${name}`;
  for (const [f, words] of table) if (words.some((w) => s.includes(w))) return f;
  return dflt;
}

export function wideIll(kind = "", name = "") {
  if (name.includes("남산공원")) return "/aigo/ill/wide_namsan.svg";
  return `/aigo/ill/${pick(WIDE, kind, name, "wide_etc")}.svg`;
}
export function photoIll(kind = "", name = "") {
  if (name.includes("남산공원")) return "/aigo/ill/photo_namsan.svg";
  return `/aigo/ill/${pick(PHOTO, kind, name, "photo_forest")}.svg`;
}
