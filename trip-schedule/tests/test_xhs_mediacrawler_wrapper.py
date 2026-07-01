import json
from pathlib import Path

import pytest

from wrappers import xhs_mediacrawler_wrapper as wrapper


def test_xhs_wrapper_requires_mediacrawler_root(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("MEDIACRAWLER_ROOT", raising=False)

    with pytest.raises(SystemExit) as exc_info:
        wrapper.run(
            request={
                "destination": "张家界",
                "keywords": ["张家界 景点"],
                "limit": 5,
            },
            output_dir=tmp_path,
        )

    assert exc_info.value.code == 2


def test_xhs_wrapper_builds_bounded_mediacrawler_command(
    monkeypatch,
    tmp_path,
) -> None:
    root = tmp_path / "MediaCrawler"
    root.mkdir()
    (root / "main.py").write_text("print('stub')", encoding="utf-8")
    monkeypatch.setenv("MEDIACRAWLER_ROOT", str(root))
    command = wrapper.build_mediacrawler_command(
        request={
            "destination": "张家界",
            "keywords": ["张家界 景点", "张家界 旅游攻略", "ignored"],
            "limit": 50,
        },
        output_dir=tmp_path / "out",
    )

    assert command[:3] == ["python", "-c", wrapper.MEDIACRAWLER_BOOTSTRAP]
    assert "--platform" in command
    assert command[command.index("--platform") + 1] == "xhs"
    assert "--lt" in command
    assert command[command.index("--lt") + 1] == "qrcode"
    assert "--type" in command
    assert "search" in command
    assert "--keywords" in command
    assert "张家界 景点,张家界 旅游攻略" in command
    assert "--save_data_option" in command
    assert "jsonl" in command
    assert "--save_data_path" in command
    assert str(tmp_path / "out") in command
    assert "--crawler_max_notes_count" in command
    assert command[command.index("--crawler_max_notes_count") + 1] == "20"
    assert "--get_comment" in command
    assert command[command.index("--get_comment") + 1] == "false"
    assert "--get_sub_comment" in command
    assert command[command.index("--get_sub_comment") + 1] == "false"
    assert "--output_dir" not in command
    assert "--max_notes" not in command


def test_xhs_wrapper_uses_configured_login_mode(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("TRIP_XHS_LOGIN_MODE", "cookie")

    command = wrapper.build_mediacrawler_command(
        request={"destination": "张家界", "limit": 1},
        output_dir=tmp_path / "out",
    )

    assert command[command.index("--lt") + 1] == "cookie"


def test_xhs_wrapper_defaults_to_standard_browser_mode() -> None:
    env = wrapper.build_mediacrawler_env({})

    assert env["MEDIACRAWLER_ENABLE_CDP_MODE"] == "false"
    assert env["MEDIACRAWLER_CDP_CONNECT_EXISTING"] == "false"


def test_xhs_wrapper_can_request_existing_cdp_browser(monkeypatch) -> None:
    monkeypatch.setenv("TRIP_XHS_BROWSER_MODE", "cdp-existing")

    env = wrapper.build_mediacrawler_env({})

    assert env["MEDIACRAWLER_ENABLE_CDP_MODE"] == "true"
    assert env["MEDIACRAWLER_CDP_CONNECT_EXISTING"] == "true"


def test_xhs_wrapper_uses_configured_mediacrawler_python(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("MEDIACRAWLER_PYTHON", "/tmp/mediacrawler/.venv/bin/python")

    command = wrapper.build_mediacrawler_command(
        request={"destination": "张家界", "limit": 1},
        output_dir=tmp_path / "out",
    )

    assert command[0] == "/tmp/mediacrawler/.venv/bin/python"


def test_xhs_wrapper_normalizes_mediacrawler_jsonl_output(tmp_path) -> None:
    output = tmp_path / "xhs_notes.jsonl"
    output.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "title": "天门山攻略",
                        "desc": "索道和天门洞",
                        "note_url": "https://www.xiaohongshu.com/explore/1",
                        "liked_count": "1,200",
                        "collected_count": "300",
                        "comment_count": "20",
                        "source_keyword": "张家界 景点",
                    },
                    ensure_ascii=False,
                ),
                json.dumps({"title": "missing url"}, ensure_ascii=False),
            ]
        ),
        encoding="utf-8",
    )

    rows = wrapper.load_mediacrawler_rows(tmp_path)

    assert rows == [
        {
            "title": "天门山攻略",
            "desc": "索道和天门洞",
            "note_url": "https://www.xiaohongshu.com/explore/1",
            "liked_count": "1,200",
            "collected_count": "300",
            "comment_count": "20",
            "source_keyword": "张家界 景点",
        }
    ]


def test_xhs_wrapper_runs_command_and_returns_normalized_rows(
    monkeypatch,
    tmp_path,
) -> None:
    root = tmp_path / "MediaCrawler"
    root.mkdir()
    (root / "main.py").write_text("print('stub')", encoding="utf-8")
    monkeypatch.setenv("MEDIACRAWLER_ROOT", str(root))
    observed = {}

    class Completed:
        returncode = 0
        stderr = ""

    def fake_run(command, **kwargs):
        observed["command"] = command
        observed["cwd"] = kwargs["cwd"]
        output_dir = Path(command[command.index("--save_data_path") + 1])
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "notes.json").write_text(
            json.dumps(
                [
                    {
                        "title": "森林公园",
                        "desc": "袁家界和金鞭溪",
                        "url": "https://www.xiaohongshu.com/explore/2",
                        "liked_count": 10,
                        "collected_count": 4,
                        "comment_count": 1,
                    }
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return Completed()

    monkeypatch.setattr(wrapper.subprocess, "run", fake_run)

    rows = wrapper.run(
        request={"destination": "张家界", "keywords": ["张家界 景点"], "limit": 5},
        output_dir=tmp_path / "out",
    )

    assert observed["cwd"] == root
    assert rows[0]["note_url"] == "https://www.xiaohongshu.com/explore/2"
    assert rows[0]["source_keyword"] == "张家界 景点"
