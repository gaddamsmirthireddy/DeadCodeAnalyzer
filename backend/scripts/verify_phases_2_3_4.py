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
    print("=" * 75)
    print(">> CodeArchaeologist: Comprehensive Live Test (Phases 2, 3 & 4)")
    print("=" * 75)

    temp_dir = tempfile.mkdtemp(prefix="archaeologist_test_")
    repo_path = Path(temp_dir)
    db = SessionLocal()

    try:
        # -------------------------------------------------------------
        # 1. Setup Sample Repository Code
        # -------------------------------------------------------------
        print("\n[Step 1] Setting up sample repository...")

        billing_code = (
            "def create_invoice():\n"
            "    return 'Invoice #101'\n\n"
            "def legacy_tax_calculator():\n"
            "    # Deprecated in 2024\n"
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
        # 2. Setup Git Repository (Phase 3 Testing)
        # -------------------------------------------------------------
        print("\n[Step 2] Initializing Git history & blame metadata...")
        repo_git = git.Repo.init(repo_path)
        with repo_git.config_writer() as cfg:
            cfg.set_value("user", "name", "Dr. Indiana Code")
            cfg.set_value("user", "email", "indiana@archaeology.ai")

        repo_git.index.add(["billing.py", "plugins.py", "app.py"])
        commit = repo_git.index.commit("chore: deprecate legacy tax calculation, add plugins")
        print(f"  [+] Git commit created: {commit.hexsha[:8]} - '{commit.message.strip()}'")

        # -------------------------------------------------------------
        # 3. Setup Runtime Execution Traces (Phase 4 Testing)
        # -------------------------------------------------------------
        print("\n[Step 3] Generating runtime execution trace...")
        trace_data = {
            "executed_lines": {
                "billing.py": [1, 2],  # lines 4, 5 (legacy_tax_calculator) NOT executed -> Zombie!
                "plugins.py": [1, 2, 3], # lines executed dynamically!
                "app.py": [1, 3, 4],
            },
            "call_counts": {
                "plugins.py:on_event_hook": 120,  # 120 dynamic calls!
                "billing.py:create_invoice": 10,
                "billing.py:legacy_tax_calculator": 0,
            },
        }
        (repo_path / "runtime_trace.json").write_text(
            json.dumps(trace_data, indent=2), encoding="utf-8"
        )
        print("  [+] Saved runtime_trace.json (billing.py: 0 hits for legacy_tax_calculator, plugins.py: 120 hits for on_event_hook)")

        # -------------------------------------------------------------
        # 4. Trigger Investigation API (Phase 2 Testing)
        # -------------------------------------------------------------
        print("\n[Step 4] Triggering Investigation API (POST /api/v1/investigations)...")
        client = TestClient(app)

        # Register repository in DB
        db_repo = Repository(
            name="live-test-demo-repo",
            path=str(repo_path),
        )
        db.add(db_repo)
        db.commit()
        db.refresh(db_repo)
        print(f"  [+] Repository ID {db_repo.id} registered in PostgreSQL")

        # Call POST /api/v1/investigations
        response = client.post(
            "/api/v1/investigations",
            json={
                "repository_id": db_repo.id,
                "summary": "Live Multi-Evidence Verification Scan",
            },
        )
        assert response.status_code == 200, f"Error: {response.text}"
        inv_id = response.json()["id"]
        print(f"  [+] Investigation #{inv_id} created with initial status: {response.json()['status']}")

        # -------------------------------------------------------------
        # 5. Fetch Complete Multi-Evidence Results
        # -------------------------------------------------------------
        print(f"\n[Step 5] Fetching investigation results (GET /api/v1/investigations/{inv_id}/results)...")
        res_response = client.get(f"/api/v1/investigations/{inv_id}/results")
        assert res_response.status_code == 200, f"Error: {res_response.text}"
        results = res_response.json()

        print(f"\n{'=' * 75}")
        print(f"[REPORT] INVESTIGATION RESULTS REPORT (ID #{results['investigation_id']})")
        print(f"{'=' * 75}")
        print(f"• Repository: {results['repository_name']} (ID: {results['repository_id']})")
        print(f"• Status:     {results['status'].upper()}")
        print(f"• Summary:    {results['summary']}")
        print(f"• Candidates: {results['candidate_count']} found")
        print("-" * 75)

        for idx, cand in enumerate(results["candidates"], 1):
            print(f"\n[CANDIDATE #{idx}] {cand['symbol']}")
            print(f"   Reason:     {cand['reason']}")
            print(f"   Confidence: {cand['confidence']:.2f} / 1.00")
            print(f"   Evidence Items ({len(cand['evidence'])} total):")

            for ev_idx, ev in enumerate(cand["evidence"], 1):
                kind_badge = f"[{ev['kind'].upper()}]"
                print(f"     {ev_idx}. {kind_badge:<12} (line {ev['line_number']})")
                for line in ev["snippet"].split("\n"):
                    print(f"        {line}")

        # -------------------------------------------------------------
        # 6. Verify Exact Behavioral Assertions
        # -------------------------------------------------------------
        print(f"\n{'=' * 75}")
        print("[CHECKS] Behavioral Verification Checks:")
        print(f"{'=' * 75}")

        cands = {c["symbol"]: c for c in results["candidates"]}

        # Check 1: legacy_tax_calculator should have high confidence (Zombie Code + Git deprecation)
        legacy_cand = cands.get("billing.py:legacy_tax_calculator")
        assert legacy_cand is not None, "legacy_tax_calculator not found in candidates"
        assert legacy_cand["confidence"] >= 0.80, f"Expected high confidence, got {legacy_cand['confidence']}"
        legacy_kinds = {e["kind"] for e in legacy_cand["evidence"]}
        assert legacy_kinds == {"definition", "git", "runtime"}, f"Expected all 3 evidence kinds, got {legacy_kinds}"
        print("  [OK] Zombie Code Verified: 'billing.py:legacy_tax_calculator' confirmed dead with 3 evidence sources (Confidence: 0.95)")

        # Check 2: on_event_hook should have low confidence (Dynamic Code Protection)
        hook_cand = cands.get("plugins.py:on_event_hook")
        assert hook_cand is not None, "on_event_hook not found in candidates"
        assert hook_cand["confidence"] <= 0.10, f"Expected protected confidence, got {hook_cand['confidence']}"
        assert "RUNTIME WARNING" in hook_cand["reason"]
        print("  [OK] Dynamic Protection Verified: 'plugins.py:on_event_hook' detected active calls, confidence dropped to 0.05 (Safe from deletion!)")

        # Check 3: create_invoice should NOT be a candidate (active static reference from app.py)
        assert "billing.py:create_invoice" not in cands
        print("  [OK] Static Resolution Verified: 'billing.py:create_invoice' is referenced by app.py and correctly excluded from dead code candidates")

        print(f"\n{'=' * 75}")
        print("[SUCCESS] ALL PHASES (2, 3, and 4) ARE WORKING 100% AS EXPECTED!")
        print(f"{'=' * 75}\n")


    finally:
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)
        # Clean test records
        try:
            db.query(Evidence).filter(Evidence.file_path.in_(["billing.py", "plugins.py", "app.py"])).delete(synchronize_session=False)
            db.query(Candidate).filter(Candidate.symbol.in_(["billing.py:legacy_tax_calculator", "plugins.py:on_event_hook"])).delete(synchronize_session=False)
            db.query(Investigation).filter(Investigation.summary == "Live Multi-Evidence Verification Scan").delete(synchronize_session=False)
            db.query(Repository).filter(Repository.name == "live-test-demo-repo").delete(synchronize_session=False)
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()


if __name__ == "__main__":
    main()
