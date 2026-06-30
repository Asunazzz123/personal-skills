from render_html import render_itinerary


def test_rendered_html_contains_no_amap_credentials(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AMAP_JSAPI_KEY", "js-secret")
    monkeypatch.setenv("AMAP_SECURITY_KEY", "security-secret")
    output = tmp_path / "itinerary.html"

    render_itinerary(
        output_path=output,
        plan={"plans": []},
        geojson={"type": "FeatureCollection", "features": []},
    )

    html = output.read_text(encoding="utf-8")
    assert "js-secret" not in html
    assert "security-secret" not in html
    assert "/runtime-config" in html
    assert "routes.geojson" in html


def test_template_has_daily_route_and_budget_panels(tmp_path) -> None:
    output = tmp_path / "itinerary.html"
    render_itinerary(
        output_path=output,
        plan={"plans": [{"label": "balanced", "total_cost_cny": 3000}]},
        geojson={"type": "FeatureCollection", "features": []},
    )

    html = output.read_text(encoding="utf-8")
    assert 'id="map"' in html
    assert 'id="timeline"' in html
    assert 'id="budget"' in html
    assert 'id="evidence"' in html
    assert "new AMap.Polyline" in html
    assert "new AMap.Marker" in html
    assert "map.setFitView" in html
