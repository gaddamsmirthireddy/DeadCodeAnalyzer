from pathlib import Path

import git
import pytest

from app.analyzers.git.analyzer import analyze_git
from app.analyzers.git.blame import get_line_blame
from app.analyzers.git.history import get_file_git_history
from app.analyzers.static.analyzer import CandidateResult, EvidenceResult


@pytest.fixture
def git_repo(tmp_path: Path):
    """Creates a temporary Git repository with committed Python files."""
    repo = git.Repo.init(tmp_path)
    with repo.config_writer() as config:
        config.set_value("user", "name", "Archaeologist Tester")
        config.set_value("user", "email", "tester@codearchaeologist.ai")

    test_file = tmp_path / "module.py"
    test_file.write_text(
        "def deprecated_func():\n    return 'old'\n\ndef active_func():\n    return 'new'\n",
        encoding="utf-8",
    )

    repo.index.add(["module.py"])
    repo.index.commit("feat: initial commit with deprecated_func and active_func")

    return tmp_path


class TestGitHistory:
    """Tests for Git commit history traversal and file metadata."""

    def test_get_file_git_history_success(self, git_repo: Path):
        history = get_file_git_history(git_repo, "module.py")
        assert history is not None
        assert history.commit_count == 1
        assert history.last_commit_author == "Archaeologist Tester"
        assert "initial commit" in history.last_commit_message
        assert history.age_in_days >= 0
        assert "Archaeologist Tester" in history.authors

    def test_get_file_git_history_non_git_fallback(self, tmp_path: Path):
        non_git_file = tmp_path / "plain.py"
        non_git_file.write_text("def plain(): pass\n", encoding="utf-8")
        assert get_file_git_history(tmp_path, "plain.py") is None


class TestGitBlame:
    """Tests for line-by-line Git blame resolution."""

    def test_get_line_blame_success(self, git_repo: Path):
        blame = get_line_blame(git_repo, "module.py", line_number=1)
        assert blame is not None
        assert blame.author == "Archaeologist Tester"
        assert blame.line_number == 1
        assert "initial commit" in blame.summary
        assert len(blame.commit_hash) == 40

    def test_get_line_blame_non_git_fallback(self, tmp_path: Path):
        assert get_line_blame(tmp_path, "plain.py", line_number=1) is None


class TestGitAnalyzer:
    """Tests for Git evidence generation and confidence tuning."""

    def test_enriches_candidates_with_git_evidence(self, git_repo: Path):
        initial_candidate = CandidateResult(
            symbol="module.py:deprecated_func",
            reason="Function 'deprecated_func' has no references.",
            confidence=0.70,
            evidence=[
                EvidenceResult(
                    file_path="module.py",
                    line_number=1,
                    snippet="def deprecated_func():",
                    kind="definition",
                )
            ],
        )

        enriched = analyze_git(git_repo, [initial_candidate])
        assert len(enriched) == 1
        result = enriched[0]
        assert len(result.evidence) == 2

        # First evidence is definition, second is Git
        assert result.evidence[0].kind == "definition"
        git_ev = result.evidence[1]
        assert git_ev.kind == "git"
        assert "Archaeologist Tester" in git_ev.snippet
        assert "commit" in git_ev.snippet

    def test_boosts_confidence_on_deprecation_keyword(self, git_repo: Path):
        initial_candidate = CandidateResult(
            symbol="module.py:deprecated_func",
            reason="Function 'deprecated_func' has no references.",
            confidence=0.70,
            evidence=[
                EvidenceResult(
                    file_path="module.py",
                    line_number=1,
                    snippet="def deprecated_func():",
                    kind="definition",
                )
            ],
        )

        enriched = analyze_git(git_repo, [initial_candidate])
        result = enriched[0]
        assert result.confidence != 0.70
        assert any(ev.kind == "git" for ev in result.evidence)

    def test_graceful_fallback_on_non_git_repo(self, tmp_path: Path):
        candidate = CandidateResult(
            symbol="plain.py:plain",
            reason="No references.",
            confidence=0.70,
            evidence=[
                EvidenceResult(
                    file_path="plain.py",
                    line_number=1,
                    snippet="def plain(): pass",
                    kind="definition",
                )
            ],
        )

        enriched = analyze_git(tmp_path, [candidate])
        assert len(enriched) == 1
        assert len(enriched[0].evidence) == 1
        assert enriched[0].evidence[0].kind == "definition"
