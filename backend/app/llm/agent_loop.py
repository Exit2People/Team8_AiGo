"""도구를 쓰는 에이전트 한 곳 (LangGraph): agent → tools → agent … / 제출 · 도구 없음 · 횟수 초과 → 끝.

질문 에이전트와 추천 에이전트가 같이 써요. 모델은 `make_chat`으로 만들어서 테스트가 가짜로 바꿔 끼워요.
보낸 값 · 받은 값은 로그에 안 남기고, 도구 횟수 · 끝난 까닭만 남겨요.
"""

import asyncio
import json
import logging
from typing import Annotated, Any, Awaitable, Callable, TypedDict

from app import config

log = logging.getLogger("aigo.agent")

Tool = Callable[..., Awaitable[Any] | Any]


def make_chat(model: str, max_tokens: int, effort: str | None):
    from langchain_anthropic import ChatAnthropic

    kw: dict = {"model": model, "max_tokens": max_tokens, "max_retries": 0}
    key = config.env("ANTHROPIC_API_KEY")
    if key:
        kw["api_key"] = key
    if effort:
        kw["effort"] = effort
    return ChatAnthropic(**kw)


async def run(system: str, first: dict, tools: dict[str, Tool], schemas: list[dict], submit: str,
              max_rounds: int, timeout: float, model: str, max_tokens: int, effort: str | None,
              name: str = "agent") -> dict | None:
    """제출 도구의 인자를 돌려줘요. {"submitted": args 또는 None, "rounds": n}. 실패 · 늦음은 None."""
    if not config.has_ai() or timeout <= 0:
        return None
    from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage, ToolMessage
    from langgraph.graph import END, StateGraph
    from langgraph.graph.message import add_messages

    class State(TypedDict):
        messages: Annotated[list[AnyMessage], add_messages]
        rounds: int
        submitted: dict | None

    chat = make_chat(model, max_tokens, effort).bind_tools(schemas)

    async def agent(state: State):
        msg = await chat.ainvoke(state["messages"])
        sub = next((tc for tc in (getattr(msg, "tool_calls", None) or []) if tc["name"] == submit), None)
        return {"messages": [msg], "submitted": (sub["args"] if sub else None)}

    async def run_tools(state: State):
        out = []
        for tc in state["messages"][-1].tool_calls:
            fn = tools.get(tc["name"])
            if fn is None:
                res: Any = {"error": "없는 도구예요"}
            else:
                try:
                    res = fn(**(tc.get("args") or {}))
                    if asyncio.iscoroutine(res):
                        res = await res
                except (TypeError, ValueError):
                    res = {"error": "입력이 잘못됐어요"}
            out.append(ToolMessage(content=json.dumps(res, ensure_ascii=False, default=str), tool_call_id=tc["id"]))
        return {"messages": out, "rounds": state["rounds"] + 1}

    def route(state: State):
        last = state["messages"][-1]
        if state.get("submitted") is not None or not getattr(last, "tool_calls", None):
            return "end"
        if state["rounds"] >= max_rounds:
            return "end"
        return "tools"

    g = StateGraph(State)
    g.add_node("agent", agent)
    g.add_node("tools", run_tools)
    g.set_entry_point("agent")
    g.add_conditional_edges("agent", route, {"tools": "tools", "end": END})
    g.add_edge("tools", "agent")
    app = g.compile()
    init = {"messages": [SystemMessage(content=system), HumanMessage(content=json.dumps(first, ensure_ascii=False))],
            "rounds": 0, "submitted": None}
    try:
        final = await asyncio.wait_for(app.ainvoke(init, config={"recursion_limit": max_rounds * 2 + 5}),
                                       timeout=timeout)
    except asyncio.TimeoutError:
        log.warning("%s: 시간 안에 끝나지 않았어요", name)
        return None
    except Exception as e:
        log.warning("%s 오류: %s", name, type(e).__name__)
        return None
    log.info("%s: 도구 %s번, 제출 %s", name, final["rounds"], final.get("submitted") is not None)
    return {"submitted": final.get("submitted"), "rounds": final["rounds"]}
