"""Contract tests for production Dockerfile dependency isolation.

Verifies that UV_NO_SYNC=1 is set in the correct position so that
dev dependencies (pytest, mypy, ruff, django-stubs) are never installed
in the production image, while production runtime dependencies work.
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCKERFILE_PATH = PROJECT_ROOT / "Dockerfile"
DOCKERIGNORE_PATH = PROJECT_ROOT / ".dockerignore"


def _read_dockerfile() -> str:
    """Return the full text of the Dockerfile."""
    return DOCKERFILE_PATH.read_text(encoding="utf-8")


def _line_of(content: str, fragment: str) -> int:
    """Return the 0-indexed line number where *fragment* appears."""
    for idx, line in enumerate(content.splitlines()):
        if fragment in line and not line.strip().startswith("#"):
            return idx
    raise ValueError(f"Fragment {fragment!r} not found in Dockerfile")


def test_docker_build_context_excludes_all_environment_files() -> None:
    """Neither .env nor examples/variants may be copied by COPY . ."""
    patterns = {
        line.strip()
        for line in DOCKERIGNORE_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert ".env" in patterns
    assert ".env.*" in patterns


def test_production_sync_excludes_dev_dependencies() -> None:
    """Dockerfile must sync with --frozen, --no-dev and --no-install-project."""
    content = _read_dockerfile()
    assert "uv sync" in content, "Dockerfile must run uv sync."
    assert "--frozen" in content, "uv sync must use --frozen."
    assert "--no-dev" in content, "uv sync must exclude dev dependencies (--no-dev)."
    assert "--no-install-project" in content, "uv sync must use --no-install-project."


def test_uv_no_sync_is_enabled_after_production_sync() -> None:
    """UV_NO_SYNC=1 must appear AFTER the production uv sync line."""
    content = _read_dockerfile()
    sync_line = _line_of(content, "uv sync")
    no_sync_line = _line_of(content, "UV_NO_SYNC=1")
    assert no_sync_line > sync_line, (
        f"ENV UV_NO_SYNC=1 (line {no_sync_line}) must appear "
        f"after RUN uv sync ... (line {sync_line}) to avoid blocking "
        f"the production sync."
    )


def test_uv_no_sync_is_enabled_before_collectstatic() -> None:
    """UV_NO_SYNC=1 must appear BEFORE the collectstatic uv run."""
    content = _read_dockerfile()
    no_sync_line = _line_of(content, "UV_NO_SYNC=1")
    collectstatic_line = _line_of(content, "collectstatic")
    assert no_sync_line < collectstatic_line, (
        f"ENV UV_NO_SYNC=1 (line {no_sync_line}) must appear "
        f"before RUN uv run ... collectstatic (line {collectstatic_line})."
    )


def test_dockerfile_has_no_later_dependency_sync() -> None:
    """No uv sync must appear after the production sync line."""
    content = _read_dockerfile()
    sync_line = _line_of(content, "uv sync")
    lines = content.splitlines()
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        # Only flag actual uv sync commands (not comments)
        if "uv sync" in stripped and idx != sync_line:
            raise AssertionError(
                f"Additional uv sync found at line {idx}: {stripped.strip()!r}. "
                f"Only the single production sync at line {sync_line} is allowed."
            )
    # Also check there's at least one uv sync (it's required)
    assert "uv sync" in content, "Dockerfile must have a uv sync command."
