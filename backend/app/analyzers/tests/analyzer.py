from pathlib import Path

from app.analyzers.static.analyzer import analyze_static
from app.analyzers.static.parser import parse_file
from app.analyzers.static.symbols import extract_symbols
from app.analyzers.static.dependencies import (
    extract_imports,
    extract_references,
    resolve_module_reference,
)


FIXTURE_REPOSITORY = (
    Path(__file__).parent
    / "fixtures"
    / "static_repo"
)


def test_show_plain_import_ast():
    path = FIXTURE_REPOSITORY / "module_app.py"

    parsed_file = parse_file(path)

    print("\n=== PLAIN IMPORT AST ===")
    print(parsed_file.tree.root_node)


def test_static_analyzer_extracts_from_import():
    path = FIXTURE_REPOSITORY / "app.py"

    parsed_file = parse_file(path)

    imports = extract_imports(parsed_file)

    assert len(imports) == 1

    imported = imports[0]

    assert imported.module == "users"
    assert imported.name == "create_user"
    assert imported.alias is None


def test_static_analyzer_extracts_import_alias():
    path = FIXTURE_REPOSITORY / "alias_app.py"

    parsed_file = parse_file(path)

    imports = extract_imports(parsed_file)

    assert len(imports) == 1

    imported = imports[0]

    assert imported.module == "users"
    assert imported.name == "create_user"
    assert imported.alias == "create"


def test_static_analyzer_finds_unused_symbols():
    candidates = analyze_static(FIXTURE_REPOSITORY)

    symbols = {
        candidate.symbol
        for candidate in candidates
    }

    assert "user.py:delete_user" in symbols
    assert "user.py:User" in symbols

    assert not any(
    symbol.endswith(":create_user")
    for symbol in symbols
)


def test_static_analyzer_returns_expected_candidates():
    candidates = analyze_static(FIXTURE_REPOSITORY)

    symbols = {
        candidate.symbol
        for candidate in candidates
    }

    assert symbols == {
    "alias_app.py:run",
    "alias_module_app.py:run_alias",
    "consumer.py:run",
    "module_app.py:run_module",
    "orders.py:process",
    "user.py:delete_user",
    "user.py:User",
}


def test_show_static_analysis_results():
    candidates = analyze_static(FIXTURE_REPOSITORY)

    print("\n=== Static Analysis Results ===")

    for candidate in candidates:
        print(f"UNUSED: {candidate.symbol}")
        print(f"  Reason: {candidate.reason}")
        print(f"  Confidence: {candidate.confidence}")


def test_static_analyzer_extracts_module_reference():
    path = FIXTURE_REPOSITORY / "module_app.py"

    parsed_file = parse_file(path)

    references = extract_references(parsed_file)

    names = {
        reference.name
        for reference in references
    }

    assert "users.create_user" in names


def test_static_analyzer_extracts_plain_import():
    path = FIXTURE_REPOSITORY / "module_app.py"

    parsed_file = parse_file(path)

    imports = extract_imports(parsed_file)

    assert len(imports) == 1

    imported = imports[0]

    assert imported.module == "users"
    assert imported.name is None
    assert imported.alias is None


def test_static_analyzer_resolves_module_alias():
    path = FIXTURE_REPOSITORY / "alias_module_app.py"

    parsed_file = parse_file(path)

    references = extract_references(parsed_file)
    imports = extract_imports(parsed_file)

    module_reference = next(
        reference
        for reference in references
        if reference.name == "u.create_user"
    )

    resolved = resolve_module_reference(
        reference=module_reference,
        imports=imports,
    )

    assert resolved == "create_user"


def test_static_analyzer_creates_unique_symbol_identity():
    users_file = parse_file(
        FIXTURE_REPOSITORY / "users.py"
    )

    orders_file = parse_file(
        FIXTURE_REPOSITORY / "orders.py"
    )

    users_symbols = extract_symbols(users_file)
    orders_symbols = extract_symbols(orders_file)

    users_process = next(
        symbol
        for symbol in users_symbols
        if symbol.name == "process"
    )

    orders_process = next(
        symbol
        for symbol in orders_symbols
        if symbol.name == "process"
    )

    assert users_process.qualified_name == "users.process"
    assert orders_process.qualified_name == "orders.process"

    assert (
        users_process.qualified_name
        != orders_process.qualified_name
    )

def test_static_analyzer_resolves_reference_to_correct_file():
    candidates = analyze_static(FIXTURE_REPOSITORY)

    symbols = {
        candidate.symbol
        for candidate in candidates
    }

    # users.process IS used by consumer.py
    assert "users.py:process" not in symbols

    # orders.process is NOT used
    assert "orders.py:process" in symbols

def test_static_analyzer_creates_definition_evidence():
    candidates = analyze_static(FIXTURE_REPOSITORY)

    candidate = next(
        candidate
        for candidate in candidates
        if candidate.symbol == "user.py:delete_user"
    )

    assert len(candidate.evidence) == 1

    evidence = candidate.evidence[0]

    assert evidence.file_path == "user.py"
    assert evidence.line_number == 5
    assert evidence.kind == "definition"

    assert "def delete_user():" in evidence.snippet

def test_static_analyzer_candidate_contains_reason():
    candidates = analyze_static(FIXTURE_REPOSITORY)

    candidate = next(
        candidate
        for candidate in candidates
        if candidate.symbol == "user.py:delete_user"
    )

    assert "delete_user" in candidate.reason
    assert "no detected references" in candidate.reason