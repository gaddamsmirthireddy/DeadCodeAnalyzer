from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.evidence import Evidence
from app.schemas.evidence import EvidenceCreate


def create_evidence(
    db: Session,
    evidence_data: EvidenceCreate,
) -> Evidence:
    evidence = Evidence(
        candidate_id=evidence_data.candidate_id,
        file_path=evidence_data.file_path,
        line_number=evidence_data.line_number,
        snippet=evidence_data.snippet,
        kind=evidence_data.kind,
    )

    db.add(evidence)
    db.commit()
    db.refresh(evidence)

    return evidence


def list_evidence(
    db: Session,
) -> list[Evidence]:
    statement = select(Evidence).order_by(Evidence.id)

    return list(db.scalars(statement).all())


def get_evidence(
    db: Session,
    evidence_id: int,
) -> Evidence | None:
    return db.get(Evidence, evidence_id)


def delete_evidence(
    db: Session,
    evidence_id: int,
) -> bool:
    evidence = db.get(Evidence, evidence_id)

    if evidence is None:
        return False

    db.delete(evidence)
    db.commit()

    return True
