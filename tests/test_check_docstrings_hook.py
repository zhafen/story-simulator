"""Regression coverage for scripts/check-docstrings.sh
(.githooks/pre-commit's docstring check).

Runs the real script as a subprocess against a throwaway git repo, same
pattern as test_check_pr_size_hook.py.
"""

import subprocess
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[1] / "scripts" / "check-docstrings.sh"


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
    repo = tmp_path / "repo"
    repo.mkdir()
    _git("init", "-q", "-b", "main", cwd=repo)
    _git("config", "user.email", "test@example.com", cwd=repo)
    _git("config", "user.name", "Test", cwd=repo)
    _git("commit", "-q", "--allow-empty", "-m", "init", cwd=repo)
    return repo


class TestDocstringDetection:
    def test_flags_a_staged_docstring_change_on_a_tracked_file(self, git_repo):
        (git_repo / "f.py").write_text('"""old"""\n')
        _git("add", "f.py", cwd=git_repo)
        _git("commit", "-q", "-m", "add f", cwd=git_repo)
        (git_repo / "f.py").write_text('"""new, longer docstring content here"""\n')
        _git("add", "f.py", cwd=git_repo)

        result = _run_hook(git_repo)

        assert result.returncode == 0  # a nudge, never blocking
        assert "f.py" in result.stderr
        assert "review each for conciseness" in result.stderr

    def test_flags_a_brand_new_staged_python_file(self, git_repo):
        (git_repo / "new_module.py").write_text('"""A new module."""\n')
        _git("add", "new_module.py", cwd=git_repo)

        result = _run_hook(git_repo)

        assert result.returncode == 0
        assert "new_module.py" in result.stderr


class TestNotFlagged:
    def test_non_docstring_change_is_not_flagged(self, git_repo):
        (git_repo / "f.py").write_text("x = 1\n")
        _git("add", "f.py", cwd=git_repo)
        _git("commit", "-q", "-m", "add f", cwd=git_repo)
        (git_repo / "f.py").write_text("x = 2\n")
        _git("add", "f.py", cwd=git_repo)

        result = _run_hook(git_repo)

        assert result.returncode == 0
        assert result.stderr == ""

    def test_non_python_file_is_ignored_even_with_triple_quotes(self, git_repo):
        (git_repo / "notes.txt").write_text('"""looks like a docstring but is not python"""\n')
        _git("add", "notes.txt", cwd=git_repo)

        result = _run_hook(git_repo)

        assert result.returncode == 0
        assert result.stderr == ""

    def test_unstaged_docstring_edit_is_not_flagged(self, git_repo):
        """The whole reason this hook exists alongside a diff-based
        check rather than a working-tree scan: only staged content
        counts, since that's what's about to be committed."""
        (git_repo / "f.py").write_text('"""old"""\n')
        _git("add", "f.py", cwd=git_repo)
        _git("commit", "-q", "-m", "add f", cwd=git_repo)
        (git_repo / "f.py").write_text('"""edited but never staged"""\n')
        # deliberately not git add'ed

        result = _run_hook(git_repo)

        assert result.returncode == 0
        assert result.stderr == ""
