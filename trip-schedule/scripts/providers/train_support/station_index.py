from __future__ import annotations

import json
from pathlib import Path


class StationIndex:
    """Bidirectional station-name index loaded once per provider instance."""

    def __init__(self, path: Path) -> None:
        data = json.loads(path.read_text(encoding="utf-8"))
        pairs = [
            (station["station"], station["id"])
            for city in data
            for station in city.get("stations", [])
            if station.get("station") and station.get("id")
        ]
        self.name_to_code = dict(pairs)
        self.code_to_name = {code: name for name, code in pairs}

    def code_for(self, name: str) -> str:
        try:
            return self.name_to_code[name]
        except KeyError as exc:
            raise ValueError(f"unknown station: {name}") from exc

    def name_for(self, code: str) -> str:
        return self.code_to_name.get(code, code)
