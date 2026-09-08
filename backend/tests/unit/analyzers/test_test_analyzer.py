from pathlib import Path

from app.analyzers.static.analyzer import CandidateResult, EvidenceResult
from app.analyzers.static.parser import parse_file
from app.analyzers.static.symbols import extract_symbols
from app.analyzers.test.analyzer import analyze_test
from app.analyzers.test.scanner import (
    discover_test_files,
    extract_test_references,
    is_test_file,
    resolve_test_references,
)


class TestTestFileClassification:
    """Tests for classifying whether a path belongs to the test suite."""

    def test_detects_tests_directory(self):
        path = Path("tests/test_users.py")
        assert is_test_file(path) is True

    def test_detects_test_prefix(self):
        path = Path("test_users.py")
        assert is_test_file(path) is True

    def test_detects_test_suffix(self):
        path = Path("users_test.py")
        assert is_test_file(path) is True

    def test_detects_conftest(self):
        path = Path("conftest.py")
        assert is_test_file(path) is True

    def test_does_not_detect_production_file(self):
        path = Path("app/users.py")
        assert is_test_file(path) is False

    def test_discover_test_files(self, tmp_path):
        (tmp_path / "test_one.py").write_text("def test_one(): pass\n", encoding="utf-8")
        (tmp_path / "app.py").write_text("def main(): pass\n", encoding="utf-8")
        discovered = discover_test_files(tmp_path)
        names = [f.name for f in discovered]
        assert "test_one.py" in names
        assert "app.py" not in names


class TestTestReferenceResolution:
    """Tests for extracting and resolving test calls and imports back to production symbols."""

    def test_resolves_test_reference_to_production_symbol(self, tmp_path):
        users_file = tmp_path / "users.py"
        users_file.write_text("def delete_user():\n    pass\n", encoding="utf-8")

        test_file = tmp_path / "test_users.py"
        test_file.write_text(
            "from users import delete_user\n\ndef test_delete_user():\n    delete_user()\n",
            encoding="utf-8",
        )

        users_parsed = parse_file(users_file)
        test_parsed = parse_file(test_file)
        symbols = extract_symbols(users_parsed)

        resolved = resolve_test_references(
            parsed_test_file=test_parsed,
            symbols=symbols,
        )

        assert len(resolved) == 1
        test_reference, symbol = resolved[0]
        assert test_reference.name == "delete_user"
        assert test_reference.caller_test_function == "test_delete_user"
        assert symbol.name == "delete_user"
        assert symbol.file_path == users_file

    def test_identifies_containing_test_function(self, tmp_path):
        test_file = tmp_path / "test_users.py"
        test_file.write_text(
            "def test_delete_user():\n    delete_user()\n",
            encoding="utf-8",
        )

        parsed_file = parse_file(test_file)
        references = extract_test_references(parsed_file)
        delete_ref = next(r for r in references if r.name == "delete_user")
        assert delete_ref.caller_test_function == "test_delete_user"

    def test_resolves_aliased_test_reference(self, tmp_path):
        users_file = tmp_path / "users.py"
        users_file.write_text("def delete_user():\n    pass\n", encoding="utf-8")

        test_file = tmp_path / "test_users.py"
        test_file.write_text(
            "from users import delete_user as remove_user\n\ndef test_delete_user():\n    remove_user()\n",
            encoding="utf-8",
        )

        users_parsed = parse_file(users_file)
        test_parsed = parse_file(test_file)
        symbols = extract_symbols(users_parsed)

        resolved = resolve_test_references(
            parsed_test_file=test_parsed,
            symbols=symbols,
        )

        assert len(resolved) == 1
        test_reference, symbol = resolved[0]
        assert test_reference.name == "remove_user"
        assert symbol.name == "delete_user"

    def test_resolves_module_test_reference(self, tmp_path):
        users_file = tmp_path / "users.py"
        users_file.write_text("def delete_user():\n    pass\n", encoding="utf-8")

        test_file = tmp_path / "test_users.py"
        test_file.write_text(
            "import users\n\ndef test_delete_user():\n    users.delete_user()\n",
            encoding="utf-8",
        )

        users_parsed = parse_file(users_file)
        test_parsed = parse_file(test_file)
        symbols = extract_symbols(users_parsed)

        resolved = resolve_test_references(
            parsed_test_file=test_parsed,
            symbols=symbols,
        )

        assert len(resolved) == 1
        test_reference, symbol = resolved[0]
        assert test_reference.name == "users.delete_user"
        assert symbol.name == "delete_user"


class TestTestOnlyDeadCode:
    """Case A: Production symbols called only from unit tests."""

    def test_identifies_test_only_zombie_code(self, tmp_path):
        users_file = tmp_path / "users.py"
        users_file.write_text("def delete_user():\n    pass\n", encoding="utf-8")

        test_file = tmp_path / "test_users.py"
        test_file.write_text(
            "from users import delete_user\n\ndef test_delete_user():\n    delete_user()\n",
            encoding="utf-8",
        )

        candidate = CandidateResult(
            symbol="users.py:delete_user",
            reason="Function 'delete_user' has no detected references from production code.",
            confidence=0.70,
            evidence=[
                EvidenceResult(
                    file_path="users.py",
                    line_number=1,
                    snippet="def delete_user():",
                    kind="definition",
                )
            ],
        )

        enriched = analyze_test(tmp_path, [candidate])
        assert len(enriched) == 1
        result = enriched[0]

        assert "TEST-ONLY ZOMBIE" in result.reason
        assert any(ev.kind == "test" for ev in result.evidence)
        assert result.confidence >= 0.70


class TestUntestedDeadCode:
    """Case B: Candidate symbols with 0 test references across the test suite."""

    def test_boosts_confidence_on_completely_untested_code(self, tmp_path):
        orders_file = tmp_path / "orders.py"
        orders_file.write_text("def cancel_order():\n    pass\n", encoding="utf-8")

        # Test suite exists, but never touches orders.py
        test_file = tmp_path / "test_other.py"
        test_file.write_text("def test_dummy():\n    pass\n", encoding="utf-8")

        candidate = CandidateResult(
            symbol="orders.py:cancel_order",
            reason="Function 'cancel_order' has no detected references from production code.",
            confidence=0.70,
            evidence=[
                EvidenceResult(
                    file_path="orders.py",
                    line_number=1,
                    snippet="def cancel_order():",
                    kind="definition",
                )
            ],
        )

        enriched = analyze_test(tmp_path, [candidate])
        assert len(enriched) == 1
        result = enriched[0]

        # Untested code gets +0.10 confidence boost
        assert result.confidence == 0.80
        assert "UNTESTED" in result.reason

        untested_ev = next(ev for ev in result.evidence if ev.kind == "test")
        assert "No test references or test execution detected" in untested_ev.snippet


class TestMockPatchDetection:
    """Case C: Candidates targeted by @patch(...) string references."""

    def test_detects_mock_patch_and_creates_cleanup_warning(self, tmp_path):
        billing_file = tmp_path / "billing.py"
        billing_file.write_text(
            "def legacy_tax_calculator():\n    return 0.15\n",
            encoding="utf-8",
        )

        test_file = tmp_path / "test_checkout.py"
        test_file.write_text(
            "from unittest.mock import patch\n\n"
            "@patch('billing.legacy_tax_calculator')\n"
            "def test_checkout(mock_calc):\n"
            "    pass\n",
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

        enriched = analyze_test(tmp_path, [candidate])
        assert len(enriched) == 1
        result = enriched[0]

        assert "MOCK CLEANUP REQUIRED" in result.reason
        mock_ev = next(ev for ev in result.evidence if ev.kind == "test")
        assert "Obsolete mock cleanup required" in mock_ev.snippet
        assert "@patch('billing.legacy_tax_calculator')" in mock_ev.snippet


class TestTestEvidenceGeneration:
    """Tests for evidence formatting, line numbers, and snippets."""

    def test_evidence_formatting_and_line_numbers(self, tmp_path):
        users_file = tmp_path / "users.py"
        users_file.write_text("def delete_user():\n    pass\n", encoding="utf-8")

        test_file = tmp_path / "test_users.py"
        test_file.write_text(
            "from users import delete_user\n\ndef test_delete_user():\n    delete_user()\n",
            encoding="utf-8",
        )

        candidate = CandidateResult(
            symbol="users.py:delete_user",
            reason="Function 'delete_user' has no detected references.",
            confidence=0.70,
            evidence=[
                EvidenceResult(
                    file_path="users.py",
                    line_number=1,
                    snippet="def delete_user():",
                    kind="definition",
                )
            ],
        )

        enriched = analyze_test(tmp_path, [candidate])
        test_ev = next(ev for ev in enriched[0].evidence if ev.kind == "test")

        assert test_ev.file_path == "test_users.py"
        assert test_ev.line_number == 4
        assert "test_delete_user" in test_ev.snippet