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

    assert command[:4] == ["python", "main.py", "--platform", "xhs"]
    assert "--type" in command
    assert "search" in command
    assert "--keywords" in command
    assert "张家界 景点,张家界 旅游攻略" in command
    assert "--get_comment" not in command


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
        output_dir = Path(command[command.index("--output_dir") + 1])
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
