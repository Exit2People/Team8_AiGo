"""Neon Postgres 연결 하나를 다시 써요. 테스트는 `run`을 가짜로 바꿔 끼워요."""

import logging
import threading

from fastapi import HTTPException

from app import config

log = logging.getLogger("aigo.db")

_lock = threading.Lock()
_conn = None

NO_DB = "DB가 설정되지 않았어요"
DB_FAIL = "DB에 연결하지 못했어요. 잠시 후 다시 시도해 주세요."


def configured() -> bool:
    return bool(config.env("DATABASE_URL"))


def _connect():
    import psycopg
    from psycopg.rows import dict_row

    return psycopg.connect(config.env("DATABASE_URL"), autocommit=True, connect_timeout=5, row_factory=dict_row)


def _execute(sql: str, params, fetch: str):
    global _conn
    if _conn is None or _conn.closed:
        _conn = _connect()
    with _conn.cursor() as cur:
        cur.execute(sql, params)
        if fetch == "one":
            return cur.fetchone()
        if fetch == "all":
            return cur.fetchall()
        return None


def _real_run(sql: str, params=None, fetch: str = "none"):
    global _conn
    if not configured():
        raise HTTPException(503, NO_DB)
    import psycopg

    with _lock:
        for attempt in range(2):
            try:
                return _execute(sql, params, fetch)
            except psycopg.OperationalError as e:
                log.warning("DB 연결 오류: %s", type(e).__name__)
                try:
                    if _conn is not None:
                        _conn.close()
                except Exception:
                    pass
                _conn = None
                if attempt == 1:
                    raise HTTPException(503, DB_FAIL)
            except psycopg.errors.UniqueViolation:
                # 같은 요청을 두 번 눌러 이미 들어간 경우예요. 연결 실패로 보이지 않게 409로 알려요
                raise HTTPException(409, "이미 처리됐어요. 다시 해 주세요")
            except psycopg.Error as e:
                log.warning("DB 오류: %s", type(e).__name__)
                raise HTTPException(503, DB_FAIL)


# 테스트에서 이 이름을 바꿔 끼워요: monkeypatch.setattr(db, "executor", fake)
executor = _real_run


def run(sql: str, params=None, fetch: str = "none"):
    """fetch: none · one · all. 행은 dict."""
    return executor(sql, params, fetch)
