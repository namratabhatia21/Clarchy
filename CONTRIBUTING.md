# Contributing to Clarchy

## Set up

```bash
git clone https://github.com/namratabhatia21/Clarchy && cd Clarchy
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
make check        # ruff and pytest, as CI runs them
```

## Branches

`main` is what clarchy.com runs, so it always builds and passes CI. Nothing is pushed to
it directly: every change goes on a short-lived branch and comes back through a pull
request.

- Name the branch after its one topic, with a prefix for the kind of change:
  `feat/` (something new), `fix/` (a bug, an accessibility or legal fix), `docs/`,
  `ci/` (workflows and releases), `chore/` (upkeep), `refactor/`.
  For example `feat/mistral-preset` or `fix/azure-subnet-label`.
- Keep it to one topic. Unrelated fixes found on the way get their own branch.
- Branch from an up-to-date `main`, and merge `main` into the branch (or rebase it, while
  nobody else uses it) when it falls behind.
- Delete the branch once it is merged.
- Never name a branch like a version tag (`v0.1.0`): versions are tags.

## Commits

Small commits that each do one thing and leave the tests passing. The subject line says
what the change does, in the imperative and under about 70 characters ("Fix the Azure
subnet label"); the body says why, and what was checked.

## Pull requests

Open the pull request against `main` when the branch is ready. CI (ruff and pytest on
Python 3.11 and 3.12) must pass before it merges. Say in the description what changed,
why, and how you checked it; for anything people see, include a screenshot. Merge with a
merge commit or a rebase, so the small commits stay readable in the history.

## Releases

Versions follow [Semantic Versioning](https://semver.org/). To release:

1. On a branch `release/vX.Y.Z`, set `version` in `pyproject.toml` and move the notes
   into a `## [X.Y.Z] - YYYY-MM-DD` section of `CHANGELOG.md`. Merge it.
2. Tag the merge on `main` and push the tag:
   `git tag -a vX.Y.Z -m "Clarchy X.Y.Z" && git push origin vX.Y.Z`. Or, on GitHub,
   *Releases → Draft a new release*, create the tag `vX.Y.Z` on `main` and publish.
3. The `Release` workflow checks the tag against `pyproject.toml`, runs the checks,
   builds the wheel, the source package and a zip of the site, and publishes the GitHub
   release with the notes from `CHANGELOG.md` (or adds the files and notes to the release
   made on GitHub).
