from dataclasses import dataclass
from pathlib import Path

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

    Every candidate contains evidence pointing to the
    definition of the potentially unused symbol.
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

    referenced_symbols: set[str] = set()

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

        referenced_symbols.add(symbol_identity)

    # ---------------------------------------------------------
    # Step 3: Find unreferenced symbols
    # ---------------------------------------------------------

    candidates: list[CandidateResult] = []

    for symbol in all_symbols:

        relative_path = (
            symbol.file_path.relative_to(
                repository_path
            )
        )

        symbol_identity = (
            f"{relative_path}:{symbol.name}"
        )

        if symbol_identity in referenced_symbols:
            continue

        # -----------------------------------------------------
        # Step 4: Build definition evidence
        # -----------------------------------------------------

        evidence = _build_definition_evidence(
            symbol=symbol,
            parsed_files=parsed_files,
            repository_path=repository_path,
        )

        candidates.append(
            CandidateResult(
                symbol=symbol_identity,

                reason=(
                    f"{symbol.kind.capitalize()} "
                    f"'{symbol.name}' in "
                    f"'{relative_path}' has no detected "
                    "references in the repository."
                ),

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
