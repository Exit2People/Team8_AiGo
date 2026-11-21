import logging

import httpx

import app.main  # noqa: F401  (로그 설정을 적용해요)


def test_httpx_does_not_log_request_urls(caplog):
    """키가 쿼리에 든 외부 호출 주소가 로그에 남지 않아요 (09_ACCEPTANCE 7.6)."""
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json={}))
    with caplog.at_level(logging.INFO):
        with httpx.Client(transport=transport) as c:
            c.get("https://example.test/api", params={"serviceKey": "FAKE-KEY-123"})
    assert "FAKE-KEY-123" not in caplog.text
