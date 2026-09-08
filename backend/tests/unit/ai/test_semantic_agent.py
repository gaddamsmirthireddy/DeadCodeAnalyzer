from pathlib import Path

from app.ai.agents.semantic_agent import analyze_semantics
from app.analyzers.static.analyzer import CandidateResult, EvidenceResult
from app.retrieval.chunker import extract_code_chunks
from app.retrieval.retriever import find_superseded_replacements


class TestSupersededDetection:
    """Tests for identifying active modern replacement functions using RAG retrieval."""

    def test_detects_superseded_replacement_function(self, tmp_path):
        billing_file = tmp_path / "billing.py"
        billing_file.write_text(
            "def legacy_tax_calculator():\n"
            "    return 0.15\n\n"
            "def smart_tax_calculator(order):\n"
            "    return order.amount * 0.15\n",
            encoding="utf-8",
        )

        chunks = extract_code_chunks(tmp_path)
        assert len(chunks) == 2

        matches = find_superseded_replacements(
            candidate_symbol="billing.py:legacy_tax_calculator",
            candidate_code="def legacy_tax_calculator(): return 0.15",
            code_chunks=chunks,
            threshold=0.40,
        )

        assert len(matches) == 1
        assert matches[0].symbol_name == "smart_tax_calculator"
        assert matches[0].similarity >= 0.40

    def test_ignores_unrelated_active_functions(self, tmp_path):
        billing_file = tmp_path / "billing.py"
        billing_file.write_text(
            "def legacy_tax_calculator():\n"
            "    return 0.15\n\n"
            "def send_email_notification():\n"
            "    return 'Email sent'\n",
            encoding="utf-8",
        )

        chunks = extract_code_chunks(tmp_path)
        matches = find_superseded_replacements(
            candidate_symbol="billing.py:legacy_tax_calculator",
            candidate_code="def legacy_tax_calculator(): return 0.15",
            code_chunks=chunks,
            threshold=0.50,
        )

        # Unrelated notification function should not match as a replacement for tax calculator
        assert len(matches) == 0


class TestSemanticEvidenceGeneration:
    """Tests for generating kind='semantic' evidence and boosting confidence."""

    def test_generates_semantic_evidence_and_boosts_confidence(self, tmp_path):
        billing_file = tmp_path / "billing.py"
        billing_file.write_text(
            "def legacy_tax_calculator():\n"
            "    return 0.15\n\n"
            "def smart_tax_calculator(order):\n"
            "    return order.amount * 0.15\n",
            encoding="utf-8",
        )

        candidate = CandidateResult(
            symbol="billing.py:legacy_tax_calculator",
            reason="Function 'legacy_tax_calculator' has no detected references from production code.",
            confidence=0.70,
            evidence=[
                EvidenceResult(
                    file_path="billing.py",
                    line_number=1,
                    snippet="def legacy_tax_calculator():",
                    kind="definition",
                )
            ],
        )

        enriched = analyze_semantics(tmp_path, [candidate])
        assert len(enriched) == 1
        result = enriched[0]

        # Check evidence contains semantic kind
        evidence_kinds = [e.kind for e in result.evidence]
        assert "definition" in evidence_kinds
        assert "semantic" in evidence_kinds

        # Check confidence boost and superseded tag
        assert result.confidence == 0.80
        assert "SUPERSEDED" in result.reason
        assert "smart_tax_calculator" in result.reason


class TestOfflineGracefulFallback:
    """Tests that the agent runs deterministically without paid external API keys."""

    def test_offline_fallback_produces_valid_archaeological_reasoning(self, tmp_path):
        billing_file = tmp_path / "billing.py"
        billing_file.write_text(
            "def legacy_tax_calculator():\n    return 0.15\n\n"
            "def smart_tax_calculator():\n    return 0.15\n",
            encoding="utf-8",
        )

        candidate = CandidateResult(
            symbol="billing.py:legacy_tax_calculator",
            reason="Function 'legacy_tax_calculator' is unreferenced.",
            confidence=0.70,
            evidence=[
                EvidenceResult(
                    file_path="billing.py",
                    line_number=1,
                    snippet="def legacy_tax_calculator():",
                    kind="definition",
                )
            ],
        )

        enriched = analyze_semantics(tmp_path, [candidate])
        semantic_ev = next(e for e in enriched[0].evidence if e.kind == "semantic")

        assert semantic_ev.snippet is not None
        assert "Inferred purpose:" in semantic_ev.snippet