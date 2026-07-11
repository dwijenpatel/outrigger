"""Held-out tests: pinned layout + pinned toolchain configs (GL1-scaffold spec).

Spec pins the exact directory layout, an exact [tool.mypy] config, an
exact tsconfig.json, package.json (typescript ^5 sole devDependency +
typecheck script), a committed package-lock.json, .gitignore covering
node_modules/, and the requirements.txt package set.
"""

import json
import re
import tomllib
from pathlib import Path

import app as app_pkg

PROJECT_ROOT = Path(app_pkg.__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# layout
# ---------------------------------------------------------------------------

PINNED_PATHS = [
    "requirements.txt",
    "pyproject.toml",
    "tsconfig.json",
    "package.json",
    "package-lock.json",
    ".gitignore",
    "app/__init__.py",
    "app/config.py",
    "app/db.py",
    "app/models.py",
    "app/routes/__init__.py",
    "app/services/__init__.py",
    "app/templates/base.html",
    "app/static/styles.css",
    "tests/conftest.py",
    "tests/test_health.py",
    "run.py",
]


def test_pinned_layout_files_exist():
    missing = [p for p in PINNED_PATHS if not (PROJECT_ROOT / p).exists()]
    assert not missing, f"pinned layout files missing: {missing}"


# ---------------------------------------------------------------------------
# pyproject.toml — mypy config (pinned exactly)
# ---------------------------------------------------------------------------


def _mypy_config():
    data = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text())
    assert "tool" in data and "mypy" in data["tool"], (
        "pyproject.toml must contain a [tool.mypy] section"
    )
    return data["tool"]["mypy"]


def test_mypy_config_core_flags():
    cfg = _mypy_config()
    assert cfg.get("python_version") == "3.14"
    assert cfg.get("strict") is True
    assert cfg.get("warn_unreachable") is True
    assert cfg.get("warn_unused_configs") is True
    assert cfg.get("plugins") == ["pydantic.mypy"]


def test_mypy_config_overrides():
    overrides = _mypy_config().get("overrides", [])
    by_module = {o.get("module"): o for o in overrides}

    passlib = by_module.get("passlib.*")
    assert passlib is not None, "missing [[tool.mypy.overrides]] for passlib.*"
    assert passlib.get("ignore_missing_imports") is True

    tests = by_module.get("tests.*")
    assert tests is not None, "missing [[tool.mypy.overrides]] for tests.*"
    assert tests.get("disallow_untyped_defs") is False
    assert tests.get("disallow_untyped_decorators") is False


# ---------------------------------------------------------------------------
# tsconfig.json (pinned exactly)
# ---------------------------------------------------------------------------

EXPECTED_TSCONFIG = {
    "compilerOptions": {
        "allowJs": True,
        "checkJs": True,
        "noEmit": True,
        "strict": True,
        "noUncheckedIndexedAccess": True,
        "noImplicitOverride": True,
        "noFallthroughCasesInSwitch": True,
        "target": "es2022",
        "module": "es2022",
        "lib": ["es2022", "dom", "dom.iterable"],
        "types": [],
    },
    "include": ["app/static/**/*.js"],
}


def test_tsconfig_matches_pinned_content_exactly():
    data = json.loads((PROJECT_ROOT / "tsconfig.json").read_text())
    assert data == EXPECTED_TSCONFIG


# ---------------------------------------------------------------------------
# package.json / package-lock.json / .gitignore
# ---------------------------------------------------------------------------


def test_package_json_typescript_sole_devdep_and_typecheck_script():
    data = json.loads((PROJECT_ROOT / "package.json").read_text())

    dev = data.get("devDependencies", {})
    assert list(dev.keys()) == ["typescript"], (
        f"typescript must be the SOLE devDependency, got {sorted(dev)}"
    )
    assert re.match(r"\^5(\.|$)", dev["typescript"]), (
        f"typescript devDependency must be ^5, got {dev['typescript']!r}"
    )

    scripts = data.get("scripts", {})
    assert "typecheck" in scripts, "package.json must define a typecheck script"
    assert "tsc" in scripts["typecheck"]
    assert "noEmit" in scripts["typecheck"]


def test_package_lock_is_committed():
    lock = PROJECT_ROOT / "package-lock.json"
    assert lock.exists() and lock.stat().st_size > 0


def test_gitignore_covers_node_modules():
    lines = [
        ln.strip()
        for ln in (PROJECT_ROOT / ".gitignore").read_text().splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    assert any("node_modules" in ln and not ln.startswith("!") for ln in lines), (
        ".gitignore must ignore node_modules/ (git status is gate input)"
    )


# ---------------------------------------------------------------------------
# requirements.txt
# ---------------------------------------------------------------------------

PINNED_REQUIREMENTS = {
    "fastapi",
    "uvicorn",
    "jinja2",
    "sqlalchemy",
    "passlib",
    "itsdangerous",
    "python-multipart",
    "pytest",
    "httpx",
    "mypy",
    "pydantic",
}


def _normalize(name: str) -> str:
    return name.lower().replace("_", "-")


def test_requirements_contains_all_pinned_packages():
    names = set()
    for line in (PROJECT_ROOT / "requirements.txt").read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        m = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)", line)
        if m:
            names.add(_normalize(m.group(1)))
    missing = {p for p in PINNED_REQUIREMENTS if _normalize(p) not in names}
    assert not missing, f"requirements.txt missing pinned packages: {missing}"
