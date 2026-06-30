import subprocess

from models import ProviderStatus
from providers.xhs import XhsEvidenceProvider, XhsQuery


def test_xhs_provider_reports_missing_command(monkeypatch) -> None:
    monkeypatch.delenv("TRIP_XHS_COMMAND_JSON", raising=False)

    health = XhsEvidenceProvider().health_check()

    assert health.status is ProviderStatus.NOT_CONFIGURED


def test_xhs_provider_reports_invalid_command_json_without_leaking_config(
    monkeypatch,
) -> None:
    monkeypatch.setenv("TRIP_XHS_COMMAND_JSON", "not-json-secret-token")

    health = XhsEvidenceProvider().health_check()

    assert health.status is ProviderStatus.NOT_CONFIGURED
    assert "not-json-secret-token" not in health.detail


def test_xhs_provider_reports_non_list_command_json(monkeypatch) -> None:
    monkeypatch.setenv("TRIP_XHS_COMMAND_JSON", '{"cmd":"xhs"}')

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


def test_xhs_provider_maps_schema_error_to_schema_changed(monkeypatch) -> None:
    monkeypatch.setenv("TRIP_XHS_COMMAND_JSON", '["xhs-wrapper"]')
    provider = XhsEvidenceProvider()

    def fail(_):
        raise ValueError("crawler output must be a JSON array of objects")

    monkeypatch.setattr(provider.runner, "run", fail)

    result = provider.query(XhsQuery(destination="杭州"))

    assert result.status is ProviderStatus.SCHEMA_CHANGED
    assert result.error_kind == "external_crawler_schema"


def test_xhs_provider_maps_missing_executable_to_not_configured(monkeypatch) -> None:
    monkeypatch.setenv("TRIP_XHS_COMMAND_JSON", '["xhs-wrapper"]')
    provider = XhsEvidenceProvider()

    def fail(_):
        raise FileNotFoundError("xhs-wrapper")

    monkeypatch.setattr(provider.runner, "run", fail)

    result = provider.query(XhsQuery(destination="杭州"))

    assert result.status is ProviderStatus.NOT_CONFIGURED


def test_xhs_provider_maps_timeout_to_network_error(monkeypatch) -> None:
    monkeypatch.setenv("TRIP_XHS_COMMAND_JSON", '["xhs-wrapper"]')
    provider = XhsEvidenceProvider()

    def fail(_):
        raise subprocess.TimeoutExpired("xhs-wrapper", 120)

    monkeypatch.setattr(provider.runner, "run", fail)

    result = provider.query(XhsQuery(destination="杭州"))

    assert result.status is ProviderStatus.NETWORK_ERROR
    assert result.error_kind == "external_crawler_timeout"


def test_xhs_provider_skips_rows_without_note_url(monkeypatch) -> None:
    monkeypatch.setenv("TRIP_XHS_COMMAND_JSON", '["xhs-wrapper"]')
    provider = XhsEvidenceProvider()
    monkeypatch.setattr(
        provider.runner,
        "run",
        lambda _: [
            {
                "title": "缺少链接",
                "desc": "这条记录没有来源 URL",
                "liked_count": "10",
            }
        ],
    )

    result = provider.query(XhsQuery(destination="杭州"))

    assert result.status is ProviderStatus.SCHEMA_CHANGED
    assert result.records == []
    assert result.warnings


def test_xhs_provider_accepts_count_values_with_commas(monkeypatch) -> None:
    monkeypatch.setenv("TRIP_XHS_COMMAND_JSON", '["xhs-wrapper"]')
    provider = XhsEvidenceProvider()
    monkeypatch.setattr(
        provider.runner,
        "run",
        lambda _: [
            {
                "title": "杭州两日路线",
                "desc": "西湖适合安排半天",
                "liked_count": "1,200",
                "collected_count": "850",
                "comment_count": "95",
                "note_url": "https://www.xiaohongshu.com/explore/example1",
                "source_keyword": "杭州 景点",
            }
        ],
    )

    result = provider.query(XhsQuery(destination="杭州"))

    assert result.status is ProviderStatus.OK
    assert result.records[0]["engagement_score"] == 2995
