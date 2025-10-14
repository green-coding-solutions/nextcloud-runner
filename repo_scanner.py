#!/usr/bin/env python3
import argparse
import csv
import datetime as dt
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except ImportError:
    print("This script requires Python 3.9+ for zoneinfo.", file=sys.stderr)
    sys.exit(1)

# --- Configuration ---
REPOS = {
    # "text":     {"url": "https://github.com/nextcloud/text.git",     "branch": "stable32"},
    # "calendar": {"url": "https://github.com/nextcloud/calendar.git", "branch": "main"},
    # "contants": {"url": "https://github.com/nextcloud/contacts.git", "branch": "main"},
    # "spreed":   {"url": "https://github.com/nextcloud/spreed.git",   "branch": "stable32"},
    "server":   {"url": "https://github.com/nextcloud/server.git",   "branch": "stable32"},
}
OUTPUT_CSV = "git_heads_last_30_days.csv"
CACHE_DIR = Path("./repos_cache")
TZ = ZoneInfo("Europe/Berlin")
TIMES = [(12, 0), (23, 59)]  # 12:00 and 23:59 local time
DAYS = 30  # last 30 days
# ----------------------


def run(cmd, cwd=None, check=True, capture_output=True, text=True):
    """Run a command; print it; on failure, echo stderr before raising."""
    print(f"+ {' '.join(cmd)}")
    try:
        return subprocess.run(
            cmd,
            cwd=cwd,
            check=check,
            stdout=subprocess.PIPE if capture_output else None,
            stderr=subprocess.PIPE if capture_output else None,
            text=text,
        )
    except subprocess.CalledProcessError as e:
        if e.stderr:
            sys.stderr.write(e.stderr)
        raise


def repo_dir_for(name: str) -> Path:
    return CACHE_DIR / name


def branch_exists_remote(url: str, branch: str) -> bool:
    """Return True if the exact remote branch exists without cloning."""
    try:
        # --exit-code makes ls-remote return 2xx if found, nonzero if not
        run(["git", "ls-remote", "--exit-code", "--heads", url, f"refs/heads/{branch}"])
        return True
    except subprocess.CalledProcessError:
        return False


def remote_default_branch(url_or_dir: str, is_local_repo: bool) -> str:
    """
    Get remote default branch name (e.g., main or master).
    Works on a bare URL (faster) or an existing repo dir.
    """
    if is_local_repo:
        res = run(["git", "ls-remote", "--symref", "origin", "HEAD"], cwd=url_or_dir)
    else:
        res = run(["git", "ls-remote", "--symref", url_or_dir, "HEAD"])
    for line in res.stdout.splitlines():
        if line.startswith("ref: "):
            ref = line.split()[1]
            if ref.startswith("refs/heads/"):
                return ref.split("/", 2)[-1]
    # Fallbacks
    for cand in ("main", "master"):
        try:
            if is_local_repo:
                run(["git", "ls-remote", "origin", f"refs/heads/{cand}"], cwd=url_or_dir)
            else:
                run(["git", "ls-remote", url_or_dir, f"refs/heads/{cand}"])
            return cand
        except subprocess.CalledProcessError:
            continue
    raise RuntimeError("Could not determine remote default branch")


def ensure_repo_local(
    name: str,
    url: str,
    requested_branch: Optional[str],
    shallow_since: Optional[str],
    strict_branches: bool,
) -> Tuple[Path, str]:
    """
    Ensure repo exists locally and only the desired branch is fetched.
    Returns (repo_dir, actual_branch_used).
    """
    # Decide the branch we will use
    if requested_branch:
        if branch_exists_remote(url, requested_branch):
            branch = requested_branch
        else:
            msg = f"[{name}] requested branch '{requested_branch}' does not exist on remote."
            if strict_branches:
                raise RuntimeError(msg)
            sys.stderr.write(msg + " Falling back to remote default branch.\n")
            branch = remote_default_branch(url, is_local_repo=False)
    else:
        branch = remote_default_branch(url, is_local_repo=False)

    rdir = repo_dir_for(name)
    if not rdir.exists():
        rdir.parent.mkdir(parents=True, exist_ok=True)
        # Partial clone, single branch
        clone_cmd = [
            "git", "clone",
            "--single-branch",
            "--branch", branch,
            "--filter=blob:none",
            "--no-tags",
            url, str(rdir),
        ]
        run(clone_cmd)
    else:
        if not (rdir / ".git").exists():
            raise RuntimeError(f"Path {rdir} exists but is not a git repository.")
        # ensure correct origin
        run(["git", "remote", "set-url", "origin", url], cwd=rdir)

    # Fetch ONLY the chosen branch, with shallow-since if provided
    fetch_cmd = [
        "git", "fetch",
        "--no-tags",
        "--prune",
        "--filter=blob:none",
        "origin",
        f"+refs/heads/{branch}:refs/remotes/origin/{branch}",
    ]
    if shallow_since:
        fetch_cmd.insert(4, f"--shallow-since={shallow_since}")  # after --filter
    run(fetch_cmd, cwd=rdir)

    return rdir, branch


def commit_at_time(repo_dir: Path, branch: str, when_local: dt.datetime) -> str:
    """Return the commit hash that was HEAD at or before the given local time."""
    assert when_local.tzinfo is not None, "Datetime must be timezone-aware"
    offset = when_local.utcoffset()
    total_minutes = int(offset.total_seconds() // 60)
    sign = "+" if total_minutes >= 0 else "-"
    total_minutes = abs(total_minutes)
    hh = total_minutes // 60
    mm = total_minutes % 60
    tz_str = f"{sign}{hh:02d}{mm:02d}"
    when_str = when_local.strftime(f"%Y-%m-%d %H:%M {tz_str}")

    try:
        res = run(
            ["git", "rev-list", "-1", "--before", when_str, f"origin/{branch}"],
            cwd=repo_dir,
        )
        return res.stdout.strip() or ""
    except subprocess.CalledProcessError:
        return ""


def main():
    parser = argparse.ArgumentParser(
        description="Collect git HEAD hashes for each day at 12:00 and 23:59."
    )
    parser.add_argument(
        "--branch",
        dest="default_branch",
        type=str,
        help="Default branch to use if a repo has no 'branch' configured in REPOS.",
    )
    parser.add_argument(
        "--strict-branches",
        action="store_true",
        help="Fail if a requested branch is missing on a repo instead of falling back.",
    )
    args = parser.parse_args()

    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # Build date/times
    now = dt.datetime.now(TZ)
    dates = [(now - dt.timedelta(days=i)).date() for i in range(1, DAYS + 1)]
    earliest_needed = min(dates)
    # one day earlier to be safe for --before boundary
    shallow_since_str = (earliest_needed - dt.timedelta(days=1)).isoformat()

    # Prepare repos (clone/fetch only the selected branch)
    repo_info = {}
    for name, cfg in REPOS.items():
        print(f"{name}:")
        url = cfg["url"]
        requested = cfg.get("branch") or args.default_branch  # REPOS branch wins; else CLI default; else None
        rdir, actual_branch = ensure_repo_local(
            name,
            url,
            requested_branch=requested,
            shallow_since=shallow_since_str if requested else None,  # only shallow when branch is known
            strict_branches=args.strict_branches,
        )
        repo_info[name] = (rdir, actual_branch)

    # Timestamps to query
    timestamps = []
    for d in sorted(dates):
        for hh, mm in TIMES:
            timestamps.append(dt.datetime(d.year, d.month, d.day, hh, mm, tzinfo=TZ))

    # Write CSV
    header = ["date"] + [k for k in repo_info.keys()]
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for ts in timestamps:
            row = [ts.isoformat()]
            for key in header[1:]:
                rdir, br = repo_info[key]
                row.append(commit_at_time(rdir, br, ts))
            writer.writerow(row)

    print(f"Wrote {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
