from trip_schedule import build_parser


def test_generate_command_requires_request_and_output() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "generate",
            "--request",
            "request.json",
            "--output-root",
            "trip-output",
            "--attraction-candidates",
            "attraction_candidates.json",
        ]
    )

    assert args.command == "generate"
    assert str(args.request) == "request.json"
    assert str(args.output_root) == "trip-output"


def test_serve_command_accepts_itinerary_directory() -> None:
    parser = build_parser()
    args = parser.parse_args(["serve", "trip-output/example"])

    assert args.command == "serve"
