import pytest

from checkpoints import InteractiveSession, InteractiveStage


def test_interactive_session_advances_three_validated_stages(tmp_path) -> None:
    session = InteractiveSession.create(
        tmp_path,
        option_ids=["train:G100", "flight:EA100"],
    )
    assert session.state.stage is InteractiveStage.INTERCITY

    session.resume(
        selection_ids=["train:G100"],
        next_option_ids=["hotel:湖滨", "hotel:城站"],
    )
    assert session.state.stage is InteractiveStage.HOTEL

    session.resume(
        selection_ids=["hotel:湖滨"],
        next_option_ids=["attraction:西湖", "attraction:灵隐寺"],
    )
    assert session.state.stage is InteractiveStage.ATTRACTIONS

    session.resume(
        selection_ids=["attraction:西湖", "attraction:灵隐寺"],
        next_option_ids=[],
    )
    assert session.state.stage is InteractiveStage.COMPLETE


def test_interactive_session_rejects_unknown_option(tmp_path) -> None:
    session = InteractiveSession.create(tmp_path, option_ids=["train:G100"])

    with pytest.raises(ValueError, match="not offered"):
        session.resume(
            selection_ids=["flight:forged"],
            next_option_ids=[],
        )
