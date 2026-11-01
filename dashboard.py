"""EndorseGuard interactive dashboard.

    python dashboard.py            opens http://127.0.0.1:8765 in your browser
    python dashboard.py --port 9000 --no-browser

Standard library only: works on Windows with plain Python 3.10+."""

import argparse
import json
import mimetypes
import socket
import threading
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from endorseguard.environment import ATTACKER_EMAIL, ATTACKER_IBAN
from endorseguard.llm_agent import llm_configured
from endorseguard.monitor import run_named
from endorseguard.scenarios import load_presets, scenario_from_dict
from endorseguard.strategies import STRATEGY_CLASSES, Config

WEB = Path(__file__).resolve().parent / "web"
DEFENSES = [{"name": c.name, "description": c.description} for c in STRATEGY_CLASSES]


def summarise(result) -> dict:
    blocks = [e["reason"] for e in result.events if e.get("type") == "write" and e.get("allowed") is False]
    return {"attack_present": result.attack_present, "attack_success": result.attack_success,
            "utility": result.utility, "intended_blocked": result.intended_blocked, "approvals": result.approvals,
            "first_block": blocks[0] if blocks else None, "pending": result.pending is not None}


def api_run(body: dict) -> dict:
    sc = scenario_from_dict(body["scenario"])
    agent = body.get("agent", "simulated")
    decisions = body.get("decisions") if body.get("approver") == "human" and agent == "simulated" else None
    result = run_named(sc.world, sc.query, body.get("defense", "SIEVE"), Config.from_dict(body.get("config")),
                       decisions, agent)
    return result.to_dict()


def api_compare(body: dict) -> dict:
    sc = scenario_from_dict(body["scenario"])
    cfg = Config.from_dict(body.get("config"))
    return {"rows": [{"defense": d["name"], **summarise(run_named(sc.world, sc.query, d["name"], cfg))}
                     for d in DEFENSES]}


def api_benchmark(body: dict) -> dict:
    cfg = Config.from_dict(body.get("config"))
    scenarios = [scenario_from_dict(s) for s in body.get("scenarios", [])] or load_presets()
    rows, totals = [], {d["name"]: {"attacks": 0, "attacks_succeeded": 0, "intended": 0, "intended_done": 0,
                                    "approvals": 0} for d in DEFENSES}
    for sc in scenarios:
        cells = {}
        for d in DEFENSES:
            s = summarise(run_named(sc.world, sc.query, d["name"], cfg))
            cells[d["name"]] = s
            t = totals[d["name"]]
            if s["attack_success"] is not None:
                t["attacks"] += 1
                t["attacks_succeeded"] += int(s["attack_success"])
            if s["utility"] is not None:
                t["intended"] += 1
                t["intended_done"] += int(s["utility"])
            t["approvals"] += s["approvals"]
        rows.append({"id": sc.sid, "title": sc.title, "attack_class": sc.attack_class, "cells": cells})
    return {"rows": rows, "totals": totals}


ROUTES_GET = {
    "/api/presets": lambda: [s.raw for s in load_presets()],
    "/api/meta": lambda: {"defenses": DEFENSES, "config": Config().__dict__, "attacker_iban": ATTACKER_IBAN,
                          "attacker_email": ATTACKER_EMAIL, "llm_configured": llm_configured()},
}
ROUTES_POST = {"/api/run": api_run, "/api/compare": api_compare, "/api/benchmark": api_benchmark}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, payload: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _json(self, code: int, obj) -> None:
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ROUTES_GET:
            return self._json(200, ROUTES_GET[path]())
        file = (WEB / ("index.html" if path == "/" else path.lstrip("/"))).resolve()
        if WEB in file.parents and file.is_file():
            ctype = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
            if ctype.startswith("text/") or ctype.endswith("javascript"):
                ctype += "; charset=utf-8"
            return self._send(200, file.read_bytes(), ctype)
        self._json(404, {"error": "not found"})

    def do_POST(self):
        handler = ROUTES_POST.get(self.path.split("?")[0])
        if not handler:
            return self._json(404, {"error": "not found"})
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            self._json(200, handler(body))
        except Exception as e:  # report errors to the page instead of crashing the server
            traceback.print_exc()
            self._json(400, {"error": f"{type(e).__name__}: {e}"})

    def log_message(self, fmt, *args):
        pass


def free_port(preferred: int) -> int:
    for port in [preferred] + list(range(preferred + 1, preferred + 20)):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return 0


def main():
    ap = argparse.ArgumentParser(description="EndorseGuard dashboard")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    port = free_port(a.port)
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{server.server_port}"
    print(f"EndorseGuard dashboard running at {url}  (press Ctrl+C to stop)")
    if not a.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
