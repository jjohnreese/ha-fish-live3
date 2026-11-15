"""Reject runtime data and credential-shaped strings; never print matched values."""

from __future__ import annotations

import argparse
import re
import subprocess
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent
SKIP = {
    ".git",
    "node_modules",
    "bin",
    "obj",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    ".venv",
}
FORBIDDEN = {"data", "webview", ".storage", "node_modules"}
NAMES = {"home-assistant.json", "fish_live3_worker_secret", "secrets.yaml"}
PATTERNS = [
    re.compile(rb"gh[pousr]_[A-Za-z0-9]{24,}"),
    re.compile(rb"github_pat_[A-Za-z0-9_]{30,}"),
    re.compile(rb"(?<![A-Za-z0-9_-])sk-[A-Za-z0-9_-]{24,}"),
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb"eyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}"),
    re.compile(
        rb"(?:C:\\Users\\|/Users/|/home/)[^/\\\s\x00]+[/\\](?:Documents|AppData)[/\\]Codex", re.I
    ),
]


def inspect(name: str, data: bytes) -> list[str]:
    path = PurePosixPath(name.replace("\\", "/"))
    findings = []
    if path.is_absolute() or ".." in path.parts:
        findings.append("unsafe archive path")
    if any(part.lower() in FORBIDDEN for part in path.parts):
        findings.append("runtime/private directory")
    if (
        path.name.lower() in NAMES
        or ".dpapi" in path.name.lower()
        or path.name.startswith(".env")
        and path.name != ".env.example"
    ):
        findings.append("runtime credential/config file")
    if any(pattern.search(data) for pattern in PATTERNS):
        findings.append("credential or personal-path pattern")
    return findings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, action="append", default=[])
    args = parser.parse_args()
    findings = []
    count = 0
    if args.zip:
        for archive in args.zip:
            with zipfile.ZipFile(archive) as bundle:
                for member in bundle.infolist():
                    if member.is_dir():
                        continue
                    count += 1
                    for reason in inspect(member.filename, bundle.read(member)):
                        findings.append(f"{archive.name}/{member.filename}: {reason}")
    else:
        result = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True)
        names = (
            result.stdout.decode().split("\0")
            if result.returncode == 0
            else [
                str(p.relative_to(ROOT))
                for p in ROOT.rglob("*")
                if p.is_file() and not any(part in SKIP for part in p.relative_to(ROOT).parts)
            ]
        )
        for name in filter(None, names):
            count += 1
            for reason in inspect(name, (ROOT / name).read_bytes()):
                findings.append(f"{name}: {reason}")
    if findings:
        raise SystemExit("Public package check failed (values withheld):\n" + "\n".join(findings))
    print(
        f"Public package check passed: {count} files; no prohibited runtime data or detected credential patterns"
    )


if __name__ == "__main__":
    main()
