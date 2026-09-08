from dataclasses import dataclass
from pathlib import Path

from app.analyzers.test.scanner import is_test_file

from app.analyzers.static.dependencies import (
    Reference,
    extract_imports,
    extract_references,
    resolve_reference_to_symbol,
)
from app.analyzers.static.parser import parse_repository
from app.analyzers.static.symbols import (
    Symbol,
    extract_symbols,
)


@dataclass(frozen=True)
class EvidenceResult:
    file_path: str
    line_number: int
    snippet: str
    kind: str = "definition"


@dataclass(frozen=True)
class CandidateResult:
    # Unique symbol identity:
    # example: "user.py:delete_user"
    symbol: str

    reason: str
    confidence: float
    evidence: list[EvidenceResult]


def analyze_static(
    repository_path: str | Path,
) -> list[CandidateResult]:
    """
    Find potentially unused Python functions and classes.

    Production references and test references are tracked
    separately.

    A symbol is considered used only when it has a production
    reference. A symbol referenced only by tests remains a
    candidate so that the Test Analyzer can investigate it
    further.
    """

    repository_path = Path(repository_path)

    parsed_files = parse_repository(repository_path)

    all_symbols: list[Symbol] = []
    all_references: list[Reference] = []
    all_imports = []

    # ---------------------------------------------------------
    # Step 1: Extract symbols, references and imports
    # ---------------------------------------------------------

    for parsed_file in parsed_files:

        all_symbols.extend(
            extract_symbols(parsed_file)
        )

        all_references.extend(
            extract_references(parsed_file)
        )

        all_imports.extend(
            extract_imports(parsed_file)
        )

    # ---------------------------------------------------------
    # Step 2: Resolve references to exact symbols
    # ---------------------------------------------------------

    production_referenced_symbols: set[str] = set()
    test_referenced_symbols: set[str] = set()

    for reference in all_references:

        resolved_symbol = resolve_reference_to_symbol(
            reference=reference,
            imports=all_imports,
            symbols=all_symbols,
        )

        if resolved_symbol is None:
            continue

        relative_path = (
            resolved_symbol.file_path.relative_to(
                repository_path
            )
        )

        symbol_identity = (
            f"{relative_path}:{resolved_symbol.name}"
        )

        # -----------------------------------------------------
        # Separate production references from test references
        # -----------------------------------------------------

        if is_test_file(
            reference.file_path,
            repository_path,
        ):
            test_referenced_symbols.add(symbol_identity)
        else:
            production_referenced_symbols.add(symbol_identity)

    # ---------------------------------------------------------
    # Step 3: Find symbols with no production references
    # ---------------------------------------------------------

    candidates: list[CandidateResult] = []

    for symbol in all_symbols:
        if is_test_file(symbol.file_path, repository_path):
            continue

        relative_path = (
            symbol.file_path.relative_to(
                repository_path
            )
        )

        symbol_identity = (
            f"{relative_path}:{symbol.name}"
        )

        # -----------------------------------------------------
        # If production code references this symbol,
        # it is currently considered used.
        # -----------------------------------------------------

        if symbol_identity in production_referenced_symbols:
            continue

        # -----------------------------------------------------
        # Step 4: Build definition evidence
        # -----------------------------------------------------

        evidence = _build_definition_evidence(
            symbol=symbol,
            parsed_files=parsed_files,
            repository_path=repository_path,
        )

        # -----------------------------------------------------
        # Step 5: Build candidate reason
        # -----------------------------------------------------

        reason = (
            f"{symbol.kind.capitalize()} "
            f"'{symbol.name}' in "
            f"'{relative_path}' has no detected references "
            "from production code."
    )

        if symbol_identity in test_referenced_symbols:
            reason += " It is referenced only by tests."

        # -----------------------------------------------------
        # Step 6: Create candidate
        # -----------------------------------------------------

        candidates.append(
            CandidateResult(
                symbol=symbol_identity,
                reason=reason,
                confidence=0.70,
                evidence=[evidence],
            )
        )

    return candidates


def _build_definition_evidence(
    symbol: Symbol,
    parsed_files: list,
    repository_path: Path,
) -> EvidenceResult:
    """
    Build evidence pointing to the symbol definition.
    """

    snippet = _get_definition_snippet(
        symbol=symbol,
        parsed_files=parsed_files,
    )

    relative_path = (
        symbol.file_path.relative_to(
            repository_path
        )
    )

    return EvidenceResult(
        file_path=str(relative_path),
        line_number=symbol.line_number,
        snippet=snippet,
        kind="definition",
    )


def _get_definition_snippet(
    symbol: Symbol,
    parsed_files: list,
) -> str:
    """
    Return a small source-code snippet around the
    symbol definition.
    """

    for parsed_file in parsed_files:

        if parsed_file.path != symbol.file_path:
            continue

        lines = parsed_file.source.splitlines()

        start = max(
            symbol.line_number - 1,
            0,
        )

        # Show up to three lines beginning at the
        # symbol definition.
        end = min(
            symbol.end_line_number,
            start + 3,
        )

        return "\n".join(
            lines[start:end]
        )

    return ""