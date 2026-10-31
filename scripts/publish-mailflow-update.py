#!/usr/bin/env python3
"""Intentional MailFlow update publish helper (development machine).

Does NOT auto-commit every dirty file. You must either:
  - already have commits ready to push, and pass --tag-only, or
  - pass --paths with an explicit file list to stage/commit.

Never force-pushes. Never includes .env, storage, secrets, or runtime files.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_PATH_PARTS = (
    ".env",
    ".venv",
    "node_modules",
    ".mailflow",
    "launcher/.runtime",
    "storage/",
    "backend/storage/",
    "credentials",
    "secret",
    ".pem",
    "id_rsa",
)


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    print("+", " ".join(cmd))
    return subprocess.run(cmd, cwd=ROOT, check=check, text=True, capture_output=True)


def assert_allowed_path(rel: str) -> None:
    normalized = rel.replace("\\", "/").lstrip("./")
    lower = normalized.lower()
    for part in FORBIDDEN_PATH_PARTS:
        if part in lower or lower.endswith(part.strip("/")):
            raise SystemExit(f"Refusing to publish path that looks sensitive/runtime: {rel}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish a MailFlow client update to GitHub")
    parser.add_argument(
        "--paths",
        nargs="*",
        default=[],
        help="Explicit paths to git add/commit (required unless --tag-only)",
    )
    parser.add_argument("--message", required=True, help="Commit and/or tag message")
    parser.add_argument(
        "--tag-only",
        action="store_true",
        help="Do not create a commit; only tag HEAD and push tag + current branch",
    )
    parser.add_argument(
        "--ref",
        default="main",
        help="Branch clients should track (also written into docs reminder). Default: main",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip backend/frontend validation (not recommended)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print actions without committing/pushing",
    )
    args = parser.parse_args()

    if not args.tag_only and not args.paths:
        print("Pass --paths FILE… or use --tag-only for an already-committed tip.", file=sys.stderr)
        return 2

    for p in args.paths:
        assert_allowed_path(p)
        if not (ROOT / p).exists():
            raise SystemExit(f"Path not found: {p}")

    if not args.skip_tests:
        print("Running backend tests…")
        r = run(
            ["backend/.venv/bin/pytest", "-q", "--tb=line"],
            check=False,
        ) if (ROOT / "backend/.venv/bin/pytest").exists() else run(
            [sys.executable, "-m", "pytest", "backend", "-q", "--tb=line"],
            check=False,
        )
        if r.returncode != 0:
            print(r.stdout)
            print(r.stderr, file=sys.stderr)
            raise SystemExit("Backend tests failed; publish aborted.")
        print("Running frontend tests + build…")
        for cmd in (["npm", "test"], ["npm", "run", "build"]):
            print("+", " ".join(cmd), "(frontend)")
            r = subprocess.run(cmd, cwd=ROOT / "frontend", check=False, text=True, capture_output=True)
            if r.returncode != 0:
                print(r.stdout)
                print(r.stderr, file=sys.stderr)
                raise SystemExit(f"Frontend step failed: {' '.join(cmd)}")
        print("Validation OK.")

    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    tag = f"mailflow-{stamp}"
    if not re.fullmatch(r"mailflow-\d{8}-\d{6}", tag):
        raise SystemExit("Internal tag format error")

    if args.dry_run:
        print(f"DRY RUN would tag {tag} and push to origin/{args.ref}")
        if not args.tag_only:
            print("Would commit paths:", ", ".join(args.paths))
        return 0

    if not args.tag_only:
        run(["git", "add", "--", *args.paths])
        # Ensure nothing forbidden staged
        staged = run(["git", "diff", "--cached", "--name-only"]).stdout.splitlines()
        for s in staged:
            assert_allowed_path(s)
        commit = subprocess.run(
            ["git", "commit", "-m", args.message],
            cwd=ROOT,
            check=False,
        )
        if commit.returncode != 0:
            raise SystemExit("Commit failed (nothing staged or hook failure).")

    run(["git", "tag", "-a", tag, "-m", args.message])
    # Normal push only — never --force
    branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()
    push_branch = subprocess.run(["git", "push", "-u", "origin", "HEAD"], cwd=ROOT, check=False)
    if push_branch.returncode != 0:
        print("Branch push failed. Tag was created locally:", tag, file=sys.stderr)
        return push_branch.returncode
    push_tag = subprocess.run(["git", "push", "origin", tag], cwd=ROOT, check=False)
    if push_tag.returncode != 0:
        print("Tag push failed:", tag, file=sys.stderr)
        return push_tag.returncode

    head = run(["git", "rev-parse", "HEAD"]).stdout.strip()
    print()
    print("Published update.")
    print(f"  Branch tip: {branch} @ {head[:7]}")
    print(f"  Tag:        {tag}")
    print()
    print("Clients:")
    print("  1. Open the local launcher")
    print("  2. Optional: set .mailflow/update-config.json release_ref to the tag or 'main'")
    print("  3. Click Check for updates → Update now")
    print()
    print("Default client ref is 'main'. To pin clients to this tag, set release_ref to:")
    print(f"  {tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
