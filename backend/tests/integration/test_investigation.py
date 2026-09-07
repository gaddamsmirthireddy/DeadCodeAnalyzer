from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db.database import SessionLocal
from app.main import app
from app.models.investigation import Investigation
from app.models.repository import Repository
from app.services.investigation_service import (
    get_investigation_results,
    run_investigation,
)

FIXTURE_REPOSITORY = (
    Path(__file__).resolve().parent.parent
    / "fixtures"
    / "Static_repo"
)


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_run_investigation_service_lifecycle(db_session):
    # 1. Create a repository pointing to the fixture
    repo = Repository(
        name="test-repo-lifecycle",
        path=str(FIXTURE_REPOSITORY),
    )
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)

    # 2. Create an investigation in queued status
    investigation = Investigation(
        repository_id=repo.id,
        status="queued",
        summary="Initial queued status",
    )
    db_session.add(investigation)
    db_session.commit()
    db_session.refresh(investigation)

    assert investigation.status == "queued"

    # 3. Execute investigation
    completed_inv = run_investigation(db_session, investigation.id)

    assert completed_inv.status == "completed"
    assert "Static analysis completed" in completed_inv.summary
    assert "candidate(s)" in completed_inv.summary

    # 4. Fetch results
    results = get_investigation_results(db_session, investigation.id)
    assert results is not None
    assert results.investigation_id == investigation.id
    assert results.repository_id == repo.id
    assert results.status == "completed"
    assert results.candidate_count > 0

    symbols = {c.symbol for c in results.candidates}
    assert "user.py:delete_user" in symbols
    assert "user.py:User" in symbols

    # Check evidence attached
    for candidate in results.candidates:
        assert len(candidate.evidence) > 0
        ev = candidate.evidence[0]
        assert ev.snippet
        assert ev.kind == "definition"


def test_run_investigation_service_failure_invalid_path(db_session):
    repo = Repository(
        name="nonexistent-repo",
        path="/path/that/does/not/exist/deadcode_dummy",
    )
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)

    investigation = Investigation(
        repository_id=repo.id,
        status="queued",
    )
    db_session.add(investigation)
    db_session.commit()
    db_session.refresh(investigation)

    with pytest.raises(FileNotFoundError):
        run_investigation(db_session, investigation.id)

    db_session.refresh(investigation)
    assert investigation.status == "failed"
    assert "Analysis failed" in investigation.summary


def test_api_investigation_flow_with_background_tasks(db_session):
    client = TestClient(app)

    # 1. Create Repository via API or DB
    repo = Repository(
        name="test-api-repo",
        path=str(FIXTURE_REPOSITORY),
    )
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)

    # 2. Trigger POST /api/v1/investigations (TestClient executes background tasks)
    response = client.post(
        "/api/v1/investigations",
        json={"repository_id": repo.id, "summary": "API scan test"},
    )
    assert response.status_code == 200
    created_data = response.json()
    investigation_id = created_data["id"]

    # In TestClient, BackgroundTasks run before the response is fully completed
    # 3. Verify GET /api/v1/investigations/{id} status is completed
    get_response = client.get(f"/api/v1/investigations/{investigation_id}")
    assert get_response.status_code == 200
    inv_data = get_response.json()
    assert inv_data["status"] == "completed"

    # 4. Verify GET /api/v1/investigations/{id}/results
    results_response = client.get(
        f"/api/v1/investigations/{investigation_id}/results"
    )
    assert results_response.status_code == 200
    results_data = results_response.json()
    assert results_data["investigation_id"] == investigation_id
    assert results_data["status"] == "completed"
    assert results_data["candidate_count"] > 0
    assert len(results_data["candidates"]) == results_data["candidate_count"]

    symbols = [c["symbol"] for c in results_data["candidates"]]
    assert "user.py:delete_user" in symbols
    assert "user.py:User" in symbols

    # 5. Test POST /api/v1/investigations/{id}/run manual trigger
    run_response = client.post(f"/api/v1/investigations/{investigation_id}/run")
    assert run_response.status_code == 200


def test_investigation_on_git_repository_saves_git_evidence(db_session, tmp_path):
    import git

    # 1. Initialize a git repository with a dead code candidate
    repo_git = git.Repo.init(tmp_path)
    with repo_git.config_writer() as config:
        config.set_value("user", "name", "Git Integration Bot")
        config.set_value("user", "email", "bot@codearchaeologist.ai")

    test_file = tmp_path / "orders.py"
    test_file.write_text("def unused_order_handler():\n    pass\n", encoding="utf-8")

    repo_git.index.add(["orders.py"])
    repo_git.index.commit("feat: add legacy order handler")

    # 2. Save repository in DB and create investigation
    repo = Repository(
        name="git-integration-test-repo",
        path=str(tmp_path),
    )
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)

    investigation = Investigation(
        repository_id=repo.id,
        status="queued",
    )
    db_session.add(investigation)
    db_session.commit()
    db_session.refresh(investigation)

    # 3. Run investigation
    completed_inv = run_investigation(db_session, investigation.id)
    assert completed_inv.status == "completed"
    assert "Static & Git analysis completed" in completed_inv.summary

    # 4. Fetch results
    results = get_investigation_results(db_session, investigation.id)
    assert results is not None
    assert results.candidate_count == 1

    candidate = results.candidates[0]
    assert candidate.symbol == "orders.py:unused_order_handler"
    assert len(candidate.evidence) == 2

    evidence_kinds = {ev.kind for ev in candidate.evidence}
    assert "definition" in evidence_kinds
    assert "git" in evidence_kinds

    git_ev = next(ev for ev in candidate.evidence if ev.kind == "git")
    assert "Git Integration Bot" in git_ev.snippet
    assert "legacy order handler" in git_ev.snippet


def test_investigation_with_runtime_and_git_traces_persists_multi_evidence(
    db_session, tmp_path
):
    import json

    import git

    # 1. Setup git repo
    repo_git = git.Repo.init(tmp_path)
    with repo_git.config_writer() as config:
        config.set_value("user", "name", "Full Archaeology Agent")
        config.set_value("user", "email", "agent@codearchaeologist.ai")

    test_file = tmp_path / "billing.py"
    test_file.write_text(
        "def active_billing():\n    return 100\n\ndef zombie_refund():\n    return 0\n",
        encoding="utf-8",
    )
    repo_git.index.add(["billing.py"])
    repo_git.index.commit("feat: initial billing module")

    # 2. Add runtime_trace.json (billing.py was executed, active_billing was hit, zombie_refund was not)
    trace_payload = {
        "executed_lines": {
            "billing.py": [1, 2],  # lines 4, 5 (zombie_refund) were never executed!
        },
        "call_counts": {
            "billing.py:active_billing": 88,
            "billing.py:zombie_refund": 0,
        },
    }
    (tmp_path / "runtime_trace.json").write_text(
        json.dumps(trace_payload), encoding="utf-8"
    )

    # 3. Create repository and investigation
    repo = Repository(
        name="full-archaeology-test-repo",
        path=str(tmp_path),
    )
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)

    investigation = Investigation(
        repository_id=repo.id,
        status="queued",
    )
    db_session.add(investigation)
    db_session.commit()
    db_session.refresh(investigation)

    # 4. Run investigation
    completed_inv = run_investigation(db_session, investigation.id)
    assert completed_inv.status == "completed"
    assert "Static, Git & Runtime analysis completed" in completed_inv.summary

    # 5. Verify results endpoint payload
    results = get_investigation_results(db_session, investigation.id)
    assert results is not None

    candidates_by_sym = {c.symbol: c for c in results.candidates}
    assert "billing.py:zombie_refund" in candidates_by_sym

    zombie_cand = candidates_by_sym["billing.py:zombie_refund"]
    # Should have all 3 evidence types: definition, git, runtime!
    evidence_kinds = [ev.kind for ev in zombie_cand.evidence]
    assert "definition" in evidence_kinds
    assert "git" in evidence_kinds
    assert "runtime" in evidence_kinds

    runtime_ev = next(ev for ev in zombie_cand.evidence if ev.kind == "runtime")
    assert "0 executions observed" in runtime_ev.snippet
    # Zombie code confidence boosted
    assert zombie_cand.confidence >= 0.70



