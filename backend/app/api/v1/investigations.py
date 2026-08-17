from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.investigation import (
    InvestigationCreate,
    InvestigationResponse,
)
from app.services.investigation_service import (
    create_investigation,
    delete_investigation,
    get_investigation,
    list_investigations,
)


router = APIRouter(
    prefix="/investigations",
    tags=["investigations"],
)


@router.post(
    "",
    response_model=InvestigationResponse,
)
def create_investigation_endpoint(
    investigation_data: InvestigationCreate,
    db: Session = Depends(get_db),
) -> InvestigationResponse:
    return create_investigation(
        db,
        investigation_data,
    )


@router.get(
    "",
    response_model=list[InvestigationResponse],
)
def list_investigations_endpoint(
    db: Session = Depends(get_db),
) -> list[InvestigationResponse]:
    return list_investigations(db)


@router.get(
    "/{investigation_id}",
    response_model=InvestigationResponse,
)
def get_investigation_endpoint(
    investigation_id: int,
    db: Session = Depends(get_db),
) -> InvestigationResponse:
    investigation = get_investigation(
        db,
        investigation_id,
    )

    if investigation is None:
        raise HTTPException(
            status_code=404,
            detail="Investigation not found",
        )

    return investigation


@router.delete(
    "/{investigation_id}",
)
def delete_investigation_endpoint(
    investigation_id: int,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    deleted = delete_investigation(
        db,
        investigation_id,
    )

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Investigation not found",
        )

    return {
        "message": "Investigation deleted successfully",
    }