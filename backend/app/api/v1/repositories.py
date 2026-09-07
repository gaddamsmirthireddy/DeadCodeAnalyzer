from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.repository import RepositoryCreate, RepositoryResponse
from app.services.repository_service import (
    create_repository,
    delete_repository,
    get_repository,
    list_repositories,
)

router = APIRouter(
    prefix="/repositories",
    tags=["repositories"],
)


@router.post("", response_model=RepositoryResponse)
def create_repository_endpoint(
    repository_data: RepositoryCreate,
    db: Session = Depends(get_db),
) -> RepositoryResponse:
    return create_repository(db, repository_data)


@router.get("", response_model=list[RepositoryResponse])
def list_repositories_endpoint(
    db: Session = Depends(get_db),
) -> list[RepositoryResponse]:
    return list_repositories(db)


@router.get("/{repository_id}", response_model=RepositoryResponse)
def get_repository_endpoint(
    repository_id: int,
    db: Session = Depends(get_db),
) -> RepositoryResponse:
    repository = get_repository(db, repository_id)

    if repository is None:
        raise HTTPException(
            status_code=404,
            detail="Repository not found",
        )

    return repository

@router.delete("/{repository_id}")
def delete_repository_endpoint(
    repository_id: int,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    deleted = delete_repository(db, repository_id)

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Repository not found",
        )

    return {"message": "Repository deleted successfully"}
