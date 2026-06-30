from planning.scoring import score_plan


def test_scoring_uses_approved_weights() -> None:
    score = score_plan(
        affordability=1,
        door_to_door_time=0.5,
        convenience=0.5,
        data_confidence=1,
    )

    assert score == 0.8
