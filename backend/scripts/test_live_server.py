import json
import os
import sys
import time
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

base_url = "http://127.0.0.1:8000"
repo_path = os.path.abspath("tests/fixtures/Static_repo")

# 1. Register repository
repo_payload = json.dumps({"name": "LiveDemoRepo", "path": repo_path}).encode("utf-8")
req = urllib.request.Request(
    f"{base_url}/api/v1/repositories",
    data=repo_payload,
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(req) as resp:
    repo = json.loads(resp.read().decode("utf-8"))
    print(f"1. Repository Registered: id={repo['id']}, name='{repo['name']}'")

# 2. Trigger Investigation
inv_payload = json.dumps({"repository_id": repo["id"]}).encode("utf-8")
req2 = urllib.request.Request(
    f"{base_url}/api/v1/investigations",
    data=inv_payload,
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(req2) as resp2:
    inv = json.loads(resp2.read().decode("utf-8"))
    inv_id = inv["id"]
    print(f"2. Investigation Created: id={inv_id}, status='{inv['status']}'")

# 3. Poll for background task completion
for _ in range(10):
    time.sleep(1)
    with urllib.request.urlopen(f"{base_url}/api/v1/investigations/{inv_id}") as resp3:
        inv_status = json.loads(resp3.read().decode("utf-8"))
        print(f"   Polling status: {inv_status['status']}")
        if inv_status["status"] in ("completed", "failed"):
            break

# 4. Fetch Results with evidence
with urllib.request.urlopen(f"{base_url}/api/v1/investigations/{inv_id}/results") as resp4:
    results = json.loads(resp4.read().decode("utf-8"))
    print("\n3. Live Investigation Results:")
    print(f"   Status: {results['status']}")
    print(f"   Summary: {results['summary']}")
    print(f"   Candidate Count: {results['candidate_count']}")
    for c in results["candidates"][:4]:
        print(f"   - Candidate: {c['symbol']} (Confidence: {c['confidence']})")
        for ev in c["evidence"]:
            print(f"     * [{ev['kind'].upper()}] line {ev['line_number']}: {ev['snippet']}")
