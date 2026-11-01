"""EndorseGuard terminal demo (backup for the dashboard; same engine).

  python demo.py                         results matrix: all presets x 6 defenses
  python demo.py --trace S5              step-by-step trace of one scenario, every defense
  python demo.py --trace S5 -d SIEVE     ... one defense only
  python demo.py --list                  list preset scenarios
  python demo.py --live S3 -d SIEVE      real LLM agent (needs LLM_API_KEY, see llm_agent.py)

For the interactive version run:  python dashboard.py
"""

import argparse
import os
import sys

from endorseguard.monitor import run_named
from endorseguard.scenarios import load_presets
from endorseguard.strategies import STRATEGY_CLASSES

if os.name == "nt":
    os.system("")  # enable ANSI colours in the Windows console
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

GREEN, RED, YELLOW, DIM, BOLD, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[1m", "\033[0m"
DEFENSES = [c.name for c in STRATEGY_CLASSES]


def cell(r) -> tuple[str, str]:
    if r.attack_success is True:
        return "XX  ATTACKED", RED
    if r.attack_success is False:
        return ("OK  blocked, task lost" if r.intended_blocked else "OK  blocked"), GREEN
    return ("OK  task done", GREEN) if r.utility else ("XX  task blocked", YELLOW)


def print_matrix(scs, defenses, c):
    w0, w = 40, 24
    print(f"\n{c(BOLD)}EndorseGuard - simulated agent, {len(scs)} scenarios x {len(defenses)} defenses{c(RESET)}")
    print(f"{'Scenario':<{w0}}" + "".join(f"{d:<{w}}" for d in defenses))
    print("-" * (w0 + w * len(defenses)))
    tot = {d: [0, 0, 0, 0, 0] for d in defenses}
    for sc in scs:
        line = f"{(sc.sid + ' ' + sc.title)[:w0 - 2]:<{w0}}"
        for d in defenses:
            r = run_named(sc.world, sc.query, d)
            text, colour = cell(r)
            line += c(colour) + f"{text:<{w}}" + c(RESET)
            t = tot[d]
            if r.attack_success is not None:
                t[0] += 1; t[1] += int(r.attack_success)
            if r.utility is not None:
                t[2] += 1; t[3] += int(r.utility)
            t[4] += r.approvals
        print(line)
    print("-" * (w0 + w * len(defenses)))
    print(f"{'Attacks that succeeded':<{w0}}" + "".join(f"{f'{t[1]}/{t[0]}':<{w}}" for t in tot.values()))
    print(f"{'Intended actions completed':<{w0}}" + "".join(f"{f'{t[3]}/{t[2]}':<{w}}" for t in tot.values()))
    print(f"{'Approval requests':<{w0}}" + "".join(f"{t[4]:<{w}}" for t in tot.values()))


def print_trace(sc, defenses, c, agent="simulated"):
    print(f"\n{c(BOLD)}{sc.sid}: {sc.title}{c(RESET)}  [{sc.attack_class}]")
    print(f"User request: {sc.query}\n")
    for d in defenses:
        r = run_named(sc.world, sc.query, d, agent=agent)
        text, colour = cell(r)
        print(f"{c(BOLD)}-- {d}{c(RESET)}  ->  {c(colour)}{text}{c(RESET)}")
        for t in r.thoughts:
            print(f"   {c(DIM)}agent: {t}{c(RESET)}")
        for ev in r.events:
            if ev["type"] == "read":
                print(f"   read  {ev['tool']}({ev['args'] or ''})")
            elif ev["type"] == "write":
                mark = c(GREEN) + "ALLOW" if ev.get("allowed") else c(RED) + "BLOCK"
                amt = f", amount={ev['args']['amount']}" if "amount" in ev["args"] else ""
                print(f"   {mark}{c(RESET)} {ev['tool']}(recipient={ev['args']['recipient']!r}{amt})")
                print(f"         reason: {ev.get('reason')}")
                if ev.get("approval_shown"):
                    print(f"         {c(DIM)}approval prompt: {ev['approval_shown'].replace(chr(10), ' | ')}{c(RESET)}")
        print()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--trace", metavar="SID")
    ap.add_argument("-d", "--defense")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--live", metavar="SID", help="trace with a real LLM agent")
    ap.add_argument("--no-color", action="store_true")
    a = ap.parse_args()
    c = (lambda code: "") if a.no_color else (lambda code: code)
    scs = load_presets()
    by_id = {s.sid.upper(): s for s in scs}
    defenses = DEFENSES
    if a.defense:
        defenses = [d for d in DEFENSES if d.lower() == a.defense.lower()] or sys.exit(f"Unknown defense {a.defense}")
    if a.list:
        for sc in scs:
            print(f"{sc.sid}  [{sc.attack_class}] {sc.title}\n     \"{sc.query}\"\n     {sc.explanation}\n")
    elif a.trace or a.live:
        sid = (a.trace or a.live).upper()
        sc = by_id.get(sid) or sys.exit(f"Unknown scenario {sid}")
        print_trace(sc, defenses, c, agent="llm" if a.live else "simulated")
    else:
        print_matrix(scs, defenses, c)


if __name__ == "__main__":
    main()
