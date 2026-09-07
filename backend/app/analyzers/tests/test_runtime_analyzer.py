import json
from pathlib import Path

from app.analyzers.runtime.analyzer import analyze_runtime
from app.analyzers.runtime.traces import load_runtime_trace, parse_trace_dict
from app.analyzers.static.analyzer import CandidateResult, EvidenceResult


def test_load_runtime_trace_structured(tmp_path: Path):
    trace_payload = {
        "executed_lines": {
            "services/user.py": [1, 2, 5, 8],
        },
        "call_counts": {
            "services/user.py:create_user": 42,
            "services/user.py:delete_user": 0,
        },
    }
    trace_file = tmp_path / "runtime_trace.json"
    trace_file.write_text(json.dumps(trace_payload), encoding="utf-8")

    trace_data = load_runtime_trace(tmp_path)
    assert trace_data is not None
    assert trace_data.source == "runtime_trace.json"
    assert 5 in trace_data.executed_lines["services/user.py"]
    assert trace_data.call_counts["services/user.py:create_user"] == 42


def test_load_coverage_json_format():
    coverage_payload = {
        "files": {
            "app/orders.py": {
                "executed_lines": [10, 11, 15],
                "missing_lines": [20, 21],
            }
        }
    }
    trace_data = parse_trace_dict(coverage_payload, source="coverage.json")
    assert trace_data.source == "coverage.json"
    assert "app/orders.py" in trace_data.executed_lines
    assert 10 in trace_data.executed_lines["app/orders.py"]
    assert 20 not in trace_data.executed_lines["app/orders.py"]


def test_analyze_runtime_detects_zombie_code(tmp_path: Path):
    # Traced file where line 50 (zombie function) was never hit
    trace_payload = {
        "executed_lines": {
            "utils.py": [1, 2, 3, 4],  # Line 50 is missing!
        },
        "call_counts": {
            "utils.py:zombie_cleaner": 0,
        },
    }
    trace_file = tmp_path / "runtime_trace.json"
    trace_file.write_text(json.dumps(trace_payload), encoding="utf-8")

    candidate = CandidateResult(
        symbol="utils.py:zombie_cleaner",
        reason="Function has no static references.",
        confidence=0.70,
        evidence=[
            EvidenceResult(
                file_path="utils.py",
                line_number=50,
                snippet="def zombie_cleaner(): pass",
                kind="definition",
            )
        ],
    )

    enriched = analyze_runtime(tmp_path, [candidate])
    assert len(enriched) == 1
    result = enriched[0]

    # Confidence boosted due to 0 hits in active file (zombie code confirmed)
    assert result.confidence == 0.85
    assert len(result.evidence) == 2

    runtime_ev = result.evidence[1]
    assert runtime_ev.kind == "runtime"
    assert "0 executions observed" in runtime_ev.snippet
    assert "never entered" in runtime_ev.snippet


def test_analyze_runtime_protects_dynamic_invocations(tmp_path: Path):
    # Symbol has no static references, but WAS executed dynamically at runtime
    trace_payload = {
        "executed_lines": {
            "plugins/hook.py": [1, 2, 10, 11],  # Line 10 was executed!
        },
        "call_counts": {
            "plugins/hook.py:on_startup": 5,
        },
    }
    trace_file = tmp_path / "runtime_trace.json"
    trace_file.write_text(json.dumps(trace_payload), encoding="utf-8")

    candidate = CandidateResult(
        symbol="plugins/hook.py:on_startup",
        reason="Function has no detected static references.",
        confidence=0.70,
        evidence=[
            EvidenceResult(
                file_path="plugins/hook.py",
                line_number=10,
                snippet="def on_startup(): pass",
                kind="definition",
            )
        ],
    )

    enriched = analyze_runtime(tmp_path, [candidate])
    assert len(enriched) == 1
    result = enriched[0]

    # Confidence dropped to protect against false positive deletion
    assert result.confidence <= 0.10
    assert len(result.evidence) == 2

    runtime_ev = result.evidence[1]
    assert runtime_ev.kind == "runtime"
    assert "Observed active execution" in runtime_ev.snippet
    assert "Dynamic or reflection entry point detected" in runtime_ev.snippet
    assert "RUNTIME WARNING" in result.reason


def test_analyze_runtime_graceful_fallback_no_trace(tmp_path: Path):
    candidate = CandidateResult(
        symbol="plain.py:foo",
        reason="No references.",
        confidence=0.70,
        evidence=[
            EvidenceResult(
                file_path="plain.py",
                line_number=1,
                snippet="def foo(): pass",
                kind="definition",
            )
        ],
    )

    enriched = analyze_runtime(tmp_path, [candidate])
    assert len(enriched) == 1
    assert enriched[0].confidence == 0.70
    assert len(enriched[0].evidence) == 1
    assert enriched[0].evidence[0].kind == "definition"
