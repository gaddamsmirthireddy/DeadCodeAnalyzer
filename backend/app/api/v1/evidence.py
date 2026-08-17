from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.evidence import EvidenceCreate, EvidenceResponse
from app.services.evidence_service import (
    create_evidence,
    delete_evidence,
    get_evidence,
    list_evidence,
)


router = APIRouter(
    prefix="/evidence",
    tags=["evidence"],
)


@router.post(
    "",
    response_model=EvidenceResponse,
)
def create_evidence_endpoint(
    evidence_data: EvidenceCreate,
    db: Session = Depends(get_db),
) -> EvidenceResponse:
    return create_evidence(
        db,
        evidence_data,
    )


@router.get(
    "",
    response_model=list[EvidenceResponse],
)
def list_evidence_endpoint(
    db: Session = Depends(get_db),
) -> list[EvidenceResponse]:
    return list_evidence(db)


@router.get(
    "/{evidence_id}",
    response_model=EvidenceResponse,
)
def get_evidence_endpoint(
    evidence_id: int,
    db: Session = Depends(get_db),
) -> EvidenceResponse:
    evidence = get_evidence(
        db,
        evidence_id,
    )

    if evidence is None:
        raise HTTPException(
            status_code=404,
            detail="Evidence not found",
        )

    return evidence


@router.delete(
    "/{evidence_id}",
)
def delete_evidence_endpoint(
    evidence_id: int,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    deleted = delete_evidence(
        db,
        evidence_id,
    )

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Evidence not found",
        )

    return {
        "message": "Evidence deleted successfully",
    }