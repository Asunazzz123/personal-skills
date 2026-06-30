import pytest
from pydantic import ValidationError

from models import ProviderResult, ProviderStatus
from planning.attraction_resolver import AttractionCandidate, AttractionResolver


class FakeAMap:
    def search_poi(self, keyword: str, *, city: str) -> ProviderResult:
        return ProviderResult(
            provider_id="amap-webservice",
            status=ProviderStatus.OK,
            queried_at="2026-07-01T10:00:00+08:00",
            records=[
                {
                    "name": "西湖风景名胜区",
                    "address": "杭州市西湖区",
                    "longitude": 120.150,
                    "latitude": 30.250,
                }
            ],
        )


def test_resolver_combines_media_evidence_with_amap_coordinates() -> None:
    candidate = AttractionCandidate(
        name="西湖",
        description="建议预留三小时",
        source_url="https://www.xiaohongshu.com/explore/example",
        queried_at="2026-07-01T09:00:00+08:00",
        suggested_visit_minutes=180,
        ticket_price_cny=0,
    )

    attractions, warnings = AttractionResolver(FakeAMap()).resolve(
        [candidate],
        city="杭州",
    )

    assert warnings == []
    assert attractions[0].name == "西湖风景名胜区"
    assert attractions[0].longitude == 120.150
    assert attractions[0].evidence[0].source == "Xiaohongshu"


def test_attraction_candidate_rejects_unexpected_fields() -> None:
    with pytest.raises(ValidationError):
        AttractionCandidate(
            name="西湖",
            description="建议预留三小时",
            source_url="https://www.xiaohongshu.com/explore/example",
            queried_at="2026-07-01T09:00:00+08:00",
            suggested_visit_minutes=180,
            ticket_price_cny=0,
            unexpected="x",
        )


class FakeAMapWithInvalidThenValidPOI:
    def search_poi(self, keyword: str, *, city: str) -> ProviderResult:
        return ProviderResult(
            provider_id="amap-webservice",
            status=ProviderStatus.OK,
            queried_at="2026-07-01T10:00:00+08:00",
            records=[
                {
                    "name": "西湖风景名胜区",
                    "address": "杭州市西湖区",
                },
                {
                    "name": "西湖风景名胜区",
                    "address": "杭州市西湖区",
                    "longitude": 120.150,
                    "latitude": 30.250,
                },
            ],
        )


def test_resolver_uses_next_valid_poi_when_first_record_is_invalid() -> None:
    candidate = AttractionCandidate(
        name="西湖",
        description="建议预留三小时",
        source_url="https://www.xiaohongshu.com/explore/example",
        queried_at="2026-07-01T09:00:00+08:00",
        suggested_visit_minutes=180,
        ticket_price_cny=0,
    )

    attractions, warnings = AttractionResolver(
        FakeAMapWithInvalidThenValidPOI()
    ).resolve(
        [candidate],
        city="杭州",
    )

    assert warnings == []
    assert attractions[0].name == "西湖风景名胜区"
    assert attractions[0].longitude == 120.150


class FakeAMapWithOnlyInvalidPOI:
    def search_poi(self, keyword: str, *, city: str) -> ProviderResult:
        return ProviderResult(
            provider_id="amap-webservice",
            status=ProviderStatus.OK,
            queried_at="2026-07-01T10:00:00+08:00",
            records=[
                {
                    "name": "西湖风景名胜区",
                    "address": "杭州市西湖区",
                }
            ],
        )


def test_resolver_warns_without_raising_when_all_pois_are_invalid() -> None:
    candidate = AttractionCandidate(
        name="西湖",
        description="建议预留三小时",
        source_url="https://www.xiaohongshu.com/explore/example",
        queried_at="2026-07-01T09:00:00+08:00",
        suggested_visit_minutes=180,
        ticket_price_cny=0,
    )

    attractions, warnings = AttractionResolver(FakeAMapWithOnlyInvalidPOI()).resolve(
        [candidate],
        city="杭州",
    )

    assert attractions == []
    assert warnings == ["AMap returned invalid POI: 西湖"]
