import assert from "node:assert/strict";
import { test } from "node:test";
import { alreadyAsked, finishedQuestions, nextBasic } from "../lib/questions.ts";

const activity = { question: "뭘 하고 싶으세요?", choices: ["그림 · 사진", "물가"], slot: null, answered: true, src: "ai", a: "그림 · 사진" };

test("분류 없는 활동 질문에 답한 다음 기본 질문으로 넘어가도 되묻지 않아요", () => {
  assert.equal(nextBasic([activity], null, [], null).slot, "walk");
  assert.equal(nextBasic([activity], "서울숲", [], "좀 무거워요"), undefined);
});

test("잘 모르겠다고 한 장소 목록은 질문 표현과 순서가 바뀌어도 알아봐요", () => {
  const first = { ...activity, question: "어느 공원에 가실래요?", choices: ["여의도한강공원", "망원한강공원"], a: null };
  assert.ok(alreadyAsked({ ...first, question: "어디가 끌리세요?", choices: [...first.choices].reverse() }, [first]));
  assert.equal(alreadyAsked(activity, [first]), false);
});

test("첫 발화에서 알아낸 칸은 후속 질문 횟수에서 빼고 서버가 정한 추가 질문까지 받아요", () => {
  const open = { ...activity, src: "open" };
  const regular = [3, 4, 5, 6].map((no) => ({ ...activity, no, total: 7 }));
  assert.equal(finishedQuestions([open, ...regular], 3), false);
  assert.equal(finishedQuestions([...regular, { ...activity, no: 7, total: 8, extra: true }], 3), true);
  assert.equal(finishedQuestions([open, activity, activity], 3), false);
  assert.equal(finishedQuestions([activity, activity, activity], 3), true);
});
