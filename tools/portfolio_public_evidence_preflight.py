from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

EVIDENCE_SENSITIVE_PREFIXES = (
    "README.md",
    "README.zh.md",
    "docs/",
    "frontend2/src/pages/portfolio/",
    "frontend2/src/pages/play/",
    "frontend2/src/pages/replay/",
    "frontend2/src/pages/create/",
    "rpg_backend/narrative/",
    "tests/",
)


@dataclass(frozen=True)
class PublicEvidenceStatus:
    head: str
    remote_ref: str
    remote_head: str
    ahead_count: int
    behind_count: int
    changed_paths: tuple[str, ...]


def _run_git(args: list[str]) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.strip()


def evidence_sensitive_paths(paths: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(
        path
        for path in paths
        if any(path == prefix.rstrip("/") or path.startswith(prefix) for prefix in EVIDENCE_SENSITIVE_PREFIXES)
    )


def collect_status(remote: str, branch: str, *, skip_fetch: bool = False) -> PublicEvidenceStatus:
    remote_ref = f"{remote}/{branch}"
    if not skip_fetch:
        _run_git(["fetch", remote, branch, "--prune"])
    head = _run_git(["rev-parse", "HEAD"])
    remote_head = _run_git(["rev-parse", remote_ref])
    ahead_count = int(_run_git(["rev-list", "--count", f"{remote_ref}..HEAD"]) or "0")
    behind_count = int(_run_git(["rev-list", "--count", f"HEAD..{remote_ref}"]) or "0")
    changed_raw = _run_git(["diff", "--name-only", f"{remote_ref}..HEAD"])
    changed_paths = tuple(path for path in changed_raw.splitlines() if path)
    return PublicEvidenceStatus(
        head=head,
        remote_ref=remote_ref,
        remote_head=remote_head,
        ahead_count=ahead_count,
        behind_count=behind_count,
        changed_paths=changed_paths,
    )


def status_exit_code(status: PublicEvidenceStatus) -> int:
    return 0 if status.ahead_count == 0 and status.behind_count == 0 else 1


def format_status(status: PublicEvidenceStatus) -> str:
    if status_exit_code(status) == 0:
        return (
            "Portfolio public evidence preflight: PASS\n"
            f"Local HEAD matches {status.remote_ref} at {status.head[:7]}.\n"
            "Public GitHub and GitHub Pages reviewers should see the same committed source evidence."
        )

    lines = [
        "Portfolio public evidence preflight: FAIL",
        f"Local HEAD: {status.head[:7]}",
        f"{status.remote_ref}: {status.remote_head[:7]}",
    ]
    if status.ahead_count:
        lines.append(
            f"Local branch is {status.ahead_count} commit(s) ahead of {status.remote_ref}; "
            "public reviewers will not see those local changes until they are pushed and deployed."
        )
    if status.behind_count:
        lines.append(
            f"Local branch is {status.behind_count} commit(s) behind {status.remote_ref}; "
            "refresh or reconcile before using this checkout as application evidence."
        )

    sensitive = evidence_sensitive_paths(status.changed_paths)
    if sensitive:
        lines.append("Evidence-sensitive local changes not yet public:")
        lines.extend(f"- {path}" for path in sensitive[:24])
        if len(sensitive) > 24:
            lines.append(f"- ... {len(sensitive) - 24} more")
    else:
        lines.append("No configured evidence-sensitive paths changed, but commit state is still not public-synced.")
    lines.append("Next: push the intended branch, wait for the public page/docs to update, then rerun this preflight.")
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check whether local Tiny Stories portfolio evidence is published to the public Git remote.",
    )
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--branch", default="main")
    parser.add_argument(
        "--skip-fetch",
        action="store_true",
        help="Use the existing remote-tracking ref without fetching. Useful for offline checks.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    status = collect_status(args.remote, args.branch, skip_fetch=args.skip_fetch)
    print(format_status(status))
    return status_exit_code(status)


if __name__ == "__main__":
    raise SystemExit(main())
