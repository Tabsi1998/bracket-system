#!/usr/bin/env python3
"""Fail CI when repository source contains provider remnants or credentials."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".ico", ".woff", ".woff2", ".pdf", ".zip"}
SKIP_NAMES = {"yarn.lock", "package-lock.json"}
PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "Discord webhook": re.compile(r"https://(?:canary\.|ptb\.)?discord(?:app)?\.com/api/webhooks/\d+/[A-Za-z0-9._-]{20,}"),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    "OpenAI-style secret": re.compile(r"\bsk-[A-Za-z0-9_-]{24,}\b"),
    "Resend API key": re.compile(r"\bre_[A-Za-z0-9_-]{24,}\b"),
    "removed provider remnant": re.compile("emer" + r"gent(?:agent)?", re.IGNORECASE),
}


def repository_files() -> list[Path]:
    """Return tracked and not-ignored untracked files without scanning build output."""
    paths: set[Path] = set()
    for args in (["git", "ls-files", "-z"], ["git", "ls-files", "--others", "--exclude-standard", "-z"]):
        result = subprocess.run(args, cwd=ROOT, check=True, capture_output=True)
        paths.update(ROOT / item.decode("utf-8") for item in result.stdout.split(b"\0") if item)
    return sorted(paths)


def main() -> int:
    findings: list[str] = []
    for path in repository_files():
        if path.resolve() == Path(__file__).resolve():
            continue
        if path.suffix.lower() in SKIP_SUFFIXES or path.name in SKIP_NAMES or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for label, pattern in PATTERNS.items():
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                findings.append(f"{path.relative_to(ROOT)}:{line}: {label}")
    if findings:
        print("Potential secrets/provider remnants found:")
        print("\n".join(f"- {item}" for item in findings))
        return 1
    print("Repository-source secret scan passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
