"use client";

import type { FlowApi } from "../Flow";
import { PinIcon } from "../Icons";
import { Caption, Primary, Progress, Secondary, Sheet, Sub, Title } from "../ui";
import { DONGS, GUS, distText, dongsOf, type NearDong } from "@/lib/geo";
import { useEffect, useRef, useState } from "react";

export function OriginScreen({ f }: { f: FlowApi }) {
  const o = f.s.origin;
  const dong = o ? DONGS.find((d) => d.id === o.id) : null;
  return (
    <div className="content">
      <Progress on={1} text="1 / 4" />
      <Title y={112}>{"어디서\n출발하세요?"}</Title>
      <Sub y={196}>{"가까운 동을 찾아\n갈 곳을 알려 드려요"}</Sub>
      <Sheet y={470} />
      <div className="abs" style={{ left: 24, top: 500, display: "flex", gap: 10, alignItems: "center" }}>
        <PinIcon />
        <p className="t-tile">지금 있는 곳을 쓸까요?</p>
      </div>
      <Sub y={548} mute>{"위치는 가까운 동을 찾는 데만 쓰고\n어디에도 저장하지 않아요."}</Sub>
      {dong && (
        <Secondary y={386} white onClick={() => f.setOriginDong(dong)} label={`아까 고른 ${dong.name}`}>
          {`아까 고른 ${dong.name}`}
        </Secondary>
      )}
      <Primary y={636} onClick={f.useMyLocation}>
        네, 지금 위치로
      </Primary>
      <Secondary y={708} onClick={() => f.go({ k: "gu" })}>
        직접 고를게요
      </Secondary>
    </div>
  );
}

function DongRow({ d, onClick }: { d: NearDong; onClick: () => void }) {
  return (
    <button className="row" onClick={onClick}>
      <span className="badge">동</span>
      <span className="main">
        <span className="t-answer" style={{ display: "block" }}>
          {d.name}
        </span>
        <span className="t-item c-mute" style={{ display: "block", marginTop: 8 }}>
          {d.gu}
        </span>
      </span>
      <span className="side">
        <span className="t-count" style={{ display: "block" }}>
          {distText(d.distanceM)}
        </span>
        <span className="t-item c-mute" style={{ display: "block", marginTop: 8 }}>
          걸어서 {d.walkMin}분
        </span>
      </span>
    </button>
  );
}

export function NearbyScreen({ f, list, widened }: { f: FlowApi; list: NearDong[]; widened: boolean }) {
  const km = widened ? Math.max(1, Math.ceil((list[0]?.distanceM ?? 1000) / 1000)) : 1;
  return (
    <div className="content">
      <Progress on={1} text="1 / 4" />
      <Title y={112}>{"어디서\n출발하세요?"}</Title>
      <Sub y={196}>{`지금 위치에서\n${km}km 안의 동이에요`}</Sub>
      <div className="list" style={{ top: 266, height: 380 }}>
        {list.length ? (
          list.map((d) => <DongRow key={d.id} d={d} onClick={() => f.setOriginDong(d)} />)
        ) : (
          <p className="t-sub c-sub">이 근처에서 동을 찾지 못했어요. 뒤로 가서 다른 곳을 골라 주세요.</p>
        )}
      </div>
      <Secondary y={662} white onClick={() => f.go({ k: "gu" })}>
        직접 고를게요
      </Secondary>
      <Caption y={746}>가까운 순서로 보여 드려요</Caption>
    </div>
  );
}

export function GuScreen({ f }: { f: FlowApi }) {
  return (
    <div className="content">
      <Progress on={1} text="1 / 4" />
      <Title y={112}>{"어느 구에서\n출발하세요?"}</Title>
      <Sub y={196}>{"구를 고르면\n동을 보여 드려요"}</Sub>
      <div className="grid4" style={{ top: 280 }}>
        {GUS.map((g) => (
          <button key={g} className="pick" onClick={() => f.go({ k: "dong", gu: g })}>
            {g}
          </button>
        ))}
      </div>
      <Caption y={726}>가나다 순서예요</Caption>
    </div>
  );
}

export function DongScreen({ f, gu }: { f: FlowApi; gu: string }) {
  const list = dongsOf(gu);
  const ref = useRef<HTMLDivElement>(null);
  const [more, setMore] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const check = () => setMore(el.scrollHeight - el.scrollTop - el.clientHeight > 8);
    check();
    el.addEventListener("scroll", check, { passive: true });
    return () => el.removeEventListener("scroll", check);
  }, [gu]);
  return (
    <div className="content">
      <Progress on={1} text="1 / 4" />
      <Title y={112}>{"어느 동에서\n출발하세요?"}</Title>
      <Sub y={196}>{`${gu}에 있는\n동이에요`}</Sub>
      <div ref={ref} className="grid2" style={{ top: 266, height: 440, paddingBottom: 12 }}>
        {list.map((d) => (
          <button key={d.id} className="pick" style={{ fontSize: `calc(${d.name.length > 6 ? 15 : 18}px * var(--fs))` }} onClick={() => f.setOriginDong(d)}>
            {d.name}
          </button>
        ))}
      </div>
      <Caption y={726}>{more ? "아래로 밀면 동이 더 있어요 ↓" : "동을 누르면 다음으로 넘어가요"}</Caption>
    </div>
  );
}
