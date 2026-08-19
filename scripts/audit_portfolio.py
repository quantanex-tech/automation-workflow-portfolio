#!/usr/bin/env python3
"""Scan a portfolio repository for common secrets and personal data."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

TEXT_EXTENSIONS = {
    ".css", ".html", ".js", ".json", ".md", ".mmd", ".py", ".ts", ".txt", ".yaml", ".yml"
}
IGNORE_DIRS = {".git", ".idea", ".vscode", "__pycache__", "private", "raw", "unsanitised"}

PATTERNS = {
    "email address": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    "private IPv4 address": re.compile(
        r"\b(?:10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})\b"
    ),
    "possible phone number": re.compile(r"(?<!\w)(?:\+?\d[\d ()-]{7,}\d)(?!\w)"),
    "OpenAI-style secret": re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    "GitHub token": re.compile(r"\b(?:ghp|github_pat)_[A-Za-z0-9_]{20,}\b"),
    "bearer token": re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}\b", re.IGNORECASE),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "n8n credentials object": re.compile(r'"credentials"\s*:'),
    "n8n pinned data": re.compile(r'"pinData"\s*:'),
    "n8n webhook identifier": re.compile(r'"webhookId"\s*:'),
    "cached resource URL": re.compile(r'"cachedResultUrl"\s*:'),
    "likely secret setting": re.compile(
        r"\b(?:api[_-]?key|token|secret|password)\s*[:=]\s*['\"]?[^\s,'\"}]{6,}",
        re.IGNORECASE,
    ),
}

PLACEHOLDERS = {
    "[redacted-email]",
    "[redacted-phone]",
    "[redacted-private-ip]",
    "[redacted-secret]",
    "[redacted-token]",
}


def iter_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        if any(part in IGNORE_DIRS for part in path.parts):
            continue
        yield path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", default=".", type=Path, help="Repository path")
    args = parser.parse_args()

    root = args.path.resolve()
    findings: list[str] = []

    for path in iter_files(root):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            findings.append(f"{path}: could not read file: {exc}")
            continue

        for line_number, line in enumerate(text.splitlines(), start=1):
            check_line = line
            for placeholder in PLACEHOLDERS:
                check_line = check_line.replace(placeholder, "")
            for label, pattern in PATTERNS.items():
                if pattern.search(check_line):
                    findings.append(f"{path.relative_to(root)}:{line_number}: {label}")

    if findings:
        print("Potentially sensitive content found:")
        for finding in findings:
            print(f"- {finding}")
        print("\nReview each finding manually before publishing.")
        return 1

    print("No common sensitive patterns found. Manual review is still required.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
