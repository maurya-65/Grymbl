"""Pattern-based secret redaction. Fully local: no network, no model.

Only the secret portion is masked so the command stays readable:
`psql -h prod-db -U admin -p s3cret` -> `psql -h prod-db -U admin -p [REDACTED]`.
Coverage is deliberately "common formats", not exhaustive (plan §5).
"""

from __future__ import annotations

import re

REDACTED = "[REDACTED]"

_QUOTED_OR_BARE = r"""(?:"[^"]*"|'[^']*'|[^\s&"',;]+)"""

_CONNECTION_STRING = re.compile(
    r"\b((?:postgres(?:ql)?|mysql|mariadb|mongodb(?:\+srv)?|rediss?|amqps?)://[^:/@\s]*:)"
    r"([^@\s]+)(?=@)",
    re.IGNORECASE,
)
_AUTH_HEADER = re.compile(
    # curl `Authorization: ...`, PowerShell `@{Authorization="..."}`, JSON `"Authorization": "..."`
    r"(authorization[\"']?\s*[:=]\s*[\"']?(?:(?:bearer|basic|token|digest)\s+)?)([^\s'\"]+)",
    re.IGNORECASE,
)
_TOKEN_FORMATS = re.compile(
    r"(?<![A-Za-z0-9])(?:"
    r"sk-[A-Za-z0-9_-]{16,}"
    r"|gh[pousr]_[A-Za-z0-9]{20,}"
    r"|github_pat_[A-Za-z0-9_]{20,}"
    r"|AKIA[0-9A-Z]{16}"
    r"|xox[abprs]-[A-Za-z0-9-]{10,}"
    r"|eyJ[A-Za-z0-9_-]{5,}\.eyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]+"
    r")"
)
# `API_KEY=...`, `export GH_TOKEN=...`, `$env:DB_PASSWORD = ...`, `?token=...`, `"secret": "..."`
# Matches start only at a name boundary, with bounded name length: unbounded `[\w.-]*` on
# both sides backtracks quadratically through long word runs (minified code, base64).
_SECRET_ASSIGNMENT = re.compile(
    r"""(?<![\w.-])(["']?[\w.-]{0,64}?(?:key|token|secret|passw(?:or)?d|pwd|credential)"""
    r"""[\w.-]{0,64}["']?\s*[:=]\s*)"""
    rf"({_QUOTED_OR_BARE})",
    re.IGNORECASE,
)
_SECRET_FLAG = re.compile(
    r"(--(?:password|passwd|pass|token|api-?key|secret|client-secret|auth-token|access-token)"
    r"(?:=|\s+))"
    rf"({_QUOTED_OR_BARE})",
    re.IGNORECASE,
)
# `curl -u user:pass` keeps the user, masks the password.
_USER_PASSWORD_FLAG = re.compile(r"((?:^|\s)(?:-u|--user)\s+['\"]?[^:\s'\"]+:)([^\s'\"]+)")
# Short password flags are only meaningful for database clients (`mkdir -p` must survive).
_DB_CLIENT = re.compile(
    r"\b(?:psql|pg_dump|pg_restore|mysql|mysqldump|mysqladmin|mariadb|mongo|mongosh|mongodump"
    r"|redis-cli)\b"
)
_DB_PASSWORD_FLAG = re.compile(r"(?<=\s)(-[pa]\s*)([^\s-]\S*)")


def _mask_secret(match: re.Match[str]) -> str:
    """Keep the context captured in group 1, mask the secret in group 2."""
    return f"{match.group(1)}{REDACTED}"


def redact(text: str) -> str:
    """Mask every known secret shape in `text`, keeping the surrounding context."""
    text = _CONNECTION_STRING.sub(_mask_secret, text)
    text = _AUTH_HEADER.sub(_mask_secret, text)
    text = _TOKEN_FORMATS.sub(REDACTED, text)
    text = _SECRET_ASSIGNMENT.sub(_mask_secret, text)
    text = _SECRET_FLAG.sub(_mask_secret, text)
    text = _USER_PASSWORD_FLAG.sub(_mask_secret, text)
    if _DB_CLIENT.search(text):
        text = _DB_PASSWORD_FLAG.sub(_mask_secret, text)
    return text
