from pathlib import Path

from app.analyzers.git.blame import get_line_blame
from app.analyzers.git.history import get_file_git_history
from app.analyzers.static.analyzer import CandidateResult, EvidenceResult

DEPRECATION_KEYWORDS = (
    "deprecat",
    "unused",
    "dead",
    "legacy",
    "todo remove",
    "supersed",
    "obsolete",
    "cleanup",
    "drop",
)


def analyze_git(
    repo_path: Path | str,
    candidates: list[CandidateResult],
) -> list[CandidateResult]:
    """
    Enrich dead-code candidates with Git archaeology evidence (blame, commit history, age).
    Adjusts candidate confidence based on code age and commit signals.
    """
    repo_path = Path(repo_path)
    enriched_candidates: list[CandidateResult] = []

    for candidate in candidates:
        def_evidence = next(
            (ev for ev in candidate.evidence if ev.kind == "definition"),
            None,
        )

        if def_evidence is None:
            enriched_candidates.append(candidate)
            continue

        blame = get_line_blame(
            repo_path=repo_path,
            relative_file_path=def_evidence.file_path,
            line_number=def_evidence.line_number,
        )

        history = get_file_git_history(
            repo_path=repo_path,
            relative_file_path=def_evidence.file_path,
        )

        if blame is None and history is None:
            enriched_candidates.append(candidate)
            continue

        evidence_parts: list[str] = []

        if blame is not None:
            date_str = blame.committed_date.strftime("%Y-%m-%d")
            evidence_parts.append(
                f"Line {blame.line_number} last modified by {blame.author} "
                f"in commit {blame.commit_hash[:8]} on {date_str}: \"{blame.summary}\"."
            )

        if history is not None:
            evidence_parts.append(
                f"File has {history.commit_count} commit(s) across "
                f"{len(history.authors)} author(s). "
                f"Last touched {history.age_in_days} day(s) ago."
            )

        git_evidence = EvidenceResult(
            file_path=def_evidence.file_path,
            line_number=def_evidence.line_number,
            snippet=" ".join(evidence_parts),
            kind="git",
        )

        # Confidence tuning
        confidence = candidate.confidence

        if history is not None:
            if history.age_in_days >= 365:
                confidence += 0.15
            elif history.age_in_days >= 180:
                confidence += 0.10
            elif history.age_in_days >= 90:
                confidence += 0.05
            elif history.age_in_days <= 7:
                confidence -= 0.15

        # Check commit messages for deprecation keywords
        messages_text = ""
        if blame is not None:
            messages_text += " " + blame.summary.lower()
        if history is not None:
            messages_text += " " + history.last_commit_message.lower()

        if any(kw in messages_text for kw in DEPRECATION_KEYWORDS):
            confidence += 0.10

        adjusted_confidence = round(
            min(0.98, max(0.20, confidence)),
            2,
        )

        enriched_candidates.append(
            CandidateResult(
                symbol=candidate.symbol,
                reason=candidate.reason,
                confidence=adjusted_confidence,
                evidence=[*candidate.evidence, git_evidence],
            )
        )

    return enriched_candidates
