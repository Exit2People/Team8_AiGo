"""Claude 호출 한 곳. JSON 모양으로 받고, 실패 · 늦음은 None (보낸 값 · 받은 값은 로그에 안 남겨요)."""

import asyncio
import json
import time
import logging

from app import config

log = logging.getLogger("aigo.llm")

_client = None
_client_key = None


def _get_client():
    global _client, _client_key
    import anthropic

    key = config.env("ANTHROPIC_API_KEY") or config.env("ANTHROPIC_AUTH_TOKEN")
    if _client is None or _client_key != key:
        if config.env("ANTHROPIC_API_KEY"):
            _client = anthropic.AsyncAnthropic(api_key=key, max_retries=0)
        else:
            _client = anthropic.AsyncAnthropic(auth_token=key, max_retries=0)
        _client_key = key
    return _client


async def ask_json(system: str, payload, schema: dict, timeout: float, max_tokens: int = 2000) -> dict | None:
    if not config.has_ai() or timeout <= 0:
        return None
    from app.llm import warm

    t0 = time.monotonic()
    if not await warm.ready(timeout - 0.5):
        return None
    timeout -= time.monotonic() - t0
    import anthropic

    try:
        client = _get_client()
        resp = await asyncio.wait_for(
            client.messages.create(
                model=config.model(),
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
                output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}},
            ),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        log.warning("AI 응답이 시간 안에 오지 않았어요")
        return None
    except anthropic.APIStatusError as e:
        log.warning("AI 상태 오류 %s", e.status_code)
        return None
    except anthropic.APIConnectionError:
        log.warning("AI 연결 오류")
        return None
    except Exception as e:
        log.warning("AI 오류: %s", type(e).__name__)
        return None
    if resp.stop_reason != "end_turn":
        log.warning("AI가 끝까지 답하지 않았어요: %s", resp.stop_reason)
        return None
    text = next((b.text for b in resp.content if getattr(b, "type", None) == "text"), None)
    if not text:
        return None
    try:
        data = json.loads(text)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None
