"""Regression coverage for scripts/check-pr-size.sh (also .githooks/pre-commit,
which just calls it).

Runs the real script as a subprocess against a throwaway git repo, the
same pattern tests/test_session_checkin_hook.py already uses for
.claude/hooks/session-checkin.sh.
"""

import subprocess
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[1] / "scripts" / "check-pr-size.sh"


def _run_hook(cwd):
    return subprocess.run(
        ["bash", str(HOOK)],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def _git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture
def git_repo(tmp_path):
    """A throwaway repo with an origin/main ref at its initial commit,
    so the hook has a base to diff against -- no real remote needed,
    the hook only ever calls git rev-parse/merge-base on it."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git("init", "-q", "-b", "main", cwd=repo)
    _git("config", "user.email", "test@example.com", cwd=repo)
    _git("config", "user.name", "Test", cwd=repo)
    (repo / "README.md").write_text("hello\n")
    _git("add", "README.md", cwd=repo)
    _git("commit", "-q", "-m", "init", cwd=repo)
    _git("update-ref", "refs/remotes/origin/main", "HEAD", cwd=repo)
    return repo


class TestBelowThreshold:
    def test_small_committed_diff_produces_no_warning(self, git_repo):
        (git_repo / "small.txt").write_text("a few lines\nmore\n")
        _git("add", "small.txt", cwd=git_repo)
        _git("commit", "-q", "-m", "small change", cwd=git_repo)

        result = _run_hook(git_repo)

        assert result.returncode == 0
        assert result.stderr == ""


class TestOverThreshold:
    def test_large_committed_diff_warns_non_blocking(self, git_repo):
        (git_repo / "big.txt").write_text("\n".join(f"line {i}" for i in range(500)))
        _git("add", "big.txt", cwd=git_repo)
        _git("commit", "-q", "-m", "big change", cwd=git_repo)

        result = _run_hook(git_repo)

        assert result.returncode == 0  # a nudge, never blocking
        assert "still belong in one PR" in result.stderr

    def test_many_small_files_warns_on_file_count(self, git_repo):
        for i in range(20):
            (git_repo / f"file{i}.txt").write_text("one line\n")
        _git("add", "-A", cwd=git_repo)
        _git("commit", "-q", "-m", "many files", cwd=git_repo)

        result = _run_hook(git_repo)

        assert result.returncode == 0
        assert "20 files" in result.stderr

    def test_staged_but_uncommitted_diff_also_counts(self, git_repo):
        (git_repo / "big.txt").write_text("\n".join(f"line {i}" for i in range(500)))
        _git("add", "big.txt", cwd=git_repo)
        # deliberately not committed -- the hook must still see it

        result = _run_hook(git_repo)

        assert result.returncode == 0
        assert "still belong in one PR" in result.stderr


class TestNoBase:
    def test_no_origin_ref_silently_does_nothing(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _git("init", "-q", "-b", "main", cwd=repo)
        _git("config", "user.email", "test@example.com", cwd=repo)
        _git("config", "user.name", "Test", cwd=repo)
        (repo / "README.md").write_text("hello\n")
        _git("add", "README.md", cwd=repo)
        _git("commit", "-q", "-m", "init", cwd=repo)
        # no origin/main or origin/master ref at all

        result = _run_hook(repo)

        assert result.returncode == 0
        assert result.stderr == ""
