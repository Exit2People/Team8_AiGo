"""AI 라이브러리 미리 불러오기.

이 컴퓨터(Windows)에서 처음 `import anthropic` 이 12초, `langchain_anthropic` 이 13초쯤 걸렸어요.
첫 요청 안에서 불러오면 시간 한도(wait_for) 밖에서 막혀서 첫 말이 19초까지 걸렸어요 (화면 OPEN_FAIL 7초).
그래서 서버가 뜰 때 뒤에서 불러오고, AI를 부르는 곳은 남은 시간만큼만 기다려요. 다 못 불러왔으면 AI 없이 대신 길로 가요.
"""

import asyncio
import concurrent.futures
import logging
import time

log = logging.getLogger("aigo.warm")

_pool = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="aigo-warm")
_fut: concurrent.futures.Future | None = None


def _load() -> float:
    t0 = time.monotonic()
    import anthropic  # noqa: F401
    import langchain_anthropic  # noqa: F401
    import langchain_core.messages  # noqa: F401
    import langgraph.graph  # noqa: F401
    import langgraph.graph.message  # noqa: F401

    took = time.monotonic() - t0
    log.info("AI 라이브러리 준비: %.1f초", took)
    return took


def start() -> None:
    global _fut
    if _fut is None:
        _fut = _pool.submit(_load)


def is_ready() -> bool:
    return _fut is not None and _fut.done() and _fut.exception() is None


async def ready(timeout: float) -> bool:
    """timeout 안에 준비되면 True. 안 되면 False (불러오기는 뒤에서 계속돼요)."""
    start()
    if is_ready():
        return True
    if timeout <= 0:
        return False
    try:
        await asyncio.wait_for(asyncio.shield(asyncio.wrap_future(_fut)), timeout)
    except (asyncio.TimeoutError, Exception):
        log.warning("AI 라이브러리가 아직 준비되지 않았어요")
        return False
    return is_ready()
