from pathlib import Path

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage

from app.ai.llm.client import get_llm_client
from app.analyzers.static.analyzer import CandidateResult, EvidenceResult
from app.retrieval.chunker import extract_code_chunks
from app.retrieval.retriever import find_superseded_replacements

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "semantic.txt"


def _load_prompt_template() -> str:
    if PROMPT_PATH.exists():
        return PROMPT_PATH.read_text(encoding="utf-8")
    return (
        "Analyze candidate symbol {symbol}.\n"
        "Definition:\n{definition}\n"
        "Git context:\n{git_context}\n"
        "Replacement context:\n{replacement_context}\n"
    )


def analyze_semantics(
    repo_path: Path | str,
    candidates: list[CandidateResult],
    llm_client: BaseChatModel | None = None,
) -> list[CandidateResult]:
    """
    Enrich dead-code candidates with AI semantic reasoning:
    - Queries vector retriever for active replacement functions (superseded code detection).
    - Prompts the LLM to infer the original purpose and verify deletion safety.
    - Appends EvidenceResult with kind="semantic".
    """
    repo_path = Path(repo_path)
    if not candidates:
        return candidates

    if llm_client is None:
        llm_client = get_llm_client()

    prompt_template = _load_prompt_template()

    # 1. Extract active production code chunks for RAG search
    code_chunks = extract_code_chunks(repo_path, include_tests=False)

    enriched_candidates: list[CandidateResult] = []

    for candidate in candidates:
        # Get definition evidence
        def_evidence = next(
            (ev for ev in candidate.evidence if ev.kind == "definition"),
            None,
        )
        def_snippet = def_evidence.snippet if def_evidence else candidate.symbol
        file_path = def_evidence.file_path if def_evidence else candidate.symbol.split(":")[0]
        line_number = def_evidence.line_number if def_evidence else 1

        # Get git evidence (if available from Phase 3)
        git_evidence = next(
            (ev for ev in candidate.evidence if ev.kind == "git"),
            None,
        )
        git_context = git_evidence.snippet if git_evidence else "No Git history available."

        # 2. RAG Retrieval: Search for active functions that supersede this candidate
        replacements = find_superseded_replacements(
            candidate_symbol=candidate.symbol,
            candidate_code=def_snippet,
            code_chunks=code_chunks,
            top_k=2,
            threshold=0.35,
        )
        # Only invoke AI investigation if potential replacements were found
        if not replacements:
            enriched_candidates.append(candidate)
            continue

        if replacements:
            rep_lines = [
                f"- {m.file_path}:{m.symbol_name} (similarity {m.similarity:.2f}):\n{m.code_snippet}"
                for m in replacements
            ]
            replacement_context = "\n".join(rep_lines)
        else:
            replacement_context = "None detected across active repository files."

        # 3. Formulate LLM prompt
        prompt_content = prompt_template.format(
            symbol=candidate.symbol,
            definition=def_snippet,
            git_context=git_context,
            replacement_context=replacement_context,
        )

        # 4. Invoke LLM
        try:
            response = llm_client.invoke([HumanMessage(content=prompt_content)])
            ai_explanation = str(response.content).strip()
        except Exception as err:
            ai_explanation = f"Semantic reasoning fallback: {err}"

        # 5. Create semantic evidence
        semantic_evidence = EvidenceResult(
            file_path=file_path,
            line_number=line_number,
            snippet=ai_explanation,
            kind="semantic",
        )

        # 6. Adjust reason and confidence based on superseded detection
        reason_parts = [candidate.reason]
        final_confidence = candidate.confidence

        # If a candidate was protected by runtime trace (confidence <= 0.10), preserve dynamic protection
        is_runtime_protected = candidate.confidence <= 0.10

        if replacements and not is_runtime_protected:
            best_match = replacements[0]
            reason_parts.append(
                f"[SUPERSEDED: Likely replaced by '{best_match.file_path}:{best_match.symbol_name}' "
                f"(semantic similarity: {best_match.similarity:.2f})]."
            )
            final_confidence = round(min(0.98, candidate.confidence + 0.10), 2)
        elif not is_runtime_protected:
            reason_parts.append(f"[SEMANTIC ANALYSIS: {ai_explanation}]")

        enriched_candidates.append(
            CandidateResult(
                symbol=candidate.symbol,
                reason=" ".join(reason_parts),
                confidence=final_confidence,
                evidence=[*candidate.evidence, semantic_evidence],
            )
        )

    return enriched_candidates
