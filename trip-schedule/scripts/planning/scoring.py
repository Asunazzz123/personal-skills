def score_plan(
    *,
    affordability: float,
    door_to_door_time: float,
    convenience: float,
    data_confidence: float,
) -> float:
    values = (
        affordability,
        door_to_door_time,
        convenience,
        data_confidence,
    )
    if any(value < 0 or value > 1 for value in values):
        raise ValueError("component scores must be between 0 and 1")
    return round(
        0.40 * affordability
        + 0.25 * door_to_door_time
        + 0.15 * convenience
        + 0.20 * data_confidence,
        4,
    )
