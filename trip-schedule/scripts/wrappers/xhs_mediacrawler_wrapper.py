from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


SENSITIVE_WORDS = ("cookie", "token", "authorization", "sign", "profile")

MEDIACRAWLER_BOOTSTRAP = (
    "import os;"
    "import config;"
    "config.ENABLE_CDP_MODE=os.getenv('MEDIACRAWLER_ENABLE_CDP_MODE','false').lower() in ('1','true','yes','y','t');"
    "config.CDP_CONNECT_EXISTING=os.getenv('MEDIACRAWLER_CDP_CONNECT_EXISTING','false').lower() in ('1','true','yes','y','t');"
    "config.BROWSER_LAUNCH_TIMEOUT=int(os.getenv('MEDIACRAWLER_BROWSER_LAUNCH_TIMEOUT','15'));"
    "from tools.app_runner import run;"
    "import main as mediacrawler_main;"
    "run(mediacrawler_main.main, mediacrawler_main.async_cleanup, cleanup_timeout_seconds=15.0)"
)


def _fail(message: str, *, code: int = 2) -> None:
    print(_redact(message), file=sys.stderr)
    raise SystemExit(code)


def _redact(message: str) -> str:
    redacted = message
    for word in SENSITIVE_WORDS:
        redacted = redacted.replace(word, f"{word[:2]}[redacted]")
        redacted = redacted.replace(word.upper(), f"{word[:2].upper()}[REDACTED]")
    return redacted[-1000:]


def _media_root() -> Path:
    raw = os.getenv("MEDIACRAWLER_ROOT")
    if not raw:
        _fail("MEDIACRAWLER_ROOT is required for the XHS MediaCrawler wrapper.")
    root = Path(raw).expanduser().resolve()
    if not (root / "main.py").is_file():
        _fail("MEDIACRAWLER_ROOT must point to a MediaCrawler checkout with main.py.")
    return root


def _keywords(request: dict[str, Any]) -> list[str]:
    raw_keywords = request.get("keywords")
    if isinstance(raw_keywords, list):
        keywords = [str(item).strip() for item in raw_keywords if str(item).strip()]
    else:
        destination = str(request.get("destination", "")).strip()
        keywords = [f"{destination} 景点", f"{destination} 旅游攻略"] if destination else []
    return keywords[:2]


def _limit(request: dict[str, Any]) -> int:
    try:
        return max(1, min(20, int(request.get("limit", 10))))
    except (TypeError, ValueError):
        return 10


def _login_mode() -> str:
    raw = os.getenv("TRIP_XHS_LOGIN_MODE", "qrcode").strip().lower()
    if raw not in {"qrcode", "phone", "cookie"}:
        _fail("TRIP_XHS_LOGIN_MODE must be one of qrcode, phone, or cookie.")
    return raw


def build_mediacrawler_env(base_env: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(base_env if base_env is not None else os.environ)
    browser_mode = os.getenv("TRIP_XHS_BROWSER_MODE", "standard").strip().lower()
    if browser_mode == "standard":
        enable_cdp = "false"
        connect_existing = "false"
    elif browser_mode == "cdp-new":
        enable_cdp = "true"
        connect_existing = "false"
    elif browser_mode == "cdp-existing":
        enable_cdp = "true"
        connect_existing = "true"
    else:
        _fail("TRIP_XHS_BROWSER_MODE must be one of standard, cdp-new, or cdp-existing.")
    env["MEDIACRAWLER_ENABLE_CDP_MODE"] = enable_cdp
    env["MEDIACRAWLER_CDP_CONNECT_EXISTING"] = connect_existing
    env.setdefault(
        "MEDIACRAWLER_BROWSER_LAUNCH_TIMEOUT",
        os.getenv("TRIP_XHS_BROWSER_LAUNCH_TIMEOUT", "15"),
    )
    env.setdefault("PYTHONUNBUFFERED", "1")
    return env


def build_mediacrawler_command(
    *,
    request: dict[str, Any],
    output_dir: Path,
) -> list[str]:
    keywords = _keywords(request)
    if not keywords:
        _fail("request must include destination or non-empty keywords.")
    python_executable = os.getenv("MEDIACRAWLER_PYTHON", "python")
    return [
        python_executable,
        "-c",
        MEDIACRAWLER_BOOTSTRAP,
        "--platform",
        "xhs",
        "--lt",
        _login_mode(),
        "--type",
        "search",
        "--keywords",
        ",".join(keywords),
        "--save_data_option",
        "jsonl",
        "--save_data_path",
        str(output_dir),
        "--crawler_max_notes_count",
        str(_limit(request)),
        "--get_comment",
        "false",
        "--get_sub_comment",
        "false",
        "--headless",
        "false",
    ]


def _load_json_file(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("notes", "data", "items", "results"):
            rows = payload.get(key)
            if isinstance(rows, list):
                return [item for item in rows if isinstance(item, dict)]
    return []


def _load_jsonl_file(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _normalize_row(row: dict[str, Any], *, fallback_keyword: str = "") -> dict[str, Any] | None:
    note_url = row.get("note_url") or row.get("url") or row.get("source_url")
    if not isinstance(note_url, str) or not note_url.strip():
        return None
    return {
        "title": str(row.get("title") or row.get("display_title") or ""),
        "desc": str(row.get("desc") or row.get("description") or ""),
        "note_url": note_url.strip(),
        "source_keyword": str(row.get("source_keyword") or fallback_keyword),
        "liked_count": row.get("liked_count") or row.get("liked") or row.get("likes") or 0,
        "collected_count": row.get("collected_count")
        or row.get("collected")
        or row.get("collect_count")
        or 0,
        "comment_count": row.get("comment_count") or row.get("comments") or 0,
    }


def load_mediacrawler_rows(output_dir: Path, *, fallback_keyword: str = "") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(output_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix == ".json":
            raw_rows = _load_json_file(path)
        elif path.suffix == ".jsonl":
            raw_rows = _load_jsonl_file(path)
        else:
            continue
        for row in raw_rows:
            normalized = _normalize_row(row, fallback_keyword=fallback_keyword)
            if normalized is not None:
                rows.append(normalized)
    return rows


def run(
    *,
    request: dict[str, Any],
    output_dir: Path,
) -> list[dict[str, Any]]:
    root = _media_root()
    output_dir.mkdir(parents=True, exist_ok=True)
    command = build_mediacrawler_command(request=request, output_dir=output_dir)
    completed = subprocess.run(
        command,
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
        shell=False,
        env=build_mediacrawler_env(),
    )
    if completed.returncode != 0:
        _fail(
            "MediaCrawler failed or requires user action: "
            f"{_redact(completed.stderr or completed.stdout)}"
        )
    rows = load_mediacrawler_rows(
        output_dir,
        fallback_keyword=(_keywords(request) or [""])[0],
    )
    return rows[: _limit(request)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request-json", required=True)
    args = parser.parse_args(argv)
    request = json.loads(args.request_json)
    output_dir = Path(
        os.getenv("TRIP_XHS_OUTPUT_DIR", "tmp/trip-schedule-debug/xhs-output")
    )
    rows = run(request=request, output_dir=output_dir)
    print(json.dumps(rows, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
