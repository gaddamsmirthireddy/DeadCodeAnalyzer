from sqlalchemy.orm import Session

from app.models.repository import Repository
from app.schemas.repository import RepositoryCreate


def create_repository(
    db: Session,
    repository_data: RepositoryCreate,
) -> Repository:
    repository = Repository(
        name=repository_data.name,
        path=repository_data.path,
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