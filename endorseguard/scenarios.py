"""Scenario presets are plain JSON files in presets/. Each holds only the user's
request and the world (contacts, documents, inbox); the agent decides what to do
and the oracle decides what the user intended. Edit them, or build new ones in the
dashboard."""

import json
from dataclasses import dataclass
from pathlib import Path

from .environment import World

PRESET_DIR = Path(__file__).resolve().parent.parent / "presets"


@dataclass
class Scenario:
    sid: str
    title: str
    attack_class: str
    query: str
    world: World
    explanation: str = ""
    raw: dict | None = None


def scenario_from_dict(d: dict) -> Scenario:
    return Scenario(d.get("id", "custom"), d.get("title", "Custom scenario"), d.get("attack_class", "custom"),
                    d.get("query", ""), World.from_dict(d), d.get("explanation", ""), d)


def load_presets() -> list[Scenario]:
    out = []
    for path in sorted(PRESET_DIR.glob("*.json")):
        with open(path, encoding="utf-8") as f:
            out.append(scenario_from_dict(json.load(f)))
    return out
