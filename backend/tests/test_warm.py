"""AI 라이브러리가 아직 준비되지 않았으면 시간 한도 안에 AI 없이 대신 길로 가요 (첫 말 19초 문제)."""

import asyncio
import concurrent.futures
import time

from app.llm import agent_loop, warm
from app.llm import client as llm


def test_not_ready_returns_within_timeout(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    never = concurrent.futures.Future()
    monkeypatch.setattr(warm, "_fut", never)
    t0 = time.monotonic()
    assert asyncio.run(llm.ask_json("s", {}, {"type": "object"}, 1.0)) is None
    assert asyncio.run(agent_loop.run("s", {}, {}, [], "x", 1, 1.0, "m", 10, None)) is None
    assert time.monotonic() - t0 < 2.5
    assert asyncio.run(warm.ready(0.0)) is False


def test_ready_after_load():
    warm.start()
    assert asyncio.run(warm.ready(30.0)) is True
