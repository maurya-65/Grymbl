"""Cheap static import scan (regex, no LLM) used to relate files in episode correlation.

Supports Python and JS/TS. Only imports that resolve to files inside the repo are kept;
third-party packages are irrelevant to "which of our files depend on each other".
"""

from __future__ import annotations

import posixpath
import re
from collections.abc import Iterable, Mapping, Set

_PY_SUFFIXES = (".py",)
_JS_SUFFIXES = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs")
_PY_SOURCE_ROOTS = ("", "src/")

_PY_IMPORT = re.compile(r"^\s*import\s+(.+)$", re.MULTILINE)
_PY_FROM_IMPORT = re.compile(r"^\s*from\s+(\.*)([\w.]*)\s+import\s+\(?([^)\n]+)", re.MULTILINE)
_JS_IMPORT = re.compile(
    r"""(?:\bfrom\s*|\bimport\s*\(?\s*|\brequire\s*\(\s*)['"](\.{1,2}/[^'"]+)['"]"""
)

ImportGraph = Mapping[str, Set[str]]


def scan_imports(path: str, text: str, known_files: Set[str]) -> frozenset[str]:
    """Repo files that `path` imports, resolved against `known_files`."""
    if path.endswith(_PY_SUFFIXES):
        candidates = _python_candidates(path, text)
    elif path.endswith(_JS_SUFFIXES):
        candidates = _js_candidates(path, text)
    else:
        return frozenset()
    return frozenset(c for c in candidates if c in known_files and c != path)


def related(a: str, b: str, graph: ImportGraph) -> bool:
    """Same file, or one directly imports the other."""
    return a == b or b in graph.get(a, frozenset()) or a in graph.get(b, frozenset())


def _python_module_files(module: str) -> Iterable[str]:
    base = module.replace(".", "/")
    for root in _PY_SOURCE_ROOTS:
        yield f"{root}{base}.py"
        yield f"{root}{base}/__init__.py"


def _python_candidates(path: str, text: str) -> Iterable[str]:
    for match in _PY_IMPORT.finditer(text):
        for name in match.group(1).split(","):
            module = name.split(" as ")[0].strip()
            if module:
                yield from _python_module_files(module)

    package_dir = posixpath.dirname(path)
    for match in _PY_FROM_IMPORT.finditer(text):
        dots, module, names = match.groups()
        imported = [n.split(" as ")[0].strip() for n in names.split(",")]
        if dots:
            base = package_dir
            for _ in range(len(dots) - 1):
                base = posixpath.dirname(base)
            prefix = posixpath.join(base, module.replace(".", "/")) if module else base
            prefix = prefix.lstrip("/")
            targets = [prefix] if module else []
            targets += [posixpath.join(prefix, n) for n in imported if n.isidentifier()]
            for target in targets:
                yield f"{target}.py"
                yield f"{target}/__init__.py"
        else:
            yield from _python_module_files(module)
            for name in imported:
                if name.isidentifier():
                    yield from _python_module_files(f"{module}.{name}")


def _js_candidates(path: str, text: str) -> Iterable[str]:
    directory = posixpath.dirname(path)
    for match in _JS_IMPORT.finditer(text):
        target = posixpath.normpath(posixpath.join(directory, match.group(1)))
        yield target
        for suffix in _JS_SUFFIXES:
            yield f"{target}{suffix}"
            yield f"{target}/index{suffix}"
