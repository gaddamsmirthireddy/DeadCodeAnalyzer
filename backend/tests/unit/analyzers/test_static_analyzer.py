from pathlib import Path

from app.analyzers.static.analyzer import analyze_static
from app.analyzers.static.dependencies import (
    extract_imports,
    extract_references,
    resolve_module_reference,
)
from app.analyzers.static.parser import parse_file

FIXTURE_REPOSITORY = (
    Path(__file__).resolve().parent.parent.parent
    / "fixtures"
    / "Static_repo"
)


class TestStaticParserAndImports:
    """Tests for Tree-sitter parsing and import extraction."""

    def test_parses_plain_import_ast(self):
        path = FIXTURE_REPOSITORY / "module_app.py"
        parsed_file = parse_file(path)
        assert parsed_file.tree.root_node is not None

    def test_extracts_from_import(self):
        path = FIXTURE_REPOSITORY / "app.py"
        parsed_file = parse_file(path)
        imports = extract_imports(parsed_file)

        assert len(imports) == 1
        imported = imports[0]
        assert imported.module == "users"
        assert imported.name == "create_user"
        assert imported.alias is None

    def test_extracts_import_alias(self):
        path = FIXTURE_REPOSITORY / "alias_app.py"
        parsed_file = parse_file(path)
        imports = extract_imports(parsed_file)

        assert len(imports) == 1
        imported = imports[0]
        assert imported.module == "users"
        assert imported.name == "create_user"
        assert imported.alias == "create"

    def test_extracts_plain_import(self):
        path = FIXTURE_REPOSITORY / "module_app.py"
        parsed_file = parse_file(path)
        imports = extract_imports(parsed_file)

        assert len(imports) == 1
        imported = imports[0]
        assert imported.module == "users"
        assert imported.name is None
        assert imported.alias is None


class TestDependencyAndReferenceResolution:
    """Tests for resolving imports, aliases, and references back to symbol definitions."""

    def test_extracts_module_reference(self):
        path = FIXTURE_REPOSITORY / "module_app.py"
        parsed_file = parse_file(path)
        references = extract_references(parsed_file)

        ref_names = {r.name for r in references}
        assert "users.create_user" in ref_names

    def test_resolves_module_alias(self):
        path = FIXTURE_REPOSITORY / "alias_module_app.py"
        parsed_file = parse_file(path)
        imports = extract_imports(parsed_file)
        references = extract_references(parsed_file)

        ref = next(r for r in references if r.name == "u.create_user")
        resolved = resolve_module_reference(ref, imports)
        assert resolved == "create_user"

    def test_resolves_reference_to_correct_file(self):
        candidates = analyze_static(FIXTURE_REPOSITORY)
        symbols = {c.symbol for c in candidates}

        # users.py:process is referenced by consumer.py, so it's NOT a candidate
        assert "users.py:process" not in symbols
        # orders.py:process is NOT referenced, so it IS a candidate
        assert "orders.py:process" in symbols


class TestDeadCodeCandidateDetection:
    """Tests for identifying unused functions and classes with unique identity."""

    def test_finds_unused_symbols(self):
        candidates = analyze_static(FIXTURE_REPOSITORY)
        symbols = {c.symbol for c in candidates}

        assert "user.py:delete_user" in symbols
        assert "user.py:User" in symbols
        assert not any(s.endswith(":create_user") for s in symbols)

    def test_creates_unique_symbol_identity(self):
        candidates = analyze_static(FIXTURE_REPOSITORY)
        symbols = {c.symbol for c in candidates}

        assert "orders.py:process" in symbols
        assert "users.py:process" not in symbols

    def test_returns_expected_candidates(self):
        candidates = analyze_static(FIXTURE_REPOSITORY)
        symbols = {c.symbol for c in candidates}

        assert symbols == {
            "alias_app.py:run",
            "alias_module_app.py:run_alias",
            "consumer.py:run",
            "module_app.py:run_module",
            "orders.py:process",
            "user.py:delete_user",
            "user.py:User",
        }


class TestStaticEvidenceGeneration:
    """Tests for definition evidence snippets, line numbers, and reason descriptions."""

    def test_creates_definition_evidence(self):
        candidates = analyze_static(FIXTURE_REPOSITORY)
        cand_map = {c.symbol: c for c in candidates}

        delete_user = cand_map["user.py:delete_user"]
        assert len(delete_user.evidence) == 1

        ev = delete_user.evidence[0]
        assert ev.file_path == "user.py"
        assert ev.line_number == 5
        assert ev.kind == "definition"
        assert "def delete_user():" in ev.snippet

    def test_candidate_contains_reason(self):
        candidates = analyze_static(FIXTURE_REPOSITORY)
        cand_map = {c.symbol: c for c in candidates}

        delete_user = cand_map["user.py:delete_user"]
        assert "delete_user" in delete_user.reason
        assert "no detected references" in delete_user.reason
        assert delete_user.confidence == 0.70
