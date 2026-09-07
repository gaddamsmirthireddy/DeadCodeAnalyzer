from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import SessionLocal, get_db
from app.schemas.investigation import (
    InvestigationCreate,
    InvestigationResponse,
    InvestigationResultsResponse,
)
from app.services.investigation_service import (
    create_investigation,
    delete_investigation,
    get_investigation,
    get_investigation_results,
    list_investigations,
    run_investigation,
)

router = APIRouter(
    prefix="/investigations",
    tags=["investigations"],
)


def _run_investigation_background(investigation_id: int) -> None:
    db = SessionLocal()
    try:
        run_investigation(db, investigation_id)
    except Exception:
        # Errors and failure status are handled and saved inside run_investigation
        pass
    finally:
        db.close()


@router.post(
    "",
    response_model=InvestigationResponse,
)
def create_investigation_endpoint(
    investigation_data: InvestigationCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> InvestigationResponse:
    investigation = create_investigation(
        db,
        investigation_data,
    )
    background_tasks.add_task(
        _run_investigation_background,
        investigation.id,
    )
    return investigation


@router.post(
    "/{investigation_id}/run",
    response_model=InvestigationResponse,
)
def run_investigation_endpoint(
    investigation_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> InvestigationResponse:
    investigation = get_investigation(db, investigation_id)
    if investigation is None:
        raise HTTPException(
            status_code=404,
            detail="Investigation not found",
        )

    background_tasks.add_task(
        _run_investigation_background,
        investigation_id,
    )
    return investigation


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


@router.get(
    "/{investigation_id}/results",
    response_model=InvestigationResultsResponse,
)
def get_investigation_results_endpoint(
    investigation_id: int,
    db: Session = Depends(get_db),
) -> InvestigationResultsResponse:
    results = get_investigation_results(db, investigation_id)
    if results is None:
        raise HTTPException(
            status_code=404,
            detail="Investigation not found",
        )
    return results


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