from models import HotelOption, ProviderStatus
from providers.hotels import HotelProvider, HotelQuery


def test_hotel_provider_requires_configured_wrapper(monkeypatch) -> None:
    monkeypatch.delenv("TRIP_HOTEL_COMMAND_JSON", raising=False)

    assert HotelProvider().health_check().status is ProviderStatus.NOT_CONFIGURED


def test_hotel_provider_validates_total_stay_price(monkeypatch) -> None:
    monkeypatch.setenv("TRIP_HOTEL_COMMAND_JSON", '["hotel-wrapper"]')
    provider = HotelProvider()
    monkeypatch.setattr(
        provider.runner,
        "run",
        lambda _: [
            {
                "name": "湖滨示例酒店",
                "latitude": 30.257,
                "longitude": 120.164,
                "total_price_cny": 920,
                "nights": 2,
                "source": "configured-hotel-crawler",
                "source_url": "https://example.invalid/hotel/1",
            }
        ],
    )

    result = provider.query(
        HotelQuery(
            destination="杭州",
            check_in="2026-07-10",
            check_out="2026-07-12",
            travelers=2,
        )
    )

    hotel = HotelOption.model_validate(result.records[0])
    assert hotel.total_price_cny == 920
    assert hotel.nights == 2
