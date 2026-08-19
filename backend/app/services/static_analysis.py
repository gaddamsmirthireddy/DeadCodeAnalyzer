from sqlalchemy.orm import Session

from app.analyzers.static.analyzer import CandidateResult
from app.models.candidate import Candidate
from app.models.evidence import Evidence


def save_static_analysis(
    db: Session,
    investigation_id: int,
    candidates: list[CandidateResult],
) -> list[Candidate]:
    """
    Persist static analyzer results.

    The caller owns the transaction.
    """

    saved_candidates: list[Candidate] = []

    for result in candidates:
        candidate = Candidate(
            investigation_id=investigation_id,
            symbol=result.symbol,
            reason=result.reason,
            confidence=result.confidence,
        )

        db.add(candidate)
        db.flush()

        for evidence_result in result.evidence:
            evidence = Evidence(
                candidate_id=candidate.id,
                file_path=evidence_result.file_path,
                line_number=evidence_result.line_number,
                snippet=evidence_result.snippet,
                kind=evidence_result.kind,
            )

            db.add(evidence)

        saved_candidates.append(candidate)

    db.flush()

    for candidate in saved_candidates:
        db.refresh(candidate)

    return saved_candidates