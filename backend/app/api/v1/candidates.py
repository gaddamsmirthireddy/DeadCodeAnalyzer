from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.candidate import CandidateCreate, CandidateResponse
from app.services.candidate_service import (
    create_candidate,
    delete_candidate,
    get_candidate,
    list_candidates,
)

router = APIRouter(
    prefix="/candidates",
    tags=["candidates"],
)


@router.post("", response_model=CandidateResponse)
def create_candidate_endpoint(
    candidate_data: CandidateCreate,
    db: Session = Depends(get_db),
) -> CandidateResponse:
    return create_candidate(db, candidate_data)


@router.get("/{candidate_id}", response_model=CandidateResponse)
def get_candidate_endpoint(
    candidate_id: int,
    db: Session = Depends(get_db),
) -> CandidateResponse:
    candidate = get_candidate(db, candidate_id)

    if candidate is None:
        raise HTTPException(
            status_code=404,
            detail="Candidate not found",
        )

    return candidate

@router.get(
    "",
    response_model=list[CandidateResponse],
)
def list_candidates_endpoint(
    db: Session = Depends(get_db),
) -> list[CandidateResponse]:
    return list_candidates(db)


@router.delete(
    "/{candidate_id}",
)
def delete_candidate_endpoint(
    candidate_id: int,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    deleted = delete_candidate(
        db,
        candidate_id,
    )

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Candidate not found",
        )

    return {
        "message": "Candidate deleted successfully",
    }
