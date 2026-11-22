# Releasing

Only the owner releases. An agent never tags, publishes or creates a GitHub release.

## What a release is here

A release is a tag on the default branch (`main`) plus a GitHub release with notes. The project is a standard-library Python application run from a checkout. It has no package manifest, no build step and nothing published to a package index, so there are no artifacts to upload.

## Steps

1. Make sure every pull request meant for the release is merged and the latest `main` run of CI is green on Linux and Windows.
2. From a clean checkout of `main`, run the full suite: `python -m unittest discover -s tests -t .` (use `python3` on Linux). It must report `OK` with no test count lower than at the previous release.
3. Move the `Unreleased` entries in `CHANGELOG.md` under a new heading with the version and date, and leave an empty `Unreleased` section. Commit this through a pull request.
4. Check that the README and `docs/PRD.md` describe what the release does, and that no data directory, SQLite file or exported font is tracked.
5. Tag the merge commit (`git tag -a vX.Y.Z -m "vX.Y.Z"`), push the tag, and create the GitHub release with the changelog section as its notes.
6. After the release, read the tag and release page once to confirm they show the intended commit.
