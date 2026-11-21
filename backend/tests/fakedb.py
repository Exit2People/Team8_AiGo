"""가짜 DB: SQL 앞 /*이름*/ 으로 무엇을 할지 알아보고 파이썬 목록에 담아요 (실제 DB에 붙지 않아요)."""

import re
from datetime import datetime

from app import config


class FakeDB:
    def __init__(self):
        self.expects: set[tuple] = set()
        self.members: dict[tuple, str] = {}
        self.messages: list[dict] = []
        self.reports: list[dict] = []
        self.reviews: list[dict] = []
        self.handlers: dict = {}
        self.calls: list[str] = []
        self._id = 0

    def __call__(self, sql, params=None, fetch="none"):
        m = re.match(r"\s*/\*(\w+)\*/", sql)
        assert m, f"이름 없는 SQL: {sql[:40]}"
        tag = m.group(1)
        self.calls.append(tag)
        fn = self.handlers.get(tag) or getattr(self, "h_" + tag, None)
        assert fn, f"가짜 DB에 없는 SQL: {tag}"
        return fn(sql, params or (), fetch)

    def now(self):
        return config.now() if config.env("AIGO_NOW") else datetime.now(config.KST)

    # 소셜
    def h_cleanup(self, sql, p, f):
        d = p[0]
        if "place_expects" in sql:
            self.expects = {e for e in self.expects if e[0] >= d}
        elif "chat_members" in sql:
            self.members = {k: v for k, v in self.members.items() if k[0] >= d}
        elif "chat_messages" in sql:
            self.messages = [x for x in self.messages if x["day"] >= d]
        elif "chat_reports" in sql:
            self.reports = [x for x in self.reports if x["day"] >= d]

    def h_expect_count(self, sql, p, f):
        return {"n": sum(1 for e in self.expects if e[0] == p[0] and e[1] == p[1])}

    def h_expect_add(self, sql, p, f):
        self.expects.add(tuple(p))

    def h_expect_del(self, sql, p, f):
        self.expects.discard(tuple(p))

    def h_review_count(self, sql, p, f):
        return {"n": sum(1 for r in self.reviews if r["place_id"] == p[0])}

    def h_review_tags(self, sql, p, f):
        counts: dict[str, int] = {}
        for r in self.reviews:
            if r["place_id"] == p[0]:
                counts[r["tag"]] = counts.get(r["tag"], 0) + 1
        return [{"tag": t, "n": n} for t, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:3]]

    def h_review_page(self, sql, p, f):
        pid, limit, offset = p
        rows = sorted([r for r in self.reviews if r["place_id"] == pid], key=lambda r: (r["created_at"], r["id"]),
                      reverse=True)
        return rows[offset: offset + limit]

    def h_member_get(self, sql, p, f):
        n = self.members.get(tuple(p))
        return {"nick": n} if n else None

    def h_member_list(self, sql, p, f):
        return sorted([{"client": k[2], "nick": v} for k, v in self.members.items() if k[0] == p[0] and k[1] == p[1]],
                      key=lambda r: r["nick"])

    def h_member_add(self, sql, p, f):
        self.members.setdefault((p[0], p[1], p[2]), p[3])

    def h_member_del(self, sql, p, f):
        self.members.pop(tuple(p), None)

    def h_msg_add(self, sql, p, f):
        self._id += 1
        row = {"id": self._id, "day": p[0], "place_id": p[1], "client": p[2], "nick": p[3], "kind": p[4],
               "body": p[5], "created_at": self.now()}
        self.messages.append(row)
        return dict(row)

    def h_msg_list(self, sql, p, f):
        return [dict(x) for x in self.messages if x["day"] == p[0] and x["place_id"] == p[1] and x["id"] > p[2]]

    def h_msg_mine(self, sql, p, f):
        d, pid, client, since, n = p
        rows = [x for x in self.messages if x["day"] == d and x["place_id"] == pid and x["client"] == client
                and x["kind"] == "text" and x["created_at"] >= since]
        return list(reversed(rows))[:n]

    def h_msg_others(self, sql, p, f):
        d, pid, client, n = p
        rows = [x for x in self.messages if x["day"] == d and x["place_id"] == pid and x["client"] != client
                and x["kind"] in ("text", "quick")]
        return list(reversed(rows))[:n]

    def h_report_add(self, sql, p, f):
        self.reports.append({"day": p[0], "place_id": p[1], "target_nick": p[2]})


class FakeAuthDB(FakeDB):
    """회원 · 세션 · 게임 · 이메일 확인 숫자까지."""

    def __init__(self):
        super().__init__()
        self.users: dict[str, dict] = {}
        self.sessions: dict[str, dict] = {}
        self.consents: list[dict] = []
        self.scores: dict[str, dict] = {}
        self.codes: dict[str, dict] = {}

    def add_user(self, **kw) -> dict:
        import uuid

        uid = kw.pop("id", None) or str(uuid.uuid4())
        row = {"id": uid, "kakao_id": None, "email": None, "password_hash": None, "name": None, "nickname": None,
               "age": None, "home_dong1_id": None, "home_dong2_id": None, "created_at": self.now(),
               "last_login_at": self.now(), "deleted_at": None, "purge_after": None, "banned_at": None,
               "banned_reason": None}
        row.update(kw)
        self.users[uid] = row
        return row

    def _rt(self):
        return datetime.now(config.KST)

    def h_session_add(self, sql, p, f):
        self.sessions[p[0]] = {"user_id": p[1], "expires_at": p[2]}

    def h_user_touch(self, sql, p, f):
        self.users[p[0]]["last_login_at"] = self.now()

    def h_session_user(self, sql, p, f):
        s = self.sessions.get(p[0])
        if not s or s["expires_at"] <= self._rt():
            return None
        u = self.users.get(s["user_id"])
        if not u or u["deleted_at"] or u["banned_at"]:
            return None
        return dict(u)

    def h_session_del(self, sql, p, f):
        self.sessions.pop(p[0], None)

    def h_purge(self, sql, p, f):
        gone = [k for k, u in self.users.items() if u["purge_after"] and u["purge_after"] < self._rt()]
        for k in gone:
            self._delete_user(k)

    def _delete_user(self, uid):
        self.users.pop(uid, None)
        self.sessions = {k: v for k, v in self.sessions.items() if v["user_id"] != uid}
        self.consents = [c for c in self.consents if c["user_id"] != uid]
        self.scores.pop(uid, None)

    def _one(self, key, val):
        for u in self.users.values():
            if u.get(key) == val:
                return dict(u)
        return None

    def h_user_by_kakao(self, sql, p, f):
        return self._one("kakao_id", p[0])

    def h_user_by_email(self, sql, p, f):
        return self._one("email", p[0])

    def h_user_by_id(self, sql, p, f):
        u = self.users.get(str(p[0]))
        return dict(u) if u else None

    def h_user_add_kakao(self, sql, p, f):
        return {"id": self.add_user(kakao_id=p[0], home_dong1_id=p[1], home_dong2_id=p[2])["id"]}

    def h_consent_add(self, sql, p, f):
        self.consents.append({"user_id": p[0], "doc_type": p[1], "doc_version": p[2]})

    def h_user_update(self, sql, p, f):
        cols = re.findall(r"(\w+) = %s", sql.split(" where ")[0])
        u = self.users[str(p[-1])]
        for c, v in zip(cols, p[:-1]):
            u[c] = v
