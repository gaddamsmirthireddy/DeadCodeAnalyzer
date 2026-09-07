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
        raw_blames = repo.blame("HEAD", git_path)
        if not raw_blames:
            return None

        current_line = 1
        for entry in raw_blames:  # type: ignore[union-attr]
            if not isinstance(entry, (list, tuple)) or len(entry) < 2:
                continue
            commit = entry[0]
            lines = entry[1]
            if not isinstance(lines, (list, tuple)):
                continue
            count = len(lines)
            if current_line <= line_number < current_line + count:
                date_val = getattr(commit, "committed_date", 0)
                committed_date = datetime.fromtimestamp(
                    date_val, tz=timezone.utc
                )
                raw_message = getattr(commit, "message", "")
                if isinstance(raw_message, bytes):
                    msg_text = raw_message.decode("utf-8", errors="replace")
                elif isinstance(raw_message, str):
                    msg_text = raw_message
                else:
                    msg_text = str(raw_message)

                summary = msg_text.strip().split("\n")[0] if msg_text else ""
                author_obj = getattr(commit, "author", None)
                author_name = getattr(author_obj, "name", None) or "Unknown"
                author_email = getattr(author_obj, "email", None) or ""
                commit_hash = getattr(commit, "hexsha", "") or ""

                return LineBlameInfo(
                    commit_hash=commit_hash,
                    author=author_name,
                    author_email=author_email,
                    committed_date=committed_date,
                    summary=summary,
                    line_number=line_number,
                )
            current_line += count

        return None
    except Exception:
        return None

