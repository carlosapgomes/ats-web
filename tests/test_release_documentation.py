"""Contract tests for the maintainer release runbook."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
README_PATH = PROJECT_ROOT / "README.md"
RELEASE_GUIDE_PATH = PROJECT_ROOT / "docs" / "releases" / "README.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_readme_links_to_release_guide() -> None:
    """The project index must expose the release runbook to maintainers."""
    readme = _read(README_PATH)
    assert "docs/releases/README.md" in readme


def test_release_guide_documents_prerelease_safety_contract() -> None:
    """Prereleases must be explicit and must not promote stable aliases."""
    guide = _read(RELEASE_GUIDE_PATH)
    assert "gh release create" in guide
    assert "--prerelease" in guide
    assert "--latest=false" in guide
    assert "--verify-tag" in guide
    assert "v0.2.0-rc.1" in guide
    assert "0.2.0-rc.1" in guide
    assert "não atualiza `latest`" in guide.lower()
    assert "não atualiza `0.2`" in guide.lower()


def test_release_guide_documents_stable_release_contract() -> None:
    """Stable releases must describe all tags published by the workflow."""
    guide = _read(RELEASE_GUIDE_PATH)
    for expected_tag in ("v0.2.0", "0.2.0", "0.2", "latest"):
        assert expected_tag in guide
    assert "--latest" in guide
    assert "gh run watch" in guide
    assert "ghcr.io/carlosapgomes/ats-web" in guide


def test_release_guide_requires_validation_and_immutable_versions() -> None:
    """The runbook must prevent releases from unvalidated or retagged code."""
    guide = _read(RELEASE_GUIDE_PATH)
    assert "uv run ruff check ." in guide
    assert "uv run ruff format --check ." in guide
    assert "uv run mypy ." in guide
    assert "uv run pytest" in guide
    assert "não reutilize" in guide.lower()
    assert "release.published" in guide
