#!/usr/bin/env python3
"""Create a conservative first-pass sanitised copy of an n8n export.

The script removes common n8n metadata and redacts obvious personal, secret and
infrastructure values. It cannot identify every client-specific value, prompt
or business rule. Manual review is required before publication.
"""

from __future__ import annotations

import argparse
import json
import re
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

REMOVE_KEYS = {
    "activeVersion",
    "activeVersionId",
    "cachedResultName",
    "cachedResultUrl",
    "credentials",
    "creatorId",
    "homeProject",
    "pinData",
    "projectId",
    "shared",
    "staticData",
    "triggerCount",
    "userId",
    "versionCounter",
    "versionId",
    "webhookId",
    "workflowId",
    "workflowPublishHistory",
}

TOP_LEVEL_REMOVE_KEYS = {
    "createdAt",
    "id",
    "meta",
    "updatedAt",
}

SENSITIVE_KEY_PARTS = {
    "apikey",
    "api_key",
    "authorization",
    "bearer",
    "clientsecret",
    "client_secret",
    "email",
    "password",
    "phone",
    "secret",
    "token",
}

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PRIVATE_IP_RE = re.compile(
    r"\b(?:10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})\b"
)
PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d ()-]{7,}\d)(?!\w)")
UUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)
OPENAI_SECRET_RE = re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b")
BEARER_RE = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}\b", re.IGNORECASE)
LONG_TOKEN_RE = re.compile(r"\b[A-Za-z0-9_-]{40,}\b")
URL_RE = re.compile(r"https?://[^\s'\"<>]+", re.IGNORECASE)

PORTFOLIO_NAMESPACE = uuid.UUID("36ba9d52-a92a-5bc6-8a38-7b1bd3db6d28")


def replacement_uuid(value: str) -> str:
    """Return a stable, non-reversible UUID for an original identifier."""
    return str(uuid.uuid5(PORTFOLIO_NAMESPACE, value.lower()))

SENSITIVE_RESOURCE_HOSTS = {
    "docs.google.com",
    "drive.google.com",
    "sheets.googleapis.com",
    "outlook.office.com",
    "1drv.ms",
}


def normalise_key(key: str) -> str:
    return re.sub(r"[^a-z0-9_]", "", key.lower())


def key_is_sensitive(key: str) -> bool:
    normalised = normalise_key(key)
    return any(part in normalised for part in SENSITIVE_KEY_PARTS)


def redact_url(value: str, *, redact_all_urls: bool) -> str:
    if redact_all_urls:
        return "[redacted-url]"

    try:
        parts = urlsplit(value)
    except ValueError:
        return "[redacted-url]"

    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return "[redacted-url]"

    hostname = (parts.hostname or "").lower()
    if PRIVATE_IP_RE.search(hostname) or hostname in {"localhost", "127.0.0.1"}:
        return "[redacted-internal-url]"

    if hostname in SENSITIVE_RESOURCE_HOSTS or hostname.endswith(".sharepoint.com"):
        return urlunsplit((parts.scheme, parts.netloc, "/[redacted-resource]", "", ""))

    path = UUID_RE.sub(lambda match: replacement_uuid(match.group(0)), parts.path)
    path = LONG_TOKEN_RE.sub("[redacted-token-or-id]", path)
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


def redact_string(value: str, *, redact_all_urls: bool) -> str:
    value = EMAIL_RE.sub("[redacted-email]", value)
    value = PRIVATE_IP_RE.sub("[redacted-private-ip]", value)
    value = PHONE_RE.sub("[redacted-phone]", value)
    value = OPENAI_SECRET_RE.sub("[redacted-secret]", value)
    value = BEARER_RE.sub("Bearer [redacted-token]", value)
    value = URL_RE.sub(lambda match: redact_url(match.group(0), redact_all_urls=redact_all_urls), value)
    value = UUID_RE.sub(lambda match: replacement_uuid(match.group(0)), value)
    value = LONG_TOKEN_RE.sub("[redacted-token-or-id]", value)
    return value


def sanitise(
    value: Any,
    *,
    top_level: bool = False,
    parent_key: str | None = None,
    redact_all_urls: bool = False,
) -> Any:
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        for key, child in value.items():
            if key in REMOVE_KEYS or (top_level and key in TOP_LEVEL_REMOVE_KEYS):
                continue

            if key == "path" and parent_key == "parameters":
                output[key] = "portfolio-webhook-placeholder"
                continue

            if key_is_sensitive(key) and isinstance(child, (str, int, float)):
                output[key] = "[redacted-value]"
                continue

            output[key] = sanitise(
                child,
                parent_key=key,
                redact_all_urls=redact_all_urls,
            )
        return output

    if isinstance(value, list):
        return [
            sanitise(item, parent_key=parent_key, redact_all_urls=redact_all_urls)
            for item in value
        ]

    if isinstance(value, str):
        return redact_string(value, redact_all_urls=redact_all_urls)

    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Raw n8n JSON export")
    parser.add_argument("output", type=Path, help="Destination for sanitised JSON")
    parser.add_argument("--name", help="Replacement workflow name")
    parser.add_argument(
        "--redact-all-urls",
        action="store_true",
        help="Replace all URLs instead of retaining safe public hosts and paths.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.input.is_file():
        raise SystemExit(f"Input file does not exist: {args.input}")

    try:
        data = json.loads(args.input.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Could not read n8n export: {exc}") from exc

    cleaned = sanitise(
        data,
        top_level=True,
        redact_all_urls=args.redact_all_urls,
    )

    if isinstance(cleaned, dict):
        cleaned["active"] = False
        if args.name:
            cleaned["name"] = args.name

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(cleaned, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"Wrote first-pass sanitised export to {args.output}")
    print("Manual review is still required before publishing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
