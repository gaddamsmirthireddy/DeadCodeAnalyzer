from collections import defaultdict
from pathlib import Path

from app.analyzers.static.analyzer import CandidateResult, EvidenceResult
from app.analyzers.static.parser import parse_repository
from app.analyzers.static.symbols import extract_symbols
from app.analyzers.test.scanner import (
    is_test_file,
    parse_test_files,
    resolve_test_references,
)


def analyze_test(
    repo_path: Path | str,
    candidates: list[CandidateResult],
) -> list[CandidateResult]:
    """
    Enrich dead-code candidates with test archaeology evidence:
    - Case A: Test-Only Zombie Code (called only by tests).
    - Case B: Untested Abandoned Code (0 test references -> +0.10 confidence boost).
    - Case C: Mock / Patch Targets (emits cleanup warnings for @patch).
    """
    repo_path = Path(repo_path)
    if not candidates:
        return candidates

    # 1. Discover and parse all test files
    parsed_test_files = parse_test_files(repo_path)
    if not parsed_test_files:
        return candidates

    # 2. Extract production symbols to resolve test references
    parsed_all_files = parse_repository(repo_path)
    prod_symbols = [
        sym
        for pf in parsed_all_files
        if not is_test_file(pf.path, repo_path)
        for sym in extract_symbols(pf)
    ]

    # 3. Map test references to candidate symbol identities
    test_refs_by_symbol: dict[str, list] = defaultdict(list)
    for test_file in parsed_test_files:
        resolved = resolve_test_references(
            parsed_test_file=test_file,
            symbols=prod_symbols,
        )
        for test_ref, symbol in resolved:
            rel_path = symbol.file_path.relative_to(repo_path)
            symbol_identity = f"{rel_path}:{symbol.name}"
            test_refs_by_symbol[symbol_identity].append(test_ref)

    # 4. Enrich candidates with Test Evidence
    enriched_candidates: list[CandidateResult] = []

    for candidate in candidates:
        test_matches = test_refs_by_symbol.get(candidate.symbol, [])

        # -------------------------------------------------------------
        # Case B: Completely Untested Code (0 test references)
        # -------------------------------------------------------------
        if not test_matches:
            def_evidence = next(
                (ev for ev in candidate.evidence if ev.kind == "definition"),
                None,
            )
            file_path = def_evidence.file_path if def_evidence else candidate.symbol.split(":")[0]
            line_number = def_evidence.line_number if def_evidence else 1

            untested_evidence = EvidenceResult(
                file_path=file_path,
                line_number=line_number,
                snippet=(
                    "No test references or test execution detected across test suite. "
                    "Symbol appears completely untested and abandoned."
                ),
                kind="test",
            )
                        # Preserve dynamic call protection if runtime already marked it active (confidence <= 0.10)
            if candidate.confidence > 0.10:
                boosted_confidence = round(min(0.95, candidate.confidence + 0.10), 2)
            else:
                boosted_confidence = candidate.confidence
            enriched_candidates.append(
                CandidateResult(
                    symbol=candidate.symbol,
                    reason=(
                        f"{candidate.reason} [UNTESTED: 0 test references detected across test suite]."
                    ),
                    confidence=boosted_confidence,
                    evidence=[*candidate.evidence, untested_evidence],
                )
            )
            continue

        # -------------------------------------------------------------
        # Case A (Direct Test Calls) & Case C (Mock / Patch Targets)
        # -------------------------------------------------------------
        direct_calls = [r for r in test_matches if not r.is_mock_patch]
        mock_patches = [r for r in test_matches if r.is_mock_patch]

        test_evidence_items: list[EvidenceResult] = []

        # Case A: Direct Test Calls
        for test_ref in direct_calls:
            rel_test_path = test_ref.file_path.relative_to(repo_path)
            caller = test_ref.caller_test_function or "module-level"
            snippet = (
                f"Referenced in test function '{caller}' at line {test_ref.line_number} "
                f"in '{rel_test_path}'."
            )
            test_evidence_items.append(
                EvidenceResult(
                    file_path=str(rel_test_path),
                    line_number=test_ref.line_number,
                    snippet=snippet,
                    kind="test",
                )
            )

        # Case C: Mock Patches
        for test_ref in mock_patches:
            rel_test_path = test_ref.file_path.relative_to(repo_path)
            snippet = (
                f"Referenced by mock patch in '{rel_test_path}' (line {test_ref.line_number}): "
                f"@patch('{test_ref.name}'). Obsolete mock cleanup required upon code removal."
            )
            test_evidence_items.append(
                EvidenceResult(
                    file_path=str(rel_test_path),
                    line_number=test_ref.line_number,
                    snippet=snippet,
                    kind="test",
                )
            )

        # Update reason
        reason_parts: list[str] = [candidate.reason]
        if direct_calls:
            first_ref = direct_calls[0]
            first_path = first_ref.file_path.relative_to(repo_path)
            first_caller = first_ref.caller_test_function or "module-level"
            reason_parts.append(
                f"[TEST-ONLY ZOMBIE: Symbol has 0 production references; referenced only by test suite ('{first_path}:{first_caller}')]."
            )
        if mock_patches:
            first_mock = mock_patches[0]
            first_mock_path = first_mock.file_path.relative_to(repo_path)
            reason_parts.append(
                f"[MOCK CLEANUP REQUIRED: Targeted by mock patch in '{first_mock_path}']."
            )

        # Test-only zombie code retains high candidate confidence
        final_confidence = round(max(0.70, candidate.confidence), 2)

        enriched_candidates.append(
            CandidateResult(
                symbol=candidate.symbol,
                reason=" ".join(reason_parts),
                confidence=final_confidence,
                evidence=[*candidate.evidence, *test_evidence_items],
            )
        )

    return enriched_candidates