from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


def render_itinerary(
    *,
    output_path: Path,
    plan: dict,
    geojson: dict,
) -> None:
    assets_dir = Path(__file__).resolve().parents[1] / "assets"
    environment = Environment(
        loader=FileSystemLoader(assets_dir),
        autoescape=select_autoescape(("html", "xml")),
    )
    template = environment.get_template("itinerary-template.html")
    output_path.write_text(
        template.render(
            title="Trip Schedule",
            plan_json=json.dumps(plan, ensure_ascii=False).replace("</", "<\\/"),
        ),
        encoding="utf-8",
    )
    (output_path.parent / "routes.geojson").write_text(
        json.dumps(geojson, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
