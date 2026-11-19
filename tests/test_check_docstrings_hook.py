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
    """Run the hook in `cwd`, capturing output."""
    return subprocess.run(
        ["bash", str(HOOK)],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def _git(*args, cwd):
    """Run a git command in `cwd`, failing on error."""
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture
def git_repo(tmp_path):
    """A throwaway git repo with one empty commit."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git("init", "-q", "-b", "main", cwd=repo)
    _git("config", "user.email", "test@example.com", cwd=repo)
    _git("config", "user.name", "Test", cwd=repo)
    _git("commit", "-q", "--allow-empty", "-m", "init", cwd=repo)
    return repo


class TestDocstringDetection:
    """Staged docstring edits get flagged."""
    def test_flags_a_staged_docstring_change_on_a_tracked_file(self, git_repo):
        """Flags a staged docstring change on a tracked file."""
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
        """Flags a brand new staged python file."""
        (git_repo / "new_module.py").write_text('"""A new module."""\n')
        _git("add", "new_module.py", cwd=git_repo)

        result = _run_hook(git_repo)

        assert result.returncode == 0
        assert "new_module.py" in result.stderr


class TestNotFlagged:
    """Changes that aren't docstring edits stay quiet."""
    def test_non_docstring_change_is_not_flagged(self, git_repo):
        """Non docstring change is not flagged."""
        (git_repo / "f.py").write_text("x = 1\n")
        _git("add", "f.py", cwd=git_repo)
        _git("commit", "-q", "-m", "add f", cwd=git_repo)
        (git_repo / "f.py").write_text("x = 2\n")
        _git("add", "f.py", cwd=git_repo)

        result = _run_hook(git_repo)

        assert result.returncode == 0
        assert result.stderr == ""

    def test_non_python_file_is_ignored_even_with_triple_quotes(self, git_repo):
        """Non python file is ignored even with triple quotes."""
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
