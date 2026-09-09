from pathlib import Path
import git
import pytest
from fastapi import HTTPException

from app.models.repository import Repository
from app.schemas.repository import RepositoryCreate
from app.services.repository_service import (
    _extract_repo_name,
    create_repository,
    delete_repository,
    get_repository,
    list_repositories,
)


def test_extract_repo_name():
    assert _extract_repo_name("https://github.com/psf/requests.git") == "requests"
    assert _extract_repo_name("https://github.com/pallets/flask") == "flask"
    assert _extract_repo_name("git@github.com:org/custom-repo.git") == "custom-repo"


def test_create_repository_local_path(db_session, tmp_path):
    repo_dir = tmp_path / "my_project"
    repo_dir.mkdir()

    repo = create_repository(
        db_session,
        RepositoryCreate(name="Local Test Repo", path=str(repo_dir)),
    )
    assert repo.id is not None
    assert repo.name == "Local Test Repo"
    assert repo.path == str(repo_dir)


def test_create_repository_invalid_local_path_raises_400(db_session):
    with pytest.raises(HTTPException) as exc:
        create_repository(
            db_session,
            RepositoryCreate(name="Invalid", path="C:/non_existent_folder_path_12345"),
        )
    assert exc.value.status_code == 400
    assert "Local path does not exist" in exc.value.detail


def test_create_repository_clones_git_url(db_session, tmp_path):
    # 1. Setup a local origin git repo to act as the remote git server
    origin_dir = tmp_path / "remote_origin"
    origin_repo = git.Repo.init(origin_dir)
    with origin_repo.config_writer() as cfg:
        cfg.set_value("user", "name", "Git Clone Tester")
        cfg.set_value("user", "email", "tester@codearchaeologist.ai")

    dummy_file = origin_dir / "app.py"
    dummy_file.write_text("def hello(): return 'world'\n", encoding="utf-8")
    origin_repo.index.add(["app.py"])
    origin_repo.index.commit("feat: initial commit")

    # 2. Use file:// URL to test Git cloning without depending on an internet connection
    git_url = f"file:///{origin_dir.as_posix()}"

    repo = create_repository(
        db_session,
        RepositoryCreate(url=git_url),
    )

    assert repo.id is not None
    assert "remote_origin" in repo.name
    cloned_path = Path(repo.path)
    assert cloned_path.exists()
    assert (cloned_path / "app.py").exists()
    assert (cloned_path / ".git").exists()