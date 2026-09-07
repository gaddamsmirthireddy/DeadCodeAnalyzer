from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import git


@dataclass(frozen=True)
class FileGitHistory:
    commit_count: int
    last_commit_hash: str
    last_commit_date: datetime
    last_commit_author: str
    last_commit_message: str
    age_in_days: int
    authors: list[str]


def _get_repo_and_rel_path(
    repo_path: Path,
    relative_file_path: str,
) -> tuple[git.Repo | None, str | None]:
    try:
        repo = git.Repo(repo_path, search_parent_directories=False)
        full_file_path = (repo_path / relative_file_path).resolve()
        if repo.working_tree_dir is None:
            return None, None
        repo_root = Path(repo.working_tree_dir).resolve()
        git_rel_path = full_file_path.relative_to(repo_root).as_posix()
        return repo, git_rel_path
    except Exception:
        return None, None


def get_file_git_history(
    repo_path: Path | str,
    relative_file_path: str,
) -> FileGitHistory | None:
    """
    Extract Git commit history for a file in the repository.
    Returns None if the path is not a Git repository or has no commits.
    """
    repo_path = Path(repo_path)
    repo, git_path = _get_repo_and_rel_path(repo_path, relative_file_path)
    if repo is None or git_path is None:
        return None

    try:
        commits = list(repo.iter_commits(paths=git_path, max_count=50))
        if not commits:
            return None

        last_commit = commits[0]
        commit_date = datetime.fromtimestamp(
            last_commit.committed_date, tz=timezone.utc
        )
        now = datetime.now(timezone.utc)
        age_in_days = max(0, (now - commit_date).days)

        authors = sorted(
            {c.author.name for c in commits if c.author and c.author.name}
        )

        raw_msg = getattr(last_commit, "message", "")
        if isinstance(raw_msg, bytes):
            msg_text = raw_msg.decode("utf-8", errors="replace")
        elif isinstance(raw_msg, str):
            msg_text = raw_msg
        else:
            msg_text = str(raw_msg)
        first_line_message = msg_text.strip().split("\n")[0] if msg_text else ""

        author_name = (
            last_commit.author.name
            if (last_commit.author and last_commit.author.name)
            else "Unknown"
        )

        return FileGitHistory(
            commit_count=len(commits),
            last_commit_hash=last_commit.hexsha,
            last_commit_date=commit_date,
            last_commit_author=author_name,
            last_commit_message=first_line_message,
            age_in_days=age_in_days,
            authors=authors,
        )
    except Exception:
        return None

