#!/usr/bin/env python3
"""Compute and apply the release version bump across all pyproject.toml files.

Treats the latest git tag as the source of truth for the previous version and
reports drift if the root pyproject disagrees. Prints a before/after table.

Usage:
  bump_versions.py (major|minor|patch|X.Y.Z)          # dry run (default)
  bump_versions.py (major|minor|patch|X.Y.Z) --apply  # rewrite the files
"""
import argparse
import glob
import re
import subprocess
import sys

VER_RE = re.compile(r'^(version\s*=\s*")([^"]+)(")', re.M)


def latest_tag():
    return subprocess.run(["git", "describe", "--tags", "--abbrev=0"],
                          text=True, capture_output=True, check=True).stdout.strip()


def read_version(path):
    with open(path) as f:
        m = VER_RE.search(f.read())
    return m.group(2) if m else None


def bump(prev, kind):
    if re.fullmatch(r"\d+\.\d+\.\d+", kind):
        return kind
    if not re.fullmatch(r"\d+\.\d+\.\d+", prev):
        sys.exit(f"ERROR: previous version {prev!r} is not semver X.Y.Z; "
                 f"cannot apply a {kind!r} bump. Pass an explicit X.Y.Z instead.")
    major, minor, patch = (int(x) for x in prev.split("."))
    if kind == "major":
        return f"{major + 1}.0.0"
    if kind == "minor":
        return f"{major}.{minor + 1}.0"
    if kind == "patch":
        return f"{major}.{minor}.{patch + 1}"
    sys.exit(f"ERROR: bad bump kind {kind!r}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kind")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    tag = latest_tag()
    prev = tag.removeprefix("v")
    root_ver = read_version("pyproject.toml")
    if root_ver != prev:
        print(f"DRIFT: root pyproject is {root_ver!r} but latest tag is {tag!r}; "
              f"using the tag ({prev}) as previous version.", file=sys.stderr)

    new = bump(prev, a.kind)
    files = ["pyproject.toml"] + sorted(glob.glob("packages/*/pyproject.toml"))

    print(f"{'file':<45} {'before':>10} -> {'after'}")
    for path in files:
        print(f"{path:<45} {str(read_version(path)):>10} -> {new}")
        if a.apply:
            with open(path) as f:
                text = f.read()
            text, n = VER_RE.subn(rf'\g<1>{new}\g<3>', text, count=1)
            if n != 1:
                sys.exit(f"ERROR: no version line in {path}")
            with open(path, "w") as f:
                f.write(text)

    print(f"\nNEW_VERSION={new}\nPREV_TAG={tag}")
    if not a.apply:
        print("(dry run -- re-run with --apply to write)")


if __name__ == "__main__":
    main()
