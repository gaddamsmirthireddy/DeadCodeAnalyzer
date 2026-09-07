from collections import defaultdict
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analyzers.git.analyzer import analyze_git
from app.analyzers.runtime.analyzer import analyze_runtime
from app.analyzers.static.analyzer import analyze_static
from app.models.candidate import Candidate
from app.models.evidence import Evidence
from app.models.investigation import Investigation
from app.models.repository import Repository
from app.schemas.evidence import EvidenceResponse
from app.schemas.investigation import (
    InvestigationCreate,
    InvestigationResultCandidate,
    InvestigationResultsResponse,
)
from app.services.static_analysis import save_static_analysis


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


def run_investigation(
    db: Session,
    investigation_id: int,
) -> Investigation:
    """
    Execute static analysis for an investigation, transitioning:
    queued -> running -> completed (or failed).
    """
    investigation = db.get(Investigation, investigation_id)
    if investigation is None:
        raise ValueError(f"Investigation {investigation_id} not found")

    repository = db.get(Repository, investigation.repository_id)
    if repository is None:
        investigation.status = "failed"
        investigation.summary = f"Repository {investigation.repository_id} not found"
        db.commit()
        db.refresh(investigation)
        return investigation

    investigation.status = "running"
    db.commit()
    db.refresh(investigation)

    try:
        repo_path = Path(repository.path)
        if not repo_path.exists():
            raise FileNotFoundError(f"Repository path does not exist: {repository.path}")

        candidates = analyze_static(repo_path)

        # Phase 3: Git History Analysis
        if (repo_path / ".git").exists():
            candidates = analyze_git(repo_path, candidates)

        # Phase 4: Runtime Execution Analysis
        candidates = analyze_runtime(repo_path, candidates)

        save_static_analysis(
            db=db,
            investigation_id=investigation.id,
            candidates=candidates,
        )

        analyzers: list[str] = ["Static"]
        if any(any(ev.kind == "git" for ev in c.evidence) for c in candidates):
            analyzers.append("Git")
        if any(any(ev.kind == "runtime" for ev in c.evidence) for c in candidates):
            analyzers.append("Runtime")

        if len(analyzers) == 1:
            mode = analyzers[0]
        elif len(analyzers) == 2:
            mode = f"{analyzers[0]} & {analyzers[1]}"
        else:
            mode = f"{', '.join(analyzers[:-1])} & {analyzers[-1]}"

        investigation.status = "completed"
        investigation.summary = (
            f"{mode} analysis completed. Detected {len(candidates)} "
            "potentially dead code candidate(s)."
        )
        db.commit()
        db.refresh(investigation)
        return investigation

    except Exception as exc:
        db.rollback()
        investigation = db.get(Investigation, investigation_id)
        if investigation is not None:
            investigation.status = "failed"
            investigation.summary = f"Analysis failed: {exc}"
            db.commit()
            db.refresh(investigation)
        raise


def get_investigation_results(
    db: Session,
    investigation_id: int,
) -> InvestigationResultsResponse | None:
    """
    Fetch comprehensive investigation results including candidate list and evidence.
    """
    investigation = db.get(Investigation, investigation_id)
    if investigation is None:
        return None

    repository = db.get(Repository, investigation.repository_id)
    repo_name = repository.name if repository else "Unknown"

    candidates = list(
        db.scalars(
            select(Candidate)
            .where(Candidate.investigation_id == investigation_id)
            .order_by(Candidate.id)
        ).all()
    )

    candidate_ids = [c.id for c in candidates]
    evidence_by_candidate: dict[int, list[EvidenceResponse]] = defaultdict(list)

    if candidate_ids:
        evidence_rows = db.scalars(
            select(Evidence)
            .where(Evidence.candidate_id.in_(candidate_ids))
            .order_by(Evidence.id)
        ).all()

        for ev in evidence_rows:
            evidence_by_candidate[ev.candidate_id].append(
                EvidenceResponse.model_validate(ev)
            )

    candidate_results = [
        InvestigationResultCandidate(
            id=c.id,
            investigation_id=c.investigation_id,
            symbol=c.symbol,
            reason=c.reason,
            confidence=c.confidence,
            created_at=c.created_at,
            evidence=evidence_by_candidate[c.id],
        )
        for c in candidates
    ]

    return InvestigationResultsResponse(
        investigation_id=investigation.id,
        repository_id=investigation.repository_id,
        repository_name=repo_name,
        status=investigation.status,
        summary=investigation.summary,
        created_at=investigation.created_at,
        candidate_count=len(candidates),
        candidates=candidate_results,
    )