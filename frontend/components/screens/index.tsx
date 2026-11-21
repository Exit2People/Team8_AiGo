"use client";

import type { FlowApi } from "../Flow";
import type { Step } from "@/lib/flow";
import Start from "./Start";
import { DongScreen, GuScreen, NearbyScreen, OriginScreen } from "./Origin";
import Open from "./Open";
import Question from "./Question";
import Confirm from "./Confirm";
import Result from "./Result";
import Route from "./Route";
import NotFound from "./NotFound";
import Login from "./Login";
import { Arrive, ChatJoin, Guestbook } from "./Social";
import Chat from "./Chat";
import { Blocked, My, MyEdit, Theme } from "./My";
import { Badges, Cut, Mine, Review, Sdetail, Stamped, Upload } from "./Mine";
import { Game, Rank } from "./Game";
import { Addr, Agree, Elogin, Kwait, Restore, Signup, Welcome } from "./Auth";
import { Secondary, Sub, Title } from "../ui";

/** at: 이 화면이 맨 위였을 때의 stack 길이. 넓은 화면에서 뒤에 깔린 화면 · 창 화면이 다시 만들어지지 않게 넘겨요 */
export default function Screen({ f, step, at }: { f: FlowApi; step: Step; at?: number }) {
  const key = `${at ?? f.s.stack.length}-${step.k}`;
  switch (step.k) {
    case "start":
      return <Start key={key} f={f} />;
    case "origin":
      return <OriginScreen key={key} f={f} />;
    case "nearby":
      return <NearbyScreen key={key} f={f} list={step.list} widened={step.widened} />;
    case "gu":
      return <GuScreen key={key} f={f} />;
    case "dong":
      return <DongScreen key={key} f={f} gu={step.gu} />;
    case "open":
      return <Open key={key} f={f} />;
    case "body":
    case "time":
      return <Question key={key} f={f} kind={step.k} edit={step.edit} />;
    case "flex":
      return <Question key={`${key}-${step.i}`} f={f} kind="flex" i={step.i} edit={step.edit} />;
    case "confirm":
      return <Confirm key={key} f={f} />;
    case "result":
      return <Result key={key} f={f} />;
    case "route":
      return <Route key={key} f={f} />;
    case "notFound":
      return <NotFound key={key} f={f} why={step.why} />;
    case "guestbook":
      return <Guestbook key={key} f={f} />;
    case "arrive":
      return <Arrive key={key} f={f} />;
    case "chatjoin":
      return <ChatJoin key={key} f={f} />;
    case "chat":
      return <Chat key={key} f={f} />;
    case "login":
      return <Login key={key} f={f} />;
    case "kwait":
      return <Kwait key={key} f={f} />;
    case "agree":
      return <Agree key={key} f={f} />;
    case "addr":
      return <Addr key={key} f={f} />;
    case "restore":
      return <Restore key={key} f={f} />;
    case "elogin":
      return <Elogin key={key} f={f} />;
    case "signup":
      return <Signup key={`${key}-${step.i}`} f={f} i={step.i} />;
    case "welcome":
      return <Welcome key={key} f={f} />;
    case "my":
      return <My key={key} f={f} />;
    case "myedit":
      return <MyEdit key={key} f={f} field={step.field} />;
    case "theme":
      return <Theme key={key} f={f} />;
    case "blocked":
      return <Blocked key={key} f={f} />;
    case "mine":
      return <Mine key={key} f={f} />;
    case "upload":
      return <Upload key={key} f={f} stepKey={step.key} />;
    case "cut":
      return <Cut key={key} f={f} stepKey={step.key} />;
    case "stamped":
      return <Stamped key={key} f={f} stepKey={step.key} />;
    case "review":
      return <Review key={key} f={f} stepKey={step.key} edit={step.edit} />;
    case "sdetail":
      return <Sdetail key={key} f={f} stepKey={step.key} />;
    case "badges":
      return <Badges key={key} f={f} />;
    case "game":
      return <Game key={key} f={f} />;
    case "rank":
      return <Rank key={key} f={f} />;
    default:
      return (
        <div className="content">
          <Title y={300} align="center" size="m">
            {"준비하고\n있어요"}
          </Title>
          <Sub y={392} align="center">
            곧 쓸 수 있어요
          </Sub>
          <Secondary y={700} white onClick={f.home}>
            처음으로
          </Secondary>
        </div>
      );
  }
}
