from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from providers.amap import AMapProvider
from providers.flight import FlightProvider
from providers.hotels import HotelProvider
from providers.registry import ProviderRegistry
from providers.train_12306 import Train12306Provider
from providers.xhs import XhsEvidenceProvider


def build_registry() -> ProviderRegistry:
    return ProviderRegistry(
        [
            Train12306Provider(),
            FlightProvider(),
            XhsEvidenceProvider(),
            HotelProvider(),
            AMapProvider(),
        ]
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="trip-schedule")
    subparsers = parser.add_subparsers(dest="command", required=True)

    health_parser = subparsers.add_parser("health")
    health_parser.add_argument("--json", action="store_true")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "health":
        health = build_registry().health()
        if args.json:
            payload = {
                provider_id: provider_health.model_dump(mode="json")
                for provider_id, provider_health in health.items()
            }
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        else:
            for provider_id, provider_health in health.items():
                print(
                    f"{provider_id}: "
                    f"{provider_health.status} - {provider_health.detail}"
                )
        return 0

    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
