from sqlalchemy import select

from app.analyzers.static.analyzer import analyze_static
from app.db.database import SessionLocal
from app.models.candidate import Candidate
from app.models.evidence import Evidence
from app.models.investigation import Investigation
from app.models.repository import Repository
from app.services.static_analysis import save_static_analysis


FIXTURE_REPOSITORY = (
    "app/analyzers/tests/fixtures/static_repo"
)


def test_save_static_analysis():
    db = SessionLocal()

    try:
        repository = Repository(
            name="static-analysis-test",
            path=FIXTURE_REPOSITORY,
        )

        db.add(repository)
        db.flush()

        investigation = Investigation(
            repository_id=repository.id,
            status="queued",
            summary="Static analyzer persistence test",
        )

        db.add(investigation)
        db.flush()

        results = analyze_static(
            FIXTURE_REPOSITORY
        )

        assert results

        saved_candidates = save_static_analysis(
            db=db,
            investigation_id=investigation.id,
            candidates=results,
        )

        assert saved_candidates

        candidate_rows = db.execute(
            select(Candidate).where(
                Candidate.investigation_id
                == investigation.id
            )
        ).scalars().all()

        assert len(candidate_rows) == len(results)

        for candidate in candidate_rows:
            assert candidate.id is not None
            assert candidate.investigation_id == investigation.id
            assert candidate.symbol
            assert candidate.reason
            assert candidate.confidence >= 0.0

        candidate_ids = [
            candidate.id
            for candidate in candidate_rows
        ]

        evidence_rows = db.execute(
            select(Evidence).where(
                Evidence.candidate_id.in_(candidate_ids)
            )
        ).scalars().all()

        assert evidence_rows

        for evidence in evidence_rows:
            assert evidence.id is not None
            assert evidence.candidate_id in candidate_ids
            assert evidence.file_path
            assert evidence.snippet
            assert evidence.kind == "definition"

        for candidate in candidate_rows:
            candidate_evidence = [
                evidence
                for evidence in evidence_rows
                if evidence.candidate_id == candidate.id
            ]

            assert candidate_evidence

    finally:
        db.rollback()
        db.close()