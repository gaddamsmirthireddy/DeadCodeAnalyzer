import os
import re
import uuid
from pathlib import Path

import git
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.repository import Repository
from app.schemas.repository import RepositoryCreate

# Dedicated workspace directory for cloned repositories
WORKSPACES_DIR = Path(__file__).resolve().parent.parent.parent / "workspaces"


def _extract_repo_name(url: str) -> str:
    """Extracts a clean repository name from a git URL (e.g., https://github.com/psf/requests.git -> requests)."""
    clean_url = url.rstrip("/")
    if clean_url.endswith(".git"):
        clean_url = clean_url[:-4]
    name = clean_url.split("/")[-1]
    # Remove any unsafe filesystem characters
    name = re.sub(r"[^a-zA-Z0-9_\-]", "_", name)
    return name or "cloned_repo"


def create_repository(
    db: Session,
    repository_data: RepositoryCreate,
) -> Repository:
    """
    Registers a repository.
    If 'url' is provided, automatically clones the remote git repository into backend/workspaces/.
    If 'path' is provided, validates that the local folder exists.
    """
    repo_name = repository_data.name
    repo_path_str = repository_data.path

    # Case 1: Remote Git URL provided -> Clone it!
    if repository_data.url:
        inferred_name = _extract_repo_name(repository_data.url)
        if not repo_name:
            repo_name = inferred_name

        WORKSPACES_DIR.mkdir(parents=True, exist_ok=True)
        # Create a unique folder to avoid collisions if cloned multiple times
        unique_suffix = uuid.uuid4().hex[:6]
        target_dir = WORKSPACES_DIR / f"{inferred_name}_{unique_suffix}"

        try:
            # Clone with depth=100 for fast download while preserving enough git history for archaeology
            git.Repo.clone_from(
                repository_data.url,
                target_dir,
                depth=100,
            )
        except Exception as err:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to clone Git repository from '{repository_data.url}': {err}",
            )

        repo_path_str = str(target_dir)

    # Case 2: Local folder path provided
    else:
        if not repo_name:
            repo_name = Path(repo_path_str).name or "local_repo"

        local_path = Path(repo_path_str)
        if not local_path.exists():
            raise HTTPException(
                status_code=400,
                detail=f"Local path does not exist: {repo_path_str}",
            )

    repository = Repository(
        name=repo_name,
        path=repo_path_str,
    )

    db.add(repository)
    db.commit()
    db.refresh(repository)

    return repository


def get_repository(
    db: Session,
    repository_id: int,
) -> Repository | None:
    return db.get(Repository, repository_id)


def list_repositories(db: Session) -> list[Repository]:
    return db.query(Repository).order_by(Repository.id).all()


def delete_repository(
    db: Session,
    repository_id: int,
) -> bool:
    repository = db.get(Repository, repository_id)

    if repository is None:
        return False

    db.delete(repository)
    db.commit()

    return True