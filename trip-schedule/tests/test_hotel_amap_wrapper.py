import json

import pytest

from wrappers import hotel_amap_wrapper as wrapper


def test_hotel_amap_wrapper_requires_webservice_key(monkeypatch) -> None:
    monkeypatch.delenv("AMAP_WEBSERVICE_KEY", raising=False)

    with pytest.raises(SystemExit) as exc_info:
        wrapper.fetch_hotels(
            request={
                "destination": "张家界",
                "check_in": "2026-07-02",
                "check_out": "2026-07-05",
                "travelers": 2,
            }
        )

    assert exc_info.value.code == 2


def test_hotel_amap_wrapper_normalizes_poi_rows(monkeypatch) -> None:
    monkeypatch.setenv("AMAP_WEBSERVICE_KEY", "secret-value")

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "status": "1",
                "pois": [
                    {
                        "name": "武陵源标志门酒店",
                        "location": "110.545,29.346",
                        "address": "武陵源区",
                        "biz_ext": {"rating": "4.6"},
                    }
                ],
            }

    observed = {}

    def fake_get(url, *, params, timeout):
        observed["url"] = url
        observed["params"] = params
        observed["timeout"] = timeout
        return Response()

    monkeypatch.setattr(wrapper.requests, "get", fake_get)

    rows = wrapper.fetch_hotels(
        request={
            "destination": "张家界",
            "check_in": "2026-07-02",
            "check_out": "2026-07-05",
            "travelers": 2,
        }
    )

    assert observed["params"]["city"] == "张家界"
    assert observed["params"]["keywords"] == "张家界 酒店"
    assert rows == [
        {
            "name": "武陵源标志门酒店",
            "latitude": 29.346,
            "longitude": 110.545,
            "address": "武陵源区",
            "total_price_cny": None,
            "rating": 4.6,
            "review_count": None,
            "transit_notes": ["AMap hotel POI candidate; verify live room price separately."],
            "source": "AMap",
            "source_url": "https://lbs.amap.com/",
        }
    ]


def test_hotel_amap_wrapper_applies_price_overrides(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("AMAP_WEBSERVICE_KEY", "secret-value")
    price_path = tmp_path / "hotel_prices.json"
    price_path.write_text(
        json.dumps({"武陵源标志门酒店": 1288}, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setenv("TRIP_HOTEL_PRICE_OVERRIDES", str(price_path))

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "status": "1",
                "pois": [
                    {
                        "name": "武陵源标志门酒店",
                        "location": "110.545,29.346",
                        "address": "武陵源区",
                    }
                ],
            }

    monkeypatch.setattr(wrapper.requests, "get", lambda *args, **kwargs: Response())

    rows = wrapper.fetch_hotels(
        request={
            "destination": "张家界",
            "check_in": "2026-07-02",
            "check_out": "2026-07-05",
            "travelers": 2,
        }
    )

    assert rows[0]["total_price_cny"] == 1288


def test_hotel_amap_wrapper_returns_nonzero_on_amap_error(monkeypatch) -> None:
    monkeypatch.setenv("AMAP_WEBSERVICE_KEY", "secret-value")

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"status": "0", "info": "INVALID_USER_KEY secret-value"}

    monkeypatch.setattr(wrapper.requests, "get", lambda *args, **kwargs: Response())

    with pytest.raises(SystemExit) as exc_info:
        wrapper.fetch_hotels(request={"destination": "张家界"})

    assert exc_info.value.code == 2
