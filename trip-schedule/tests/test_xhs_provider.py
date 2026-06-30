from models import ProviderStatus
from providers.xhs import XhsEvidenceProvider, XhsQuery


def test_xhs_provider_reports_missing_command(monkeypatch) -> None:
    monkeypatch.delenv("TRIP_XHS_COMMAND_JSON", raising=False)

    health = XhsEvidenceProvider().health_check()

    assert health.status is ProviderStatus.NOT_CONFIGURED


def test_xhs_provider_preserves_source_evidence(monkeypatch) -> None:
    monkeypatch.setenv("TRIP_XHS_COMMAND_JSON", '["xhs-wrapper"]')
    provider = XhsEvidenceProvider()
    monkeypatch.setattr(
        provider.runner,
        "run",
        lambda _: [
            {
                "title": "杭州两日路线",
                "desc": "西湖适合安排半天",
                "liked_count": "1200",
                "collected_count": "850",
                "comment_count": "95",
                "note_url": "https://www.xiaohongshu.com/explore/example1",
                "source_keyword": "杭州 景点",
            }
        ],
    )

    result = provider.query(XhsQuery(destination="杭州", limit=10))

    assert result.status is ProviderStatus.OK
    assert result.records[0]["source_url"].endswith("example1")
    assert result.records[0]["engagement_score"] > 0
