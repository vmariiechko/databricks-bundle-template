# Releasing

This is the canonical checklist for cutting a release of `databricks-bundle-template`. It exists so the steps are the same every time and nothing is rediscovered from memory. If you are an AI assistant helping with a release, follow this document exactly.

The guiding rule: **`main` is always release-ready the moment a PR merges.** The version bump and the changelog finalization happen inside the PR, before merge, so the commit that gets tagged is exactly what was reviewed.

## Versioning

This project follows [Semantic Versioning](https://semver.org/): `MAJOR.MINOR.PATCH`.

- **MINOR** (`1.8.0` to `1.9.0`): a new asset, a new template feature, or a new configuration axis. This is the common case.
- **PATCH** (`1.7.0` to `1.7.1`): a fix or a small refinement to an existing asset or feature, no new capability.
- **MAJOR**: a breaking change to the generated output or the install contract. Rare; discuss first.

### The two version markers

The version lives in two places and they must always agree:

1. `pyproject.toml`: the `version = "X.Y.Z"` field.
2. `template/{{.project_name}}/bundle_init_config.json.tmpl`: the `"_template_version": "X.Y.Z"` field, which stamps provenance into every generated bundle.

A guard test (`tests/test_release_metadata.py`) asserts these two markers and the most recent finalized `CHANGELOG.md` version all match, and it runs in CI on every PR. If you bump one and forget the other, or finalize the changelog without bumping the markers, the test fails before merge.

## Phase 1: in the PR (before merge)

Do all of this on the feature branch, in the PR that ships the change. By the time the PR merges, `main` is release-ready.

1. **Implement and test.** Make the change, add or update tests, and confirm the full suite is green:

   ```bash
   pytest tests/ -V
   ```

2. **Finalize the changelog.** In `CHANGELOG.md`, rename the `## [Unreleased]` heading to the new version with today's date, then add a fresh empty `## [Unreleased]` above it:

   ```markdown
   ## [Unreleased]

   ## [X.Y.Z] - YYYY-MM-DD

   ### Added
   - ...
   ```

   Use the real release date (the day you cut the release), not the day you started the work.

3. **Bump both version markers** to `X.Y.Z`: `pyproject.toml` and `template/{{.project_name}}/bundle_init_config.json.tmpl` (see "The two version markers" above).

4. **Update the catalog and roadmap as applicable.** `ASSETS.md` (new or changed asset row), `ROADMAP.md` (move the item to "Shipped" or update its status).

5. **Open the PR.** Fill out the PR template, including the optional release block confirming steps 2 and 3 are done. Run the suite once more so the version guard test passes in CI.

6. **Merge** once review and CI are green.

## Phase 2: tag and release (after merge)

Do this on a synced `main`.

1. **Sync and verify.**

   ```bash
   git checkout main && git pull
   ```

   Confirm `pyproject.toml`, `_template_version`, and the top `CHANGELOG.md` entry all read `X.Y.Z` and the changelog date is correct. (The guard test already enforces this, but eyeball it.)

2. **Create the annotated tag** on the merge commit. The tag name is `vX.Y.Z` and the message follows the established format `vX.Y.Z - <asset-or-area>: <Short Title>`:

   ```bash
   git tag -a vX.Y.Z -m "vX.Y.Z - <asset-or-area>: <Short Title>"
   git push origin vX.Y.Z
   ```

   Use an annotated tag (`-a`), not a lightweight tag; every prior release tag is annotated.

3. **Create the GitHub release** from the tag, with a notes file written from the template in the appendix below:

   ```bash
   gh release create vX.Y.Z --verify-tag \
     --title "vX.Y.Z - <asset-or-area>: <Short Title>" \
     --notes-file <path-to-filled-notes>
   ```

   Not a draft, not a prerelease. Pin every link in the notes to the `vX.Y.Z` ref so they keep working as the repo evolves.

4. **Verify.**

   ```bash
   gh release view vX.Y.Z
   ```

### If the change already merged without finalizing

If a PR merged with entries still under `## [Unreleased]` and the version markers not bumped, do not tag yet. Open a small dedicated "Release vX.Y.Z" PR that does Phase 1 steps 2 and 3 (finalize the changelog, bump both markers), merge it, then run Phase 2. Keep the tag pointing at a commit where the markers and changelog already read `X.Y.Z`.

## Release notes template

Fill this in for the `gh release create --notes-file`. It mirrors the structure of the v1.7.0 and v1.8.0 releases. Drop any section that does not apply (for a patch release, "Highlights" and "What's new" may collapse into one short section).

```markdown
## Highlights

<!-- One or two paragraphs: what this release is and why it matters. Lead with the headline change. -->

## What's new

### <Asset or feature name>

<!-- The install command (for an asset), the prompts, what ships, the key behavior. -->

### Documentation and metadata

<!-- Catalog/roadmap updates, version bump note, any doc changes. -->

## Upgrade

<!-- What existing users need to do. Usually "No action required for existing installs." plus the install command for a new asset. -->

## Breaking changes

<!-- "None." in the common case. -->

## Pointers

- [Full changelog](https://github.com/vmariiechko/databricks-bundle-template/blob/vX.Y.Z/CHANGELOG.md#xyz---yyyy-mm-dd)
- [Asset README](https://github.com/vmariiechko/databricks-bundle-template/blob/vX.Y.Z/assets/<name>/README.md)
- [Asset catalog](https://github.com/vmariiechko/databricks-bundle-template/blob/vX.Y.Z/ASSETS.md)
```

## See also

- [CONTRIBUTING.md](CONTRIBUTING.md): how to make changes and the asset framework rules.
- [CHANGELOG.md](CHANGELOG.md): the running history this release pipeline finalizes.
