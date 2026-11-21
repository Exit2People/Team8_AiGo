"use client";

import { useCallback, useEffect, useState } from "react";
import type { FlowApi } from "../Flow";
import { Sub, Title } from "../ui";
import DamgoRun, { fmtSteps } from "../DamgoRun";
import { ranking, type Player, type RankBoard, type RankEntry } from "@/lib/ranking";

/* 담고 달리기 (12절) — 그림 · 움직임 · 판정은 TestTon과 같은 DamgoRun(components/DamgoRun.tsx) */

const playerOf = (f: FlowApi): Player | null => (f.s.user ? { id: f.s.user.id, nickname: f.s.user.nickname || "닉네임 없음" } : null);

export function Game({ f }: { f: FlowApi }) {
  return (
    <div className="content">
      <Title y={100}>담고 달리기</Title>
      <div className="abs" style={{ left: 24, right: 24, top: 150 }}>
        <DamgoRun
          color={f.s.coral}
          player={playerOf(f)}
          onRanking={() => f.go({ k: "rank" })}
          onOver={(steps) => window.dispatchEvent(new CustomEvent("aigo:badge", { detail: { ev: "run", steps } }))}
        />
      </div>
    </div>
  );
}

export function Rank({ f }: { f: FlowApi }) {
  const player = playerOf(f);
  const id = player?.id ?? null;
  const nickname = player?.nickname ?? "";
  const [board, setBoard] = useState<RankBoard | null>(null);
  const [fail, setFail] = useState(false);

  const fetchBoard = useCallback(
    () =>
      ranking.board(id ? { id, nickname } : null, 10).then(
        (b) => {
          setBoard(b);
          setFail(false);
        },
        () => setFail(true),
      ),
    [id, nickname],
  );
  useEffect(() => {
    fetchBoard();
  }, [fetchBoard]);
  const retry = () => {
    setFail(false);
    setBoard(null);
    fetchBoard();
  };

  const row = (e: RankEntry, rank: number) => (
    <li key={`${rank}-${e.nickname}`} className={`rankRow${e.mine ? " me" : ""}${rank <= 3 ? ` top${rank}` : ""}`}>
      <span className="rankNo" aria-label={`${rank}위`}>
        {rank}
      </span>
      <span className="rankName">
        {e.nickname}
        {e.mine ? <i>나</i> : null}
      </span>
      <span className="rankSteps">
        <b>{fmtSteps(e.steps)}</b>걸음
      </span>
    </li>
  );

  return (
    <div className="content">
      <Title y={100}>랭킹</Title>
      <Sub y={146}>담고 달리기 · 걸음이 많은 순서예요</Sub>
      <div className="abs rankWrap" style={{ left: 24, right: 24, top: 190, bottom: 28 }}>
        {fail ? (
          <section className="rankState" role="status">
            <b>랭킹을 불러오지 못했어요</b>
            <span>인터넷이 잘 되는지 보고 다시 눌러 주세요</span>
            <button className="btn soft center gapBtn" onClick={retry}>
              다시 불러오기
            </button>
          </section>
        ) : !board ? (
          <section className="rankState" role="status">
            <span>랭킹을 불러오고 있어요…</span>
          </section>
        ) : (
          <ol className="rankList scroll" aria-label="담고 달리기 랭킹">
            {board.top.length ? board.top.map((e, i) => row(e, i + 1)) : <li className="rankEmpty">아직 아무도 기록이 없어요. 첫 번째가 되어 보세요!</li>}
            {board.me && board.me.rank > board.top.length ? (
              <>
                <li className="rankGap" aria-hidden="true">
                  ⋯
                </li>
                {row(board.me.entry, board.me.rank)}
              </>
            ) : null}
          </ol>
        )}
        {!player ? (
          <button className="badgeCard rankGuest" onClick={() => f.go({ k: "login" })}>
            <span className="profileText">
              <b>내 이름도 올려 볼까요?</b>
              <span>로그인하면 기록이 랭킹에 올라가요</span>
            </span>
            <span className="pillWhite">로그인</span>
          </button>
        ) : board && !board.me ? (
          <p className="caption">한 판 달리면 내 기록이 랭킹에 올라가요</p>
        ) : null}
        {ranking.source === "local" ? <p className="caption mute">지금은 이 기기에만 저장돼요 · 예시 기록이 섞여 있어요</p> : null}
        <button className="btn dark center runBtn" onClick={f.back}>
          다시 달리기
        </button>
      </div>
    </div>
  );
}
