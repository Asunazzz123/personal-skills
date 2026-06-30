from __future__ import annotations

from collections.abc import Iterable

from models import ProviderHealth
from providers.base import Provider


class ProviderRegistry:
    """Own providers and enforce stable unique identifiers."""

    def __init__(self, providers: Iterable[Provider] = ()) -> None:
        self._providers: dict[str, Provider] = {}
        for provider in providers:
            self.register(provider)

    def register(self, provider: Provider) -> None:
        if provider.provider_id in self._providers:
            raise ValueError(f"duplicate provider id: {provider.provider_id}")
        self._providers[provider.provider_id] = provider

    def get(self, provider_id: str) -> Provider:
        try:
            return self._providers[provider_id]
        except KeyError as exc:
            raise KeyError(f"provider not registered: {provider_id}") from exc

    def health(self) -> dict[str, ProviderHealth]:
        return {
            provider_id: provider.health_check()
            for provider_id, provider in self._providers.items()
        }
