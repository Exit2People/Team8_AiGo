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
