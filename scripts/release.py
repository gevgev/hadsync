#!/usr/bin/env python3
"""Release helper — bumps versions, updates changelogs, commits, tags, and pushes.

Usage:
    python scripts/release.py 0.2.9
"""
from __future__ import annotations

import re
import subprocess
import sys
from datetime import date
from pathlib import Path

REPO = "gevgev/hadsync"
ROOT = Path(__file__).parent.parent


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python scripts/release.py <version>  (e.g. 0.2.9)")
        sys.exit(1)

    version = sys.argv[1].lstrip("v")
    tag = f"v{version}"
    today = date.today().isoformat()

    print(f"Releasing {tag} on {today}...")

    _check_preconditions()

    _bump_pyproject(version)
    _bump_npm(version)
    _update_changelog(ROOT / "CHANGELOG.md", tag, tag, today)
    _update_changelog(ROOT / "vscode-hadsync" / "CHANGELOG.md", version, tag, today)
    _commit_and_tag(tag)

    print(f"\n✓  {tag} pushed — release workflow will start shortly.")
    print(f"   https://github.com/{REPO}/actions/workflows/release.yml")
    print(f"\nRemember to assign any open issues/PRs for this batch to the next milestone.")


# ---------------------------------------------------------------------------

def _check_preconditions() -> None:
    result = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True, cwd=ROOT
    )
    dirty = [
        l for l in result.stdout.splitlines()
        if not l.startswith("??")  # ignore untracked files
        and not any(f in l for f in [
            "CHANGELOG.md",
            "pyproject.toml",
            "package.json",
            "package-lock.json",
        ])
    ]
    if dirty:
        print("Working tree has unexpected changes — commit or stash them first:")
        for line in dirty:
            print(f"  {line}")
        sys.exit(1)

    cl = (ROOT / "CHANGELOG.md").read_text()
    if "## [Unreleased]" not in cl:
        print("No [Unreleased] section found in CHANGELOG.md — nothing to release.")
        sys.exit(1)

    unreleased_content = cl.split("## [Unreleased]")[1].split("---")[0].strip()
    if not unreleased_content:
        print("The [Unreleased] section in CHANGELOG.md is empty — add entries before releasing.")
        sys.exit(1)


def _bump_pyproject(version: str) -> None:
    path = ROOT / "pyproject.toml"
    text = re.sub(r'^version = ".*"', f'version = "{version}"', path.read_text(), flags=re.MULTILINE)
    path.write_text(text)
    print(f"  bumped pyproject.toml → {version}")


def _bump_npm(version: str) -> None:
    subprocess.run(
        ["npm", "version", version, "--no-git-tag-version"],
        cwd=ROOT / "vscode-hadsync",
        check=True,
        capture_output=True,
    )
    print(f"  bumped vscode-hadsync/package.json + package-lock.json → {version}")


def _update_changelog(path: Path, heading_version: str, tag: str, today: str) -> None:
    text = path.read_text()

    # Rename [Unreleased] → versioned heading
    new_heading = f"## [{heading_version}] — {today}"
    text = text.replace("## [Unreleased]", new_heading, 1)

    # Insert release link before the first --- separator
    link = f"[{heading_version}]: https://github.com/{REPO}/releases/tag/{tag}"
    text = text.replace("\n---\n", f"\n{link}\n\n---\n", 1)

    # Re-add a fresh [Unreleased] section at the top for the next batch
    text = text.replace(
        "# Changelog\n\n",
        "# Changelog\n\n## [Unreleased]\n\n---\n\n",
        1,
    )

    path.write_text(text)
    print(f"  updated {path.relative_to(ROOT)}")


def _commit_and_tag(tag: str) -> None:
    files = [
        "pyproject.toml",
        "CHANGELOG.md",
        "vscode-hadsync/CHANGELOG.md",
        "vscode-hadsync/package.json",
        "vscode-hadsync/package-lock.json",
    ]
    subprocess.run(["git", "add", *files], cwd=ROOT, check=True)
    subprocess.run(
        ["git", "commit", "-m", f"chore: release {tag}"],
        cwd=ROOT, check=True,
    )
    subprocess.run(["git", "tag", tag], cwd=ROOT, check=True)
    subprocess.run(["git", "push"], cwd=ROOT, check=True)
    subprocess.run(["git", "push", "--tags"], cwd=ROOT, check=True)
    print(f"  committed, tagged {tag}, pushed")


if __name__ == "__main__":
    main()
