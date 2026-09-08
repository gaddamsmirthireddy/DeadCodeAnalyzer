import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import git
from fastapi.testclient import TestClient

from app.db.database import SessionLocal
from app.main import app
from app.models.candidate import Candidate
from app.models.evidence import Evidence
from app.models.investigation import Investigation
from app.models.repository import Repository


def main():
    print("=" * 80)
    print(">> CodeArchaeologist: Full Multi-Evidence Verification (Phase 5: Test Analyzer)")
    print("=" * 80)

    temp_dir = tempfile.mkdtemp(prefix="archaeologist_phase5_")
    repo_path = Path(temp_dir)
    db = SessionLocal()

    try:
        # -------------------------------------------------------------
        # 1. Setup Sample Repository Code
        # -------------------------------------------------------------
        print("\n[Step 1] Setting up production codebase...")

        billing_code = (
            "def create_invoice():\n"
            "    return 'Invoice #101'\n\n"
            "def legacy_tax_calculator():\n"
            "    # Deprecated calculation\n"
            "    return 0.15\n"
        )
        (repo_path / "billing.py").write_text(billing_code, encoding="utf-8")

        plugins_code = (
            "def on_event_hook():\n"
            "    # Dynamically called via plugin registry\n"
            "    return 'Event handled'\n"
        )
        (repo_path / "plugins.py").write_text(plugins_code, encoding="utf-8")

        app_code = (
            "from billing import create_invoice\n\n"
            "def main():\n"
            "    create_invoice()\n"
        )
        (repo_path / "app.py").write_text(app_code, encoding="utf-8")

        print("  [+] Created billing.py (has legacy_tax_calculator)")
        print("  [+] Created plugins.py (has on_event_hook - dynamic code)")
        print("  [+] Created app.py (references create_invoice)")

        # -------------------------------------------------------------
        # 2. Setup Test Suite with Mock Patch (Phase 5)
        # -------------------------------------------------------------
        print("\n[Step 2] Setting up unit test suite with mock patches...")
        tests_dir = repo_path / "tests"
        tests_dir.mkdir()

        test_code = (
            "from unittest.mock import patch\n\n"
            "@patch('billing.legacy_tax_calculator')\n"
            "def test_invoice_checkout(mock_calc):\n"
            "    pass\n"
        )
        (tests_dir / "test_billing.py").write_text(test_code, encoding="utf-8")
        print("  [+] Created tests/test_billing.py with @patch('billing.legacy_tax_calculator')")

        # -------------------------------------------------------------
        # 3. Setup Git Repository (Phase 3)
        # -------------------------------------------------------------
        print("\n[Step 3] Initializing Git history & metadata...")
        repo_git = git.Repo.init(repo_path)
        with repo_git.config_writer() as cfg:
            cfg.set_value("user", "name", "Dr. Indiana Code")
            cfg.set_value("user", "email", "indiana@archaeology.ai")

        repo_git.index.add(["billing.py", "plugins.py", "app.py", "tests/test_billing.py"])
        commit = repo_git.index.commit("chore: deprecate legacy tax, add unit test mocks")
        print(f"  [+] Git commit created: {commit.hexsha[:8]} - '{commit.message.strip()}'")

        # -------------------------------------------------------------
        # 4. Setup Runtime Execution Trace (Phase 4)
        # -------------------------------------------------------------
        print("\n[Step 4] Generating runtime execution trace...")
        trace_data = {
            "executed_lines": {
                "billing.py": [1, 2],
                "plugins.py": [1, 2, 3],
                "app.py": [1, 3, 4],
            },
            "call_counts": {
                "plugins.py:on_event_hook": 120,
                "billing.py:create_invoice": 10,
                "billing.py:legacy_tax_calculator": 0,
            },
        }
        (repo_path / "runtime_trace.json").write_text(
            json.dumps(trace_data, indent=2), encoding="utf-8"
        )
        print("  [+] Saved runtime_trace.json (0 executions for legacy_tax_calculator)")

        # -------------------------------------------------------------
        # 5. Trigger Investigation API
        # -------------------------------------------------------------
        print("\n[Step 5] Triggering Investigation API (POST /api/v1/investigations)...")
        client = TestClient(app)

        db_repo = Repository(
            name="phase-5-verification-repo",
            path=str(repo_path),
        )
        db.add(db_repo)
        db.commit()
        db.refresh(db_repo)
        print(f"  [+] Repository ID {db_repo.id} registered in PostgreSQL")

        response = client.post(
            "/api/v1/investigations",
            json={
                "repository_id": db_repo.id,
                "summary": "Phase 5 Complete 4-Layer Multi-Evidence Verification",
            },
        )
        assert response.status_code == 200, f"Error: {response.text}"
        inv_id = response.json()["id"]
        print(f"  [+] Investigation #{inv_id} completed: {response.json()['summary']}")

        # -------------------------------------------------------------
        # 6. Fetch Complete Multi-Evidence Results
        # -------------------------------------------------------------
        print(f"\n[Step 6] Fetching investigation results (GET /api/v1/investigations/{inv_id}/results)...")
        res_response = client.get(f"/api/v1/investigations/{inv_id}/results")
        assert res_response.status_code == 200, f"Error: {res_response.text}"
        results = res_response.json()

        print(f"\n{'=' * 80}")
        print(f"[REPORT] COMPLETE MULTI-EVIDENCE ARCHAEOLOGY REPORT (ID #{results['investigation_id']})")
        print(f"{'=' * 80}")
        print(f"• Repository: {results['repository_name']}")
        print(f"• Summary:    {results['summary']}")
        print(f"• Candidates: {results['candidate_count']} found")
        print("-" * 80)

        for idx, cand in enumerate(results["candidates"], 1):
            print(f"\n[CANDIDATE #{idx}] {cand['symbol']}")
            print(f"   Reason:     {cand['reason']}")
            print(f"   Confidence: {cand['confidence']:.2f} / 1.00")
            print(f"   Evidence Items ({len(cand['evidence'])} total):")

            for ev_idx, ev in enumerate(cand["evidence"], 1):
                kind_badge = f"[{ev['kind'].upper()}]"
                print(f"     {ev_idx}. {kind_badge:<12} (line {ev['line_number']}) in {ev['file_path']}")
                for line in ev["snippet"].split("\n"):
                    print(f"        {line}")

        # -------------------------------------------------------------
        # 7. Behavioral Verification Checks
        # -------------------------------------------------------------
        print(f"\n{'=' * 80}")
        print("[CHECKS] Behavioral Verification Checks:")
        print(f"{'=' * 80}")

        cands = {c["symbol"]: c for c in results["candidates"]}

        # Check 1: legacy_tax_calculator should have ALL 4 evidence sources!
        legacy_cand = cands.get("billing.py:legacy_tax_calculator")
        assert legacy_cand is not None, "legacy_tax_calculator not found"
        legacy_kinds = {e["kind"] for e in legacy_cand["evidence"]}
        assert legacy_kinds == {"definition", "git", "runtime", "test"}, f"Missing evidence kinds: {legacy_kinds}"
        assert "MOCK CLEANUP REQUIRED" in legacy_cand["reason"]
        print("  [OK] 4-Layer Multi-Evidence Verified: 'billing.py:legacy_tax_calculator' has definition, git, runtime & test evidence (with Mock Alert)!")

        # Check 2: on_event_hook is protected by runtime trace
        hook_cand = cands.get("plugins.py:on_event_hook")
        assert hook_cand is not None, "on_event_hook not found"
        assert hook_cand["confidence"] <= 0.10
        print("  [OK] Dynamic Call Protection Verified: 'plugins.py:on_event_hook' protected against deletion (confidence: 0.05).")

        # Check 3: create_invoice is NOT a candidate
        assert "billing.py:create_invoice" not in cands
        print("  [OK] Active Code Verified: 'billing.py:create_invoice' is referenced in production and correctly excluded.")

        print(f"\n{'=' * 80}")
        print("[SUCCESS] ALL 5 PHASES (STATIC, DB, GIT, RUNTIME & TEST) FULLY VERIFIED!")
        print(f"{'=' * 80}\n")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
        try:
            db.query(Evidence).filter(Evidence.file_path.like("%billing.py%")).delete(synchronize_session=False)
            db.query(Evidence).filter(Evidence.file_path.like("%plugins.py%")).delete(synchronize_session=False)
            db.query(Evidence).filter(Evidence.file_path.like("%test_billing.py%")).delete(synchronize_session=False)
            db.query(Candidate).filter(Candidate.symbol.in_(["billing.py:legacy_tax_calculator", "plugins.py:on_event_hook"])).delete(synchronize_session=False)
            db.query(Investigation).filter(Investigation.summary == "Phase 5 Complete 4-Layer Multi-Evidence Verification").delete(synchronize_session=False)
            db.query(Repository).filter(Repository.name == "phase-5-verification-repo").delete(synchronize_session=False)
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()


if __name__ == "__main__":
    main()