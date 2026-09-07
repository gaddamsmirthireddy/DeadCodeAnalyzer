from pathlib import Path

from app.analyzers.runtime.traces import RuntimeTraceData, load_runtime_trace
from app.analyzers.static.analyzer import CandidateResult, EvidenceResult


def analyze_runtime(
    repo_path: Path | str,
    candidates: list[CandidateResult],
    trace_data: RuntimeTraceData | None = None,
) -> list[CandidateResult]:
    """
    Enrich dead-code candidates with runtime trace evidence.
    - If code was never executed in an active file -> boosts confidence (+0.15, zombie code).
    - If code was observed executing -> drops confidence to 0.05 (dynamic entry point protection).
    """
    repo_path = Path(repo_path)
    if trace_data is None:
        trace_data = load_runtime_trace(repo_path)

    if trace_data is None:
        return candidates

    enriched_candidates: list[CandidateResult] = []

    for candidate in candidates:
        def_evidence = next(
            (ev for ev in candidate.evidence if ev.kind == "definition"),
            None,
        )

        if def_evidence is None:
            enriched_candidates.append(candidate)
            continue

        cand_file_posix = Path(def_evidence.file_path).as_posix()

        # Check call counts directly
        call_hits = _lookup_call_count(candidate.symbol, cand_file_posix, trace_data.call_counts)

        # Check executed lines in matching file
        file_executed_lines = _lookup_file_lines(cand_file_posix, trace_data.executed_lines)

        # If file was not traced at all, no runtime evidence can be concluded
        if call_hits is None and file_executed_lines is None:
            enriched_candidates.append(candidate)
            continue

        is_executed = False
        hit_count = 0

        if call_hits is not None:
            is_executed = call_hits > 0
            hit_count = call_hits
        elif file_executed_lines is not None:
            is_executed = def_evidence.line_number in file_executed_lines
            hit_count = 1 if is_executed else 0

        if is_executed:
            # Active code: protected against false-positive deletion
            snippet = (
                f"Observed active execution during runtime trace (source: '{trace_data.source}', "
                f"{hit_count} recorded hit(s)). Dynamic or reflection entry point detected."
            )
            runtime_evidence = EvidenceResult(
                file_path=def_evidence.file_path,
                line_number=def_evidence.line_number,
                snippet=snippet,
                kind="runtime",
            )
            enriched_candidates.append(
                CandidateResult(
                    symbol=candidate.symbol,
                    reason=(
                        f"{candidate.reason} [RUNTIME WARNING: Code was executed during runtime trace!]"
                    ),
                    confidence=0.05,
                    evidence=[*candidate.evidence, runtime_evidence],
                )
            )
        else:
            # Zombie code: active file, but candidate lines were never invoked
            snippet = (
                f"0 executions observed during runtime trace (source: '{trace_data.source}'). "
                f"File '{cand_file_posix}' was executed, but symbol definition at line "
                f"{def_evidence.line_number} was never entered."
            )
            runtime_evidence = EvidenceResult(
                file_path=def_evidence.file_path,
                line_number=def_evidence.line_number,
                snippet=snippet,
                kind="runtime",
            )
            boosted_confidence = round(
                min(0.98, candidate.confidence + 0.15),
                2,
            )
            enriched_candidates.append(
                CandidateResult(
                    symbol=candidate.symbol,
                    reason=candidate.reason,
                    confidence=boosted_confidence,
                    evidence=[*candidate.evidence, runtime_evidence],
                )
            )

    return enriched_candidates


def _lookup_call_count(
    symbol_identity: str,
    file_posix: str,
    call_counts: dict[str, int],
) -> int | None:
    if symbol_identity in call_counts:
        return call_counts[symbol_identity]

    symbol_name = symbol_identity.split(":")[-1]
    if symbol_name in call_counts:
        return call_counts[symbol_name]

    file_symbol = f"{file_posix}:{symbol_name}"
    if file_symbol in call_counts:
        return call_counts[file_symbol]

    return None


def _lookup_file_lines(
    file_posix: str,
    executed_lines: dict[str, set[int]],
) -> set[int] | None:
    if file_posix in executed_lines:
        return executed_lines[file_posix]

    for raw_path, lines in executed_lines.items():
        if raw_path.endswith(file_posix) or file_posix.endswith(raw_path):
            return lines

    return None
