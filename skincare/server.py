"""Skincare Tracker backend: stdlib only (http.server + sqlite3), no installs needed.

Run:  python3 server.py   ->  http://localhost:8000
"""
import json
import os
import sqlite3
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("SKINCARE_DB", os.path.join(HERE, "skincare.db"))


def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with db() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS skincare(day TEXT PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS pillow_events(
                id INTEGER PRIMARY KEY, kind TEXT NOT NULL, day TEXT NOT NULL);
        """)


def parse_day(s):
    return date.fromisoformat(s) if s else date.today()


def pillow_state(con, today):
    """Pillowcase cycle: fresh cover = night 1 (side A), flipped = night 2 (side B), then re-cover."""
    change = con.execute("SELECT * FROM pillow_events WHERE kind='change' ORDER BY id DESC LIMIT 1").fetchone()
    if not change:
        return {"status": "none", "side": None, "nights_left": 0}
    flip = con.execute("SELECT * FROM pillow_events WHERE kind='flip' AND id>? ORDER BY id DESC LIMIT 1",
                       (change["id"],)).fetchone()
    changed_on = parse_day(change["day"])
    if not flip:
        status = "flip_due" if today > changed_on else "side_a"
        return {"status": status, "side": "A", "changed_on": change["day"], "nights_left": 2 if status == "side_a" else 1,
                "nights_slept": (today - changed_on).days}
    flipped_on = parse_day(flip["day"])
    status = "change_due" if today > flipped_on else "side_b"
    return {"status": status, "side": "B", "changed_on": change["day"], "flipped_on": flip["day"],
            "nights_left": 0 if status == "change_due" else 1, "nights_slept": 1 + (today - flipped_on).days}


def streak(con, today):
    full = {r["day"] for r in con.execute("SELECT day FROM skincare")}
    d = today if today.isoformat() in full else today - timedelta(days=1)
    count = 0
    while d.isoformat() in full:
        count += 1
        d -= timedelta(days=1)
    return count


def full_state(day_s, today_s):
    day, today = parse_day(day_s), parse_day(today_s)
    with db() as con:
        done = {r["day"] for r in con.execute("SELECT day FROM skincare")}
        week = [{"day": d.isoformat(), "done": d.isoformat() in done}
                for d in (today - timedelta(days=i) for i in range(6, -1, -1))]
        history = [dict(r) for r in con.execute("SELECT kind, day FROM pillow_events ORDER BY id DESC LIMIT 8")]
        return {"day": day.isoformat(), "done": day.isoformat() in done, "streak": streak(con, today),
                "week": week, "pillow": pillow_state(con, today), "pillow_history": history}


def act(body):
    kind = body.get("action")
    day = parse_day(body.get("day")).isoformat()
    with db() as con:
        if kind == "toggle":
            if con.execute("SELECT 1 FROM skincare WHERE day=?", (day,)).fetchone():
                con.execute("DELETE FROM skincare WHERE day=?", (day,))
            else:
                con.execute("INSERT INTO skincare(day) VALUES(?)", (day,))
        elif kind in ("change", "flip"):
            con.execute("INSERT INTO pillow_events(kind,day) VALUES(?,?)", (kind, day))
        elif kind == "undo_pillow":
            con.execute("DELETE FROM pillow_events WHERE id=(SELECT MAX(id) FROM pillow_events)")
        else:
            return 400
    return 200


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, payload, ctype="application/json"):
        data = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/api/state":
            q = parse_qs(url.query)
            today = q.get("today", [None])[0]
            try:
                return self._send(200, full_state(q.get("day", [today])[0], today))
            except ValueError:
                return self._send(400, {"error": "bad date"})
        if url.path in ("/", "/index.html"):
            with open(os.path.join(HERE, "static", "index.html"), "rb") as f:
                return self._send(200, f.read(), "text/html; charset=utf-8")
        self._send(404, {"error": "not found"})

    def do_POST(self):
        if urlparse(self.path).path != "/api/action":
            return self._send(404, {"error": "not found"})
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            code = act(body)
        except (ValueError, KeyError, TypeError):
            code = 400
        self._send(code, {"ok": code == 200})

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 8000))
    print(f"Skincare Tracker läuft auf http://localhost:{port}")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
