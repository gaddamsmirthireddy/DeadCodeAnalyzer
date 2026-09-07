from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import git


@dataclass(frozen=True)
class LineBlameInfo:
    commit_hash: str
    author: str
    author_email: str
    committed_date: datetime
    summary: str
    line_number: int


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


def get_line_blame(
    repo_path: Path | str,
    relative_file_path: str,
    line_number: int,
) -> LineBlameInfo | None:
    """
    Find the exact commit and author that last modified a specific line (1-indexed).
    Returns None if blame fails or the line number is out of range.
    """
    repo_path = Path(repo_path)
    repo, git_path = _get_repo_and_rel_path(repo_path, relative_file_path)
    if repo is None or git_path is None:
        return None

    try:
        blames = repo.blame("HEAD", git_path)

        current_line = 1
        for commit, lines in blames:
            count = len(lines)
            if current_line <= line_number < current_line + count:
                committed_date = datetime.fromtimestamp(
                    commit.committed_date, tz=timezone.utc
                )
                summary = (
                    commit.message.strip().split("\n")[0]
                    if commit.message
                    else ""
                )
                return LineBlameInfo(
                    commit_hash=commit.hexsha,
                    author=(
                        commit.author.name if commit.author else "Unknown"
                    ),
                    author_email=(
                        commit.author.email if commit.author else ""
                    ),
                    committed_date=committed_date,
                    summary=summary,
                    line_number=line_number,
                )
            current_line += count

        return None
    except Exception:
        return None

