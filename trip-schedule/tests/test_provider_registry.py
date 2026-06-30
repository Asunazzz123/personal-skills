from models import ProviderHealth, ProviderResult, ProviderStatus
from providers.base import Provider
from providers.registry import ProviderRegistry


class StubProvider(Provider):
    provider_id = "stub"

    def health_check(self) -> ProviderHealth:
        return ProviderHealth(
            provider_id=self.provider_id,
            status=ProviderStatus.OK,
            detail="ready",
        )

    def query(self, request: object) -> ProviderResult:
        return ProviderResult(
            provider_id=self.provider_id,
            status=ProviderStatus.OK,
            queried_at="2026-07-01T10:00:00+08:00",
            records=[],
        )


def test_registry_rejects_duplicate_provider_ids() -> None:
    registry = ProviderRegistry()
    registry.register(StubProvider())

    try:
        registry.register(StubProvider())
    except ValueError as exc:
        assert "stub" in str(exc)
    else:
        raise AssertionError("duplicate provider id was accepted")


def test_registry_reports_health_by_provider_id() -> None:
    registry = ProviderRegistry([StubProvider()])

    assert registry.health()["stub"].status is ProviderStatus.OK


def test_registry_get_returns_provider_by_id() -> None:
    provider = StubProvider()
    registry = ProviderRegistry([provider])

    assert registry.get("stub") is provider


def test_registry_get_reports_missing_provider_id() -> None:
    registry = ProviderRegistry()

    try:
        registry.get("missing")
    except KeyError as exc:
        assert "missing" in str(exc)
    else:
        raise AssertionError("missing provider id was accepted")


def test_registry_rejects_missing_provider_id() -> None:
    registry = ProviderRegistry()

    try:
        registry.register(object())  # type: ignore[arg-type]
    except ValueError as exc:
        assert "provider_id" in str(exc)
    else:
        raise AssertionError("missing provider_id was accepted")


def test_registry_rejects_empty_provider_id() -> None:
    class EmptyProvider(StubProvider):
        provider_id = ""

    registry = ProviderRegistry()

    try:
        registry.register(EmptyProvider())
    except ValueError as exc:
        assert "provider_id" in str(exc)
    else:
        raise AssertionError("empty provider_id was accepted")
