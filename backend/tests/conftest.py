import os

import pytest

# 테스트는 실제 키 · DB를 쓰지 않아요 (09_ACCEPTANCE.md 0.1). import 전에 지워요 (.env가 다시 못 채우게 빈 값).
KEYS = [
    "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "TYPESAFE_API_KEY", "SEOUL_OPENAPI_KEY",
    "DATA_GO_KR_SERVICE_KEY", "KAKAO_REST_API_KEY", "KAKAO_CLIENT_SECRET", "KAKAO_ADMIN_KEY",
    "KAKAO_JS_KEY", "TMAP_APP_KEY", "DATABASE_URL", "DATABASE_URL_DIRECT", "AIGO_SMTP_USER",
    "AIGO_SMTP_PASSWORD", "AIGO_SESSION_SECRET", "AIGO_AGENT", "AIGO_JEV", "AIGO_NOW",
    "AIGO_SYNC_FREEZE", "AIGO_PUBLIC_URL", "AIGO_QUESTION", "AIGO_QUESTION_START",
]
for _k in KEYS:
    os.environ[_k] = ""
os.environ["AIGO_WEATHER"] = "맑음"
os.environ["AIGO_QUESTION_AGENT"] = "0"
os.environ["AIGO_AGENT"] = "0"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch, tmp_path):
    for k in KEYS:
        monkeypatch.setenv(k, "")
    monkeypatch.setenv("AIGO_WEATHER", "맑음")
    monkeypatch.setenv("AIGO_QUESTION_AGENT", "0")
    monkeypatch.setenv("AIGO_AGENT", "0")  # 브랜치 기본은 켜짐, 테스트는 필요할 때만 켜요
    # 매일 DB는 빈 임시 폴더 → 저장소 스냅숏을 읽어요
    monkeypatch.setenv("AIGO_DB_PATH", str(tmp_path / "cache" / "aigo.db"))
    from app.data import loader, weather

    loader.clear_cache()
    weather.clear_cache()
    yield
