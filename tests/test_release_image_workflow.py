"""Contract tests for .github/workflows/release-image.yml.

These tests verify the static YAML content of the GitHub Actions workflow
that publishes a Docker image to GHCR when a GitHub Release is published.
They use only stdlib (pathlib, re) and do NOT add PyYAML, actionlint or any
new project dependency. They do NOT access the network, GitHub API or Docker.
"""

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_PATH = PROJECT_ROOT / ".github" / "workflows" / "release-image.yml"
WORKFLOW_RELPATH = ".github/workflows/release-image.yml"


def _read_workflow() -> str:
    """Return the full text of the workflow file.

    Raises FileNotFoundError if the file does not exist yet.
    """
    return WORKFLOW_PATH.read_text(encoding="utf-8")


# ── R1: File exists + trigger ────────────────────────────────────────────────


def test_release_image_workflow_exists() -> None:
    """The workflow file must exist at the canonical path."""
    assert WORKFLOW_PATH.is_file(), (
        f"Workflow file not found at {WORKFLOW_RELPATH}. Create {WORKFLOW_RELPATH} with release.published trigger."
    )


def test_workflow_triggers_only_for_published_release() -> None:
    """Trigger must be ONLY release.published, no push/workflow_dispatch."""
    content = _read_workflow()
    # Must declare on: and release: types: [published]
    assert re.search(r"^\s*on:\s*$", content, re.MULTILINE), "Workflow must start with 'on:' top-level trigger."
    assert re.search(r"^\s+release:\s*$", content, re.MULTILINE), "Workflow must declare 'release:' event under 'on:'."
    assert "types: [published]" in content, "Trigger must be 'types: [published]' only."
    # Forbid other top-level trigger keywords
    for forbidden in ("push:", "workflow_dispatch:", "pull_request:", "schedule:"):
        # Match at top-indentation level (e.g. spaces then keyword)
        if re.search(rf"^\s*{forbidden}\s*$", content, re.MULTILINE):
            raise AssertionError(
                f"Forbidden top-level trigger '{forbidden}' found in workflow. Only release.published is allowed."
            )


# ── R2: Concurrency and minimal permissions ──────────────────────────────────


def test_workflow_uses_minimum_package_permissions() -> None:
    """Permissions must be contents: read and packages: write, nothing more."""
    content = _read_workflow()
    assert "contents: read" in content, "Permission 'contents: read' is required."
    assert "packages: write" in content, "Permission 'packages: write' is required."
    # Check concurrency group exists
    assert "concurrency:" in content, "Workflow must declare concurrency group."
    assert "cancel-in-progress: false" in content, "Concurrency must not cancel in-progress runs."
    # Forbid write-all or excessive permissions
    assert "write-all" not in content, "Permission 'write-all' is forbidden."
    assert "contents: write" not in content, "Permission 'contents: write' is forbidden (only read is allowed)."


# ── R3: Registry and authentication ──────────────────────────────────────────


def test_workflow_logs_in_to_ghcr_with_github_token() -> None:
    """Login must use ghcr.io, github.actor and GITHUB_TOKEN only."""
    content = _read_workflow()
    assert "docker/login-action@v3" in content, "Must use docker/login-action@v3."
    assert "ghcr.io" in content, "Registry must be ghcr.io."
    assert "github.actor" in content, "Login username must use ${{ github.actor }}."
    assert "secrets.GITHUB_TOKEN" in content, "Login password must use ${{ secrets.GITHUB_TOKEN }}."
    # No custom PAT or secret
    assert "GHCR_TOKEN" not in content, "Custom GHCR_TOKEN secret is forbidden; use GITHUB_TOKEN."
    # Env vars for registry and image name
    assert "REGISTRY:" in content, "Workflow must declare env.REGISTRY."
    assert "IMAGE_NAME:" in content or "github.repository" in content, (
        "Workflow must declare env.IMAGE_NAME with github.repository."
    )


# ── R4: Metadata and stable/prerelease tags ─────────────────────────────────


def test_workflow_tags_stable_and_prerelease_channels_safely() -> None:
    """Stable releases must get exact tag, SemVer, minor and latest.
    Prereleases must NOT update minor alias or latest.
    """
    content = _read_workflow()
    # Must use docker/metadata-action
    assert "docker/metadata-action@v5" in content, "Must use docker/metadata-action@v5."
    # Exact tag
    assert "tag_name" in content, "Must include the exact release tag name."
    # SemVer normalized version
    assert "{{version}}" in content, "Must publish SemVer normalized tag ({{version}})."
    # Minor alias with prerelease guard
    assert "{{major}}.{{minor}}" in content, "Must publish major.minor alias for stable releases."
    assert "prerelease == false" in content, "Minor alias must be disabled for prereleases (prerelease == false)."
    # Latest with prerelease guard
    assert "value=latest" in content, "Must define 'latest' tag."
    prerelease_conditions = [
        line for line in content.splitlines() if "prerelease == false" in line and "latest" in line
    ]
    assert prerelease_conditions, "'latest' must be guarded by prerelease == false condition."
    # flavor latest=false
    assert "latest=false" in content, "'flavor: latest=false' must be set to avoid implicit latest."
    # No major-only alias
    major_only = re.findall(r"pattern=\{\{major\}\}(?!\.\{\{minor\}\})", content)
    assert not major_only, "Major-only alias ({{major}} without .{{minor}}) is forbidden."


# ── R5: Build and push configuration ────────────────────────────────────────


def test_workflow_builds_and_pushes_root_dockerfile_for_amd64_with_cache() -> None:
    """Build must use root Dockerfile, push/pull true, linux/amd64 and GHA cache."""
    content = _read_workflow()
    assert "docker/build-push-action@v6" in content, "Must use docker/build-push-action@v6."
    assert "context: ." in content, "Build context must be '.' (project root)."
    assert "file: ./Dockerfile" in content, "Dockerfile must be './Dockerfile'."
    assert "push: true" in content, "Push must be enabled (push: true)."
    assert "pull: true" in content, "Pull must be enabled (pull: true) to refresh base images."
    assert "linux/amd64" in content, "Platform must be linux/amd64."
    # Tags and labels from metadata
    assert "steps.metadata.outputs.tags" in content, "Tags must come from steps.metadata.outputs.tags."
    assert "steps.metadata.outputs.labels" in content, "Labels must come from steps.metadata.outputs.labels."
    # GHA cache
    assert "cache-from: type=gha" in content, "Cache read must use type=gha."
    assert "cache-to: type=gha" in content, "Cache write must use type=gha."


# ── R6: Action major versions ────────────────────────────────────────────────


def test_workflow_uses_expected_action_major_versions() -> None:
    """All used actions must be at the expected major version."""
    content = _read_workflow()
    action_checks = {
        "actions/checkout@v4": "actions/checkout@v4 is required.",
        "docker/setup-buildx-action@v3": "docker/setup-buildx-action@v3 is required.",
        "docker/login-action@v3": "docker/login-action@v3 is required.",
        "docker/metadata-action@v5": "docker/metadata-action@v5 is required.",
        "docker/build-push-action@v6": "docker/build-push-action@v6 is required.",
    }
    for action_ref, msg in action_checks.items():
        assert action_ref in content, msg
