from __future__ import annotations

from abc import ABC, abstractmethod

from models import ProviderHealth, ProviderResult


class Provider(ABC):
    """Read-only external data provider."""

    provider_id: str

    @abstractmethod
    def health_check(self) -> ProviderHealth:
        """Return readiness without mutating external state."""

    @abstractmethod
    def query(self, request: object) -> ProviderResult:
        """Return a normalized one-shot result."""
