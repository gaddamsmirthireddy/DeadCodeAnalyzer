from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.investigation import Investigation
from app.schemas.investigation import InvestigationCreate


def create_investigation(
    db: Session,
    investigation_data: InvestigationCreate,
) -> Investigation:
    investigation = Investigation(
        repository_id=investigation_data.repository_id,
        summary=investigation_data.summary,
    )

    db.add(investigation)
    db.commit()
    db.refresh(investigation)

    return investigation


def list_investigations(
    db: Session,
) -> list[Investigation]:
    statement = select(Investigation).order_by(Investigation.id)

    return list(db.scalars(statement).all())


def get_investigation(
    db: Session,
    investigation_id: int,
) -> Investigation | None:
    return db.get(Investigation, investigation_id)


def delete_investigation(
    db: Session,
    investigation_id: int,
) -> bool:
    investigation = db.get(Investigation, investigation_id)

    if investigation is None:
        return False

    db.delete(investigation)
    db.commit()

    return True