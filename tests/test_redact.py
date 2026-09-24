from __future__ import annotations

import pytest

from grymbl.redact import REDACTED, redact


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # The plan's reference example.
        ("psql -h prod-db -U admin -p s3cr3t", f"psql -h prod-db -U admin -p {REDACTED}"),
        ("mysql -u root -phunter2 app", f"mysql -u root -p{REDACTED} app"),
        ("redis-cli -a s3cret ping", f"redis-cli -a {REDACTED} ping"),
        (
            "psql postgres://app:pa55word@db.internal:5432/app",
            f"psql postgres://app:{REDACTED}@db.internal:5432/app",
        ),
        (
            "mongosh mongodb+srv://u:secretpw@cluster0.example.net/db",
            f"mongosh mongodb+srv://u:{REDACTED}@cluster0.example.net/db",
        ),
        (
            'curl -H "Authorization: Bearer abc.def.ghi" https://api.example.com',
            f'curl -H "Authorization: Bearer {REDACTED}" https://api.example.com',
        ),
        (
            'irm -Headers @{Authorization="Bearer abc123"} https://x.io',
            f'irm -Headers @{{Authorization="Bearer {REDACTED}"}} https://x.io',
        ),
        (
            """curl -d '{"Authorization": "Token abc"}' x.io""",
            f"""curl -d '{{"Authorization": "Token {REDACTED}"}}' x.io""",
        ),
        ("curl -u alice:wonderland https://x.io", f"curl -u alice:{REDACTED} https://x.io"),
        ("export OPENAI_API_KEY=abc123", f"export OPENAI_API_KEY={REDACTED}"),
        ('export DB_PASSWORD="two words"', f"export DB_PASSWORD={REDACTED}"),
        ('$env:GITHUB_TOKEN = "zzz"', f"$env:GITHUB_TOKEN = {REDACTED}"),
        ("STRIPE_SECRET=sk_live_x npm start", f"STRIPE_SECRET={REDACTED} npm start"),
        (
            "curl 'https://x.io/cb?token=abc&page=2'",
            f"curl 'https://x.io/cb?token={REDACTED}&page=2'",
        ),
        ("login --password hunter2 --verbose", f"login --password {REDACTED} --verbose"),
        ("deploy --token=abc123", f"deploy --token={REDACTED}"),
        ("echo sk-ant-api03-abcdefghijklmnopqrstuv", f"echo {REDACTED}"),
        ("git remote add o https://ghp_abcdefghijklmnopqrstuvwxyz0123@github.com/x", None),
        ("aws configure set aws_access_key_id AKIAABCDEFGHIJKLMNOP", None),
        (
            "http :8000 x-jwt:eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NSJ9.c2lnbmF0dXJl",
            None,
        ),
    ],
)
def test_masks_only_the_secret(raw: str, expected: str | None) -> None:
    result = redact(raw)
    if expected is None:
        assert REDACTED in result
    else:
        assert result == expected


@pytest.mark.parametrize(
    "benign",
    [
        "mkdir -p src/components",
        "docker run -p 8080:80 nginx",
        "git commit -m 'fix task-scheduler-with-long-name'",
        "pytest tests/test_auth.py -x",
        "ls -la",
    ],
)
def test_leaves_ordinary_commands_alone(benign: str) -> None:
    assert redact(benign) == benign


def test_long_lines_redact_in_linear_time() -> None:
    import time

    minified = "y" * 200_000 + " API_KEY=abc " + "Q29kZQ" * 20_000
    started = time.perf_counter()
    result = redact(minified)
    assert time.perf_counter() - started < 1.0
    assert f"API_KEY={REDACTED}" in result
