from __future__ import annotations

import json
from pathlib import Path


class StationIndex:
    """Bidirectional station-name index loaded once per provider instance."""

    def __init__(self, path: Path) -> None:
        data = json.loads(path.read_text(encoding="utf-8"))
        pairs: list[tuple[str, str]] = []
        self.city_to_stations: dict[str, list[str]] = {}
        for city in data:
            city_name = city.get("city")
            names: list[str] = []
            for station in city.get("stations", []):
                name = station.get("station")
                code = station.get("id")
                if name and code:
                    pairs.append((name, code))
                    names.append(name)
            if city_name and names:
                self.city_to_stations[city_name] = names
        self.name_to_code = dict(pairs)
        self.code_to_name = {code: name for name, code in pairs}

    def code_for(self, name: str) -> str:
        try:
            return self.name_to_code[name]
        except KeyError as exc:
            raise ValueError(f"unknown station: {name}") from exc

    def name_for(self, code: str) -> str:
        return self.code_to_name.get(code, code)

    def stations_for_city(self, city: str, *, limit: int = 5) -> list[str]:
        direct = self.city_to_stations.get(city)
        if direct:
            return direct[:limit]
        matching = [name for name in self.name_to_code if name.startswith(city)]
        return matching[:limit]
