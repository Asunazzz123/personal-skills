from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]


def test_skill_requires_generation_mode_and_six_inputs() -> None:
    text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    for phrase in (
        "origin city",
        "destination",
        "budget",
        "departure",
        "trip duration",
        "number of travelers",
        "one-shot",
        "interactive",
    ):
        assert phrase in text.lower()


def test_readme_has_placeholder_only_amap_setup() -> None:
    text = (SKILL_ROOT / "README.md").read_text(encoding="utf-8")
    for variable in (
        "AMAP_WEBSERVICE_KEY",
        "AMAP_JSAPI_KEY",
        "AMAP_SECURITY_KEY",
    ):
        assert variable in text
    assert "conda activate agent" not in text
    assert "pip install -r requirements.txt" in text


def test_skill_states_read_only_boundary() -> None:
    text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8").lower()
    assert "do not book" in text
    assert "do not pay" in text
    assert "do not bypass" in text
