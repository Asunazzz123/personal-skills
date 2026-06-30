import re
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
HEX_32 = re.compile(r"(?<![A-Za-z0-9])[0-9a-fA-F]{32}(?![A-Za-z0-9])")
ENV_ASSIGNMENT = re.compile(
    r"AMAP_(?:WEBSERVICE_KEY|JSAPI_KEY|SECURITY_KEY)"
    r"\s*=\s*[\"'](?!<)[^\"']{8,}[\"']"
)


def test_repository_contains_no_credential_values() -> None:
    offenders = []
    for path in SKILL_ROOT.rglob("*"):
        if any(part in {".pytest_cache", "__pycache__"} for part in path.parts):
            continue
        if not path.is_file() or path.suffix in {".pyc", ".png", ".jpg"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in HEX_32.finditer(text):
            offenders.append(f"{path}:{match.start()}")
        for match in ENV_ASSIGNMENT.finditer(text):
            offenders.append(f"{path}:{match.start()}")
    assert offenders == []
