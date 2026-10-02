"""Publish the static site to a Hugging Face Space (sdk: static).

    clarchy export-site -o space --single-file
    HF_TOKEN=hf_... python scripts/hf_space.py space --repo bhatianamrata/clarchy

The Space is a mirror of clarchy.com. The script writes the Space's card (README.md: its
title, SDK, licence and description), creates the Space if it doesn't exist yet, and makes
the Space's files match the folder in one commit: every file is uploaded (the Hub keeps one
copy of unchanged binaries) and files the build no longer has are deleted. The Space
workflow (.github/workflows/space.yml) runs it.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

SOURCE = "https://github.com/namratabhatia21/Clarchy"
SPACE = "bhatianamrata/clarchy"
# Files of the Space's own that the build doesn't make.
KEEP = {".gitattributes"}


def card(commit: str | None = None) -> str:
    """The Space's README.md: its configuration block, then what the Space is."""
    built = f", commit {commit[:7]}" if commit else ""
    return f"""---
title: Clarchy
emoji: 📐
colorFrom: blue
colorTo: indigo
sdk: static
app_file: index.html
pinned: false
license: apache-2.0
short_description: Cloud architecture from a requirements brief
---

# Clarchy

Clarchy turns a requirements brief into a cloud architecture you can question, price and
compare across AWS, Azure, Google Cloud and open source.

This Space mirrors [clarchy.com](https://clarchy.com), built from
[the source on GitHub]({SOURCE}){built}. It runs in your browser with Pyodide. The samples
replay a recorded run of the rule-based planner. A brief you type or upload is planned live
in your browser, by the rule-based planner or by an open-source model on Hugging Face with
your own token, which goes from your browser straight to the model provider.
"""


def changes(folder: Path, remote: list[str]) -> tuple[list[str], list[str]]:
    """(files to upload, files to delete) to make the Space match the folder."""
    local = sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file())
    stale = sorted(set(remote) - set(local) - KEEP)
    return local, stale


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python scripts/hf_space.py", description=__doc__)
    parser.add_argument("folder", type=Path, help="output of clarchy export-site --single-file")
    parser.add_argument("--repo", default=os.environ.get("HF_SPACE") or SPACE)
    parser.add_argument("--commit", default=os.environ.get("GITHUB_SHA"))
    args = parser.parse_args(argv)
    token = os.environ.get("HF_TOKEN")
    if not token:
        parser.error("set HF_TOKEN to a Hugging Face token that may write to the Space")
    if not (args.folder / "index.html").is_file():
        parser.error(f"{args.folder} has no index.html; build it with export-site --single-file")

    from huggingface_hub import CommitOperationAdd, CommitOperationDelete, HfApi

    (args.folder / "README.md").write_text(card(args.commit), encoding="utf-8")
    api = HfApi(token=token)
    if not api.repo_exists(args.repo, repo_type="space"):
        api.create_repo(args.repo, repo_type="space", space_sdk="static")
    upload, delete = changes(args.folder, api.list_repo_files(args.repo, repo_type="space"))
    operations = [
        CommitOperationAdd(path_in_repo=f, path_or_fileobj=args.folder / f) for f in upload
    ]
    operations += [CommitOperationDelete(path_in_repo=f) for f in delete]
    source = f"{SOURCE}/commit/{args.commit}" if args.commit else SOURCE
    api.create_commit(
        args.repo,
        operations,
        commit_message=f"Publish clarchy.com from {source}",
        repo_type="space",
    )
    print(f"published {len(upload)} files to the Space {args.repo}; deleted {len(delete)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
