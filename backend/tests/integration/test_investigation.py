from pathlib import Path
from app.models.evidence import Evidence
import json
import git


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
    assert "analysis completed" in completed_inv.summary
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
    assert "Runtime" in completed_inv.summary
    assert "analysis completed" in completed_inv.summary

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

def test_investigation_with_test_analyzer_persists_test_evidence(db_session, tmp_path):
    # 1. Setup production code with an unused function
    users_file = tmp_path / "users.py"
    users_file.write_text(
        "def delete_user():\n    pass\n",
        encoding="utf-8",
    )
    # 2. Setup test file that references delete_user
    test_file = tmp_path / "test_users.py"
    test_file.write_text(
        "from users import delete_user\n\ndef test_delete_user():\n    delete_user()\n",
        encoding="utf-8",
    )
    # 3. Register repository and investigation in PostgreSQL
    repo = Repository(
        name="test-evidence-db-repo",
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
    # 4. Run the investigation pipeline (Static -> Git -> Runtime -> Test -> DB)
    completed_inv = run_investigation(db_session, investigation.id)
    assert completed_inv.status == "completed"
    assert "Test" in completed_inv.summary
    # 5. Fetch results via API service layer
    results = get_investigation_results(db_session, investigation.id)
    assert results is not None
    assert results.candidate_count == 1
    candidate = results.candidates[0]
    assert candidate.symbol == "users.py:delete_user"
    assert "TEST-ONLY ZOMBIE" in candidate.reason
    # Verify both definition and test evidence are present in response
    kinds = [ev.kind for ev in candidate.evidence]
    assert "definition" in kinds
    assert "test" in kinds
    # 6. Directly query the PostgreSQL database to confirm test evidence persisted
    db_evidence_records = (
        db_session.query(Evidence)
        .filter(Evidence.candidate_id == candidate.id)
        .all()
    )
    db_kinds = {e.kind for e in db_evidence_records}
    assert "test" in db_kinds
    test_record = next(e for e in db_evidence_records if e.kind == "test")
    assert test_record.file_path == "test_users.py"
    assert test_record.line_number == 4
    assert "test_delete_user" in test_record.snippet

def test_investigation_full_four_layer_multi_evidence_lifecycle(db_session, tmp_path):
    # 1. Initialize Git repository
    repo_git = git.Repo.init(tmp_path)
    with repo_git.config_writer() as cfg:
        cfg.set_value("user", "name", "Archaeologist")
        cfg.set_value("user", "email", "archaeologist@example.com")
    # 2. Setup production code with active and dead symbols
    billing_code = (
        "def create_invoice():\n"
        "    return 'Invoice #1'\n\n"
        "def legacy_tax_calculator():\n"
        "    return 0.15\n"
    )
    (tmp_path / "billing.py").write_text(billing_code, encoding="utf-8")
    app_code = (
        "from billing import create_invoice\n\n"
        "def main():\n"
        "    return create_invoice()\n"
    )
    (tmp_path / "app.py").write_text(app_code, encoding="utf-8")
    # 3. Setup test suite with mock patch targeting legacy_tax_calculator
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    test_code = (
        "from unittest.mock import patch\n\n"
        "@patch('billing.legacy_tax_calculator')\n"
        "def test_invoice_generation(mock_tax):\n"
        "    pass\n"
    )
    (tests_dir / "test_billing.py").write_text(test_code, encoding="utf-8")
    # Commit all files to Git (Phase 3 evidence)
    repo_git.index.add(["billing.py", "app.py", "tests/test_billing.py"])
    repo_git.index.commit("feat: initial billing and test suite")
    # 4. Setup runtime traces (Phase 4 evidence: active billing called, legacy tax has 0 hits)
    trace_data = {
        "executed_lines": {
            "billing.py": [1, 2],
            "app.py": [1, 3, 4],
        },
        "call_counts": {
            "billing.py:create_invoice": 15,
            "billing.py:legacy_tax_calculator": 0,
        },
    }
    (tmp_path / "runtime_trace.json").write_text(
        json.dumps(trace_data), encoding="utf-8"
    )
    # 5. Register repository & investigation in PostgreSQL
    repo = Repository(
        name="four-layer-multi-evidence-repo",
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
    # 6. Execute full 4-layer investigation
    completed_inv = run_investigation(db_session, investigation.id)
    assert completed_inv.status == "completed"
    assert "Static, Git, Runtime, Test" in str(completed_inv.summary)
    assert "analysis completed" in str(completed_inv.summary)
    # 7. Fetch results via API service layer
    results = get_investigation_results(db_session, investigation.id)
    assert results is not None
    candidates_by_symbol = {c.symbol: c for c in results.candidates}
    # create_invoice should NOT be a candidate (active static production reference)
    assert "billing.py:create_invoice" not in candidates_by_symbol
    # legacy_tax_calculator is a dead candidate with ALL 4 evidence kinds!
    assert "billing.py:legacy_tax_calculator" in candidates_by_symbol
    cand = candidates_by_symbol["billing.py:legacy_tax_calculator"]
    evidence_kinds = {e.kind for e in cand.evidence}
    assert evidence_kinds == {"definition", "git", "runtime", "test"}
    assert "MOCK CLEANUP REQUIRED" in cand.reason
    # 8. Directly verify PostgreSQL database rows
    persisted_evidence = (
        db_session.query(Evidence)
        .filter(Evidence.candidate_id == cand.id)
        .all()
    )
    persisted_kinds = {e.kind for e in persisted_evidence}
    assert persisted_kinds == {"definition", "git", "runtime", "test"}

def test_investigation_full_five_layer_multi_evidence_lifecycle(db_session, tmp_path):
    """
    Phase 6 Comprehensive Integration Test:
    Verifies that an investigation orchestrates ALL 5 evidence layers:
    1. Static definition (Phase 1)
    2. Git history & blame (Phase 3)
    3. Runtime coverage traces (Phase 4)
    4. Test mock / patch references (Phase 5)
    5. AI semantic archaeology & superseded detection (Phase 6)
    And persists all 5 kinds into PostgreSQL.
    """
    import json
    import git

    # 1. Initialize Git repo
    repo_git = git.Repo.init(tmp_path)
    with repo_git.config_writer() as cfg:
        cfg.set_value("user", "name", "Senior Archaeologist")
        cfg.set_value("user", "email", "archaeologist@codearchaeologist.ai")

    # 2. Setup production code:
    # - legacy_tax_calculator: unreferenced, dead code
    # - smart_tax_calculator: active replacement function
    billing_code = (
        "def smart_tax_calculator(order):\n"
        "    return order.amount * 0.15\n\n"
        "def legacy_tax_calculator():\n"
        "    return 0.15\n"
    )
    (tmp_path / "billing.py").write_text(billing_code, encoding="utf-8")

    app_code = (
        "from billing import smart_tax_calculator\n\n"
        "def process_order(order):\n"
        "    return smart_tax_calculator(order)\n"
    )
    (tmp_path / "app.py").write_text(app_code, encoding="utf-8")

    # 3. Setup test suite referencing legacy_tax_calculator via mock patch
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    test_code = (
        "from unittest.mock import patch\n\n"
        "@patch('billing.legacy_tax_calculator')\n"
        "def test_order_taxes(mock_tax):\n"
        "    pass\n"
    )
    (tests_dir / "test_billing.py").write_text(test_code, encoding="utf-8")

    repo_git.index.add(["billing.py", "app.py", "tests/test_billing.py"])
    repo_git.index.commit("feat: implement billing and obsolete test patch")

    # 4. Setup runtime traces (smart_tax_calculator called 50 times, legacy has 0 hits)
    trace_data = {
        "executed_lines": {
            "billing.py": [1, 2],
            "app.py": [1, 3, 4],
        },
        "call_counts": {
            "billing.py:smart_tax_calculator": 50,
            "billing.py:legacy_tax_calculator": 0,
        },
    }
    (tmp_path / "runtime_trace.json").write_text(
        json.dumps(trace_data), encoding="utf-8"
    )

    # 5. Register in PostgreSQL
    repo = Repository(
        name="five-layer-multi-evidence-repo",
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

    # 6. Execute 5-layer investigation pipeline
    completed_inv = run_investigation(db_session, investigation.id)
    assert completed_inv.status == "completed"
    assert "Static, Git, Runtime, Test & Semantic analysis completed" in completed_inv.summary

    # 7. Fetch results via API service layer
    results = get_investigation_results(db_session, investigation.id)
    assert results is not None
    candidates_by_symbol = {c.symbol: c for c in results.candidates}

    # smart_tax_calculator is active production code - must NOT be flagged
    assert "billing.py:smart_tax_calculator" not in candidates_by_symbol

    # legacy_tax_calculator must have ALL 5 evidence kinds
    assert "billing.py:legacy_tax_calculator" in candidates_by_symbol
    candidate = candidates_by_symbol["billing.py:legacy_tax_calculator"]

    evidence_kinds = {e.kind for e in candidate.evidence}
    assert evidence_kinds == {"definition", "git", "runtime", "test", "semantic"}
    assert "SUPERSEDED" in candidate.reason
    assert "smart_tax_calculator" in candidate.reason

    # 8. Directly verify PostgreSQL database rows
    persisted_evidence = (
        db_session.query(Evidence)
        .filter(Evidence.candidate_id == candidate.id)
        .all()
    )
    persisted_kinds = {e.kind for e in persisted_evidence}
    assert persisted_kinds == {"definition", "git", "runtime", "test", "semantic"}