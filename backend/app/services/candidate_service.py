from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.schemas.candidate import CandidateCreate


def create_candidate(
    db: Session,
    candidate_data: CandidateCreate,
) -> Candidate:
    candidate = Candidate(
        investigation_id=candidate_data.investigation_id,
        symbol=candidate_data.symbol,
        reason=candidate_data.reason,
        confidence=candidate_data.confidence,
    )

    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    return candidate


def get_candidate(
    db: Session,
    candidate_id: int,
) -> Candidate | None:
    return db.get(Candidate, candidate_id)