import type { Slot } from "./types";
import type { Q } from "./flow";

/** 질문 은행 (11_FRONTEND_SPEC 5.3) */
export const BODY = { question: "컨디션은 어떠세요?", choices: ["가뿐해요", "보통이에요", "좀 무거워요"] };
export const TIME = {
  question: "얼마나 나가 계실 건가요?",
  choices: ["반나절", "한나절", "하루 종일"],
  hints: { 반나절: "3시간쯤", 한나절: "6시간쯤" } as Record<string, string>,
};

export type BankQ = { question: string; choices: string[]; slot: Exclude<Slot, null> };

export const BASIC: BankQ[] = [
  { slot: "want", question: "뭘 하고 싶으세요?", choices: ["바람 쐬기", "구경하기", "맛있는 것", "조용히 쉬기"] },
  { slot: "walk", question: "걷는 건 괜찮으세요?", choices: ["많이 걸어요", "보통이에요", "조금만요"] },
  { slot: "inout", question: "실내가 좋으세요, 바깥이 좋으세요?", choices: ["실내가 좋아요", "바깥이 좋아요", "둘 다 좋아요"] },
];

export const SLOT_NAME: Record<string, string> = { want: "하고 싶은 것", walk: "걷기", inout: "실내 · 바깥" };

export const DONT_KNOW = "잘 모르겠어요";

type QuestionContent = Pick<Q, "question" | "choices" | "slot">;
const questionKey = (s: string) => s.replace(/[\s?.!,·~]/g, "");

export function alreadyAsked(next: QuestionContent, history: Q[]) {
  const options = new Set(next.choices.filter((c) => ![DONT_KNOW, "둘 다 좋아요", "상관없어요"].includes(c)).map(questionKey));
  return history.some((q) => {
    if (!q.answered) return false;
    if (next.slot && next.slot === q.slot) return true;
    if (questionKey(next.question) === questionKey(q.question)) return true;
    return [...new Set(q.choices.map(questionKey))].filter((c) => options.has(c)).length >= Math.max(2, options.size - 1);
  });
}

export function nextBasic(history: Q[], place: string | null, wish: string[], body: string | null | undefined) {
  return BASIC.find((b) => {
    if (place && b.slot !== "walk") return false;
    if (wish.length && b.slot === "want") return false;
    if (body === "좀 무거워요" && b.slot === "walk") return false;
    return !alreadyAsked(b, history);
  });
}

export function finishedQuestions(history: Q[], legacyLimit: number) {
  const asked = history.filter((q) => q.src !== "open" && q.answered);
  const last = asked.at(-1);
  if (!last?.total) return asked.length >= legacyLimit;
  // 전체 수를 채운 뒤 서버가 추가 질문 하나를 결정해요. 기본 질문으로 전환했으면 여기서 끝나요.
  return !!last.extra || (last.src === "basic" && last.no != null && last.no + 1 >= last.total)
    || 3 + asked.length > last.total;
}

/** 질문 글 두 줄 만들기 (5.2) */
export function twoLines(q: string): string {
  if (q.includes("\n") || q.length <= 7) return q;
  const c = q.indexOf(", ");
  if (c > 0) return q.slice(0, c + 1) + "\n" + q.slice(c + 2);
  const mid = q.length / 2;
  let best = -1;
  for (let i = 0; i < q.length; i++) if (q[i] === " " && (best < 0 || Math.abs(i - mid) < Math.abs(best - mid))) best = i;
  return best < 0 ? q : q.slice(0, best) + "\n" + q.slice(best + 1);
}

/** 제목 크기 (5.2) */
export function titleSize(q: string): number {
  const flat = q.replace(/\n/g, " ");
  const longest = Math.max(...flat.split(/\s+/).map((w) => w.length));
  if (flat.length > 18 || longest >= 6) return 26;
  if (flat.length > 12 || longest >= 5) return 29;
  return 32;
}

/** 선택지 글자 크기 (5.2) */
export function tileSize(a: string): number {
  if (a.length > 8) return 17;
  if (a.length > 6) return 20;
  return 25;
}
