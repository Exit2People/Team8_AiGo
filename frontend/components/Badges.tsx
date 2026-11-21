"use client";
/* eslint-disable @next/next/no-img-element */

// 업적 배지 화면 (TestTon components/Badges.tsx와 같은 모양).
// 내 정보의 업적 카드 · 업적 모아 보기 · 배지 자세히 · 얻은 순간 축하. 판정은 lib/badges.ts.

import { HIDDEN_IMG, TIERS, type BadgeDef, type BadgeState } from "@/lib/badges";
import { CheckIcon } from "./Icons";

const img = (id: string) => `/aigo/badges/${id}.svg`;
const locked = (s: BadgeState) => !s.earnedAt;
const secret = (s: BadgeState) => s.def.hidden && !s.earnedAt;
const imgOf = (s: BadgeState) => (secret(s) ? HIDDEN_IMG : img(s.def.id));
// 배지 그림은 단계마다 틀 모양이 달라서(동그라미 · 육각형 · 별 · 빛살) 240칸 안에서 차지하는 크기가 달라요.
// 눈으로 볼 때 비슷하게 꽉 차 보이도록 단계별로 키워요. (숨은 업적 그림은 첫걸음과 같은 동그라미 틀)
const FIT: Record<number, number> = { 1: 1.1, 2: 1.16, 3: 1.04, 4: 0.97 };
const fit = (tier: number, hidden = false) => ({ scale: String(hidden ? FIT[1] : FIT[tier] ?? 1) });
const md = (iso: string) => {
  const d = new Date(iso);
  return `${d.getFullYear()}년 ${d.getMonth() + 1}월 ${d.getDate()}일`;
};

// ── 내 정보에 붙는 업적 카드 ──
export function BadgeCard({ states, onOpen }: { states: BadgeState[]; onOpen: () => void }) {
  const earned = states.filter((s) => s.earnedAt).sort((a, b) => (b.earnedAt! > a.earnedAt! ? 1 : -1));
  return (
    <button className="badgeCard" onClick={onOpen} aria-label={`업적 보기, ${states.length}개 중 ${earned.length}개 모음`}>
      <span className="bcThumbs" aria-hidden="true">
        {earned.length ? earned.slice(0, 3).map((s, i) => <img key={s.def.id} src={img(s.def.id)} alt="" style={{ zIndex: 3 - i, ...fit(s.def.tier) }} />) : <img src={HIDDEN_IMG} alt="" style={fit(1, true)} />}
      </span>
      <span className="profileText">
        <b>업적 {earned.length}개를 모았어요</b>
        <span>
          {earned.length ? `최근: ${earned[0].def.name}` : "첫 나들이를 하면 배지가 생겨요"} · 전체 {states.length}개
        </span>
      </span>
      <span className="pillWhite">보기</span>
    </button>
  );
}

// ── 업적 모아 보기: 단계별로 묶어요 ──
export function BadgeBoard({ states, onPick }: { states: BadgeState[]; onPick: (s: BadgeState) => void }) {
  return (
    <div className="badgeBoard">
      {TIERS.map((t) => {
        const list = states.filter((s) => s.def.tier === t.tier);
        const got = list.filter((s) => s.earnedAt).length;
        return (
          <section key={t.tier} className={`bbTier t${t.tier}`} aria-label={`${t.name} 단계, ${list.length}개 중 ${got}개`}>
            <h2 className="bbHead">
              <b>{t.name}</b>
              <i>{t.level}</i>
              <em>
                {got} / {list.length}
              </em>
            </h2>
            <div className="bbGrid">
              {list.map((s) => (
                <button
                  key={s.def.id}
                  className={`bbItem${locked(s) ? " locked" : ""}${secret(s) ? " secret" : ""}`}
                  onClick={() => onPick(s)}
                  aria-label={secret(s) ? "숨은 업적, 아직 몰라요" : `${s.def.name}, ${s.earnedAt ? "얻었어요" : `아직이에요 ${s.cur} / ${s.target}`}`}
                >
                  <img src={imgOf(s)} alt="" style={fit(s.def.tier, secret(s))} />
                  <b>{secret(s) ? "숨은 업적" : s.def.name}</b>
                  {locked(s) && !secret(s) && s.target > 1 ? (
                    <span className="bbProg" aria-hidden="true">
                      <i style={{ width: `${(s.cur / s.target) * 100}%` }} />
                      <em>
                        {s.cur}/{s.target}
                      </em>
                    </span>
                  ) : null}
                </button>
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}

// ── 배지 자세히 (아래에서 올라오는 판) ──
export function BadgeSheet({ state: s, onClose }: { state: BadgeState; onClose: () => void }) {
  const tier = TIERS.find((t) => t.tier === s.def.tier)!;
  return (
    <div className="dim" onClick={onClose}>
      <section className="menuSheet badgeSheet" role="dialog" aria-modal="true" aria-labelledby="badgeTitle" onClick={(e) => e.stopPropagation()}>
        <span className="handle" aria-hidden="true" />
        <img className={`bsImg${locked(s) && !secret(s) ? " locked" : ""}`} src={imgOf(s)} alt="" style={fit(s.def.tier, secret(s))} />
        <span className={`bsTier t${s.def.tier}`}>
          {tier.name} · {tier.level}
        </span>
        <h2 id="badgeTitle" className="menuTitle">
          {secret(s) ? "숨은 업적" : s.def.name}
        </h2>
        <p className="sheetSub">{secret(s) ? "어떻게 얻는지는 비밀이에요.\n나들이를 하다 보면 만날 거예요" : s.def.condition}</p>
        {s.earnedAt ? (
          <p className="bsDone">
            <CheckIcon size={22} />
            {md(s.earnedAt)}에 얻었어요
          </p>
        ) : !secret(s) && s.target > 1 ? (
          <div className="bsProg" aria-label={`${s.target}번 중 ${s.cur}번`}>
            <span>
              <i style={{ width: `${(s.cur / s.target) * 100}%` }} />
            </span>
            <em>
              {s.cur} / {s.target}
            </em>
          </div>
        ) : !secret(s) ? (
          <p className="bsDone muted">아직 얻지 못했어요</p>
        ) : null}
        <button className="btn dark center" onClick={onClose}>
          닫기
        </button>
      </section>
    </div>
  );
}

// ── 얻은 순간 축하 (화면 가운데 크게) ──
export function BadgeCelebrate({ badge, more, onNext, onOpenAll }: { badge: BadgeDef; more: number; onNext: () => void; onOpenAll: () => void }) {
  const tier = TIERS.find((t) => t.tier === badge.tier)!;
  return (
    <div className="dim center celebrateDim" onClick={onNext}>
      <section
        className={`celebrate t${badge.tier}`}
        role="alertdialog"
        aria-modal="true"
        aria-label="새 배지를 얻었어요"
        aria-describedby="celebrateText"
        onClick={(e) => e.stopPropagation()}
      >
        <span className="cbRays" aria-hidden="true" />
        <img className="cbImg" src={img(badge.id)} alt="" style={fit(badge.tier)} />
        <span className={`bsTier t${badge.tier}`}>
          {badge.hidden ? "숨은 업적 · " : ""}
          {tier.name}
        </span>
        <p className="cbKicker">새 배지를 얻었어요!</p>
        <h2 className="cbName">{badge.name}</h2>
        <p id="celebrateText" className="cbText">
          {badge.cheer}
        </p>
        <button className="btn dark center" autoFocus onClick={onNext}>
          {more ? "좋아요 · 하나 더 있어요" : "좋아요"}
          <span className="arrow" aria-hidden="true">
            →
          </span>
        </button>
        <button className="linkBtn under" onClick={onOpenAll}>
          내 업적 모두 보기
        </button>
      </section>
    </div>
  );
}
