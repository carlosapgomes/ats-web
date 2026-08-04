# release-container-publication Spec Delta

## ADDED Requirements

### Requirement: Published GitHub Releases shall produce a GHCR image

The repository SHALL provide a GitHub Actions workflow that builds the root `Dockerfile` and publishes an OCI image to `ghcr.io/${{ github.repository }}` when a GitHub Release is published.

#### Scenario: Stable release is published

- **GIVEN** a maintainer publishes a stable GitHub Release tagged `v1.2.3`
- **WHEN** the release workflow runs successfully
- **THEN** it builds the release ref using the root `Dockerfile`
- **AND** it publishes the image to `ghcr.io/${{ github.repository }}`
- **AND** it publishes tags `v1.2.3`, `1.2.3`, `1.2` and `latest`

#### Scenario: Draft release exists but is not published

- **GIVEN** a GitHub Release remains a draft
- **WHEN** no `release.published` event occurs
- **THEN** the image publication workflow does not run for that draft

#### Scenario: A tag is pushed without publishing a GitHub Release

- **GIVEN** a SemVer Git tag is pushed
- **WHEN** no GitHub Release is published
- **THEN** the image publication workflow does not run solely because of the tag push

### Requirement: Prereleases shall not move stable aliases

A published prerelease SHALL be publishable under prerelease-specific tags without updating aliases that represent the stable channel.

#### Scenario: Prerelease is published

- **GIVEN** a maintainer publishes a prerelease tagged `v1.3.0-rc.1`
- **WHEN** the release workflow generates image metadata
- **THEN** it includes the exact tag `v1.3.0-rc.1`
- **AND** it may include the normalized prerelease tag `1.3.0-rc.1`
- **AND** it does not publish or update `latest`
- **AND** it does not publish or update the stable minor alias `1.3`

### Requirement: GHCR publication shall use repository-scoped credentials

The release workflow SHALL authenticate to GHCR with the event actor and the repository-provided `GITHUB_TOKEN`, using only the permissions required to read source content and write packages.

#### Scenario: Workflow authenticates to GHCR

- **GIVEN** the release workflow is running in the repository
- **WHEN** it logs in to `ghcr.io`
- **THEN** the username is `${{ github.actor }}`
- **AND** the password is `${{ secrets.GITHUB_TOKEN }}`
- **AND** workflow permissions include `contents: read`
- **AND** workflow permissions include `packages: write`
- **AND** no custom PAT is required

### Requirement: Release builds shall be reproducible through the repository Docker contract

The workflow SHALL build the root Docker context for `linux/amd64`, push metadata-generated tags and labels, and use the GitHub Actions build cache without changing the application runtime contract.

#### Scenario: Build and push step executes

- **GIVEN** metadata and GHCR login succeeded
- **WHEN** `docker/build-push-action` runs
- **THEN** its context is `.`
- **AND** its Dockerfile is `./Dockerfile`
- **AND** `push` is enabled
- **AND** its platform is `linux/amd64`
- **AND** tags and labels come from `docker/metadata-action`
- **AND** GHA cache is configured for both read and write

### Requirement: Workflow contracts shall have repository-level regression tests

The repository SHALL contain an automated test that verifies the critical static contracts of the release image workflow without adding a YAML library or external test dependency.

#### Scenario: Critical workflow contract is removed

- **GIVEN** the workflow test exists
- **WHEN** a contributor removes or changes a required trigger, permission, credential, stable-tag guard, destination, push setting, platform or cache contract
- **THEN** the targeted pytest test fails with an actionable assertion

#### Scenario: Workflow contract remains valid

- **GIVEN** `.github/workflows/release-image.yml` satisfies the specified contracts
- **WHEN** `uv run pytest tests/test_release_image_workflow.py -v` runs
- **THEN** all targeted tests pass
