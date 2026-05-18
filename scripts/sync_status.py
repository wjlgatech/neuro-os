#!/usr/bin/env python3
"""
scripts/sync_status.py — regenerate docs/STATUS.md from plan stamps.

Modes:
  --write   (default) regenerate docs/STATUS.md and write to disk.
  --check   exit 1 if the regenerated content differs from on-disk file.
            Used by the pre-commit hook to fail commits that would land
            a stale STATUS.md.
  --print   regenerate and print to stdout without writing. Useful for
            `neuro-os status --sync`.

The pipeline is in `agent.status`; this script is the CLI thin wrapper.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure project root on PYTHONPATH so `agent.status` resolves when this
# script is invoked from anywhere.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from agent.status import (  # noqa: E402  (after sys.path mutation)
    build_status_markdown,
    get_recent_ships,
    walk_stamped_plans,
)
from agent.status.render import DEFAULT_CONFIG  # noqa: E402


def regenerate(*, repo_root: Path, quiet: bool = False) -> str:
    """Build the STATUS.md text. Does not write to disk."""
    docs_root = repo_root / "docs"
    plans = walk_stamped_plans(docs_root, quiet=quiet)
    recent = get_recent_ships(cwd=repo_root, limit=3)
    return build_status_markdown(
        plans=plans,
        recent=recent,
        config=DEFAULT_CONFIG,
        docs_root=docs_root,
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Regenerate docs/STATUS.md from frontmatter stamps."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--write", action="store_true", default=True,
        help="(default) write the regenerated content to docs/STATUS.md",
    )
    mode.add_argument(
        "--check", action="store_true",
        help="exit 1 if the regenerated content differs from on-disk; "
             "used by the pre-commit hook",
    )
    mode.add_argument(
        "--print", action="store_true", dest="print_only",
        help="print the regenerated content to stdout, do not write",
    )
    parser.add_argument(
        "--repo-root", default=None,
        help="path to the repo root (default: parent of this script)",
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="suppress 'no frontmatter' warnings for unstamped files",
    )
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).expanduser() if args.repo_root else _REPO_ROOT
    new_content = regenerate(repo_root=repo_root, quiet=args.quiet)
    status_path = repo_root / "docs" / "STATUS.md"

    if args.print_only:
        sys.stdout.write(new_content)
        return 0

    if args.check:
        if not status_path.exists():
            print(
                f"sync_status: STATUS.md missing at {status_path}; "
                "run with --write to create it.",
                file=sys.stderr,
            )
            return 1
        current = status_path.read_text(encoding="utf-8")
        if current != new_content:
            print(
                "sync_status: docs/STATUS.md is stale. Run "
                "`python scripts/sync_status.py --write` and re-commit.",
                file=sys.stderr,
            )
            return 1
        return 0

    # default: --write
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(new_content, encoding="utf-8")
    print(f"sync_status: wrote {status_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
