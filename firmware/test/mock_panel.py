"""Serves firmware/main/www/index.html with a fake board API, to try the web panel in a browser.

    python3 firmware/test/mock_panel.py   ->  http://localhost:8765
"""
import json
import os
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs

HTML = os.path.join(os.path.dirname(__file__), "..", "main", "www", "index.html")
state = {"home": None, "presses": 0, "hold_until": 0,
         "settings": {"arrive_radius_m": 150, "leave_radius_m": 300, "leave_presses": 10, "arrive_duration_s": 180}}
FIX = (48.2081760, 16.3738190)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype="application/json"):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/":
            return self.send(200, open(HTML, "rb").read(), "text/html")
        if self.path == "/api/status":
            home = state["home"]
            return self.send(200, json.dumps({
                "state": "LEAVING" if home else "NO_HOME", "parked": "HOME", "distance_m": 12 if home else -1,
                "gps": {"seen": True, "usable": True, "fix": True, "lat": FIX[0], "lon": FIX[1], "acc_m": 2.4,
                        "sats": 14, "age_s": 0},
                "home": {"set": bool(home), "lat": home[0] if home else 0, "lon": home[1] if home else 0},
                "settings": state["settings"], "presses_remaining": state["presses"],
                "holding": time.time() < state["hold_until"],
                "version": "1.0.0", "uptime_s": 754}))
        self.send(404, "{}")

    def do_POST(self):
        body = parse_qs(self.rfile.read(int(self.headers.get("Content-Length", 0))).decode())
        get = lambda k: body.get(k, [""])[0]
        ok = lambda: self.send(200, '{"ok":true}')
        err = lambda m: self.send(400, json.dumps({"ok": False, "error": m}))
        if self.path == "/api/home":
            state["home"] = FIX if get("mode") == "here" else (float(get("lat")), float(get("lon")))
            return ok()
        if self.path == "/api/settings":
            s = {k: int(get(k)) for k in state["settings"]}
            if s["leave_radius_m"] < s["arrive_radius_m"] + 50:
                return err("Leave radius must be at least 50 m larger than the arrive radius (max 5000 m)")
            state["settings"] = s
            return ok()
        if self.path == "/api/test":
            state["presses"] = 1
            return ok()
        if self.path == "/api/hold":
            state["hold_until"] = time.time() + 5
            return ok()
        err("unknown")


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", 8765), Handler).serve_forever()
