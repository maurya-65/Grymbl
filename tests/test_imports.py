from __future__ import annotations

from grymbl.imports import related, scan_imports

KNOWN = {
    "app/auth.py",
    "app/__init__.py",
    "app/db/models.py",
    "src/pkg/core.py",
    "tests/test_auth.py",
    "web/src/api.ts",
    "web/src/components/Login.tsx",
    "web/src/utils/index.ts",
}


def test_python_absolute_imports() -> None:
    text = "import app.auth\nfrom app.db import models\nimport requests\n"
    assert scan_imports("tests/test_auth.py", text, KNOWN) == {"app/auth.py", "app/db/models.py"}


def test_python_src_layout() -> None:
    assert scan_imports("tests/test_auth.py", "from pkg.core import run\n", KNOWN) == {
        "src/pkg/core.py"
    }


def test_python_relative_imports() -> None:
    assert scan_imports("app/auth.py", "from .db.models import User\n", KNOWN) == {
        "app/db/models.py"
    }
    assert scan_imports("app/db/models.py", "from .. import auth\n", KNOWN) == {"app/auth.py"}


def test_js_relative_imports_resolve_extensions_and_index() -> None:
    text = (
        "import { api } from '../api'\nconst u = require('../utils')\nimport React from 'react'\n"
    )
    assert scan_imports("web/src/components/Login.tsx", text, KNOWN) == {
        "web/src/api.ts",
        "web/src/utils/index.ts",
    }


def test_related_is_symmetric_over_direct_imports() -> None:
    graph = {"tests/test_auth.py": frozenset({"app/auth.py"})}
    assert related("app/auth.py", "tests/test_auth.py", graph)
    assert related("tests/test_auth.py", "app/auth.py", graph)
    assert not related("app/auth.py", "web/src/api.ts", graph)
