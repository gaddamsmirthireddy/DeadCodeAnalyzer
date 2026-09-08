from dataclasses import dataclass
from pathlib import Path

from app.analyzers.static.parser import parse_repository
from app.analyzers.static.symbols import extract_symbols
from app.analyzers.test.scanner import is_test_file


@dataclass(frozen=True)
class CodeChunk:
    """Represents a standalone searchable unit of code (function or class)."""
    symbol_name: str
    file_path: str
    line_number: int
    end_line_number: int
    kind: str
    code: str

    @property
    def qualified_id(self) -> str:
        return f"{self.file_path}:{self.symbol_name}"

    @property
    def searchable_text(self) -> str:
        """Formatted text used for vector embeddings and similarity search."""
        return (
            f"Symbol: {self.symbol_name}\n"
            f"File: {self.file_path} (lines {self.line_number}-{self.end_line_number})\n"
            f"Kind: {self.kind}\n"
            f"Code:\n{self.code}"
        )


def extract_code_chunks(
    repo_path: Path | str,
    include_tests: bool = False,
) -> list[CodeChunk]:
    """
    Extract code chunks for all function and class definitions in the repository.

    By default, test files are excluded so that search targets active production code.
    """
    repo_path = Path(repo_path)
    parsed_files = parse_repository(repo_path)
    chunks: list[CodeChunk] = []

    for parsed_file in parsed_files:
        if not include_tests and is_test_file(parsed_file.path, repo_path):
            continue

        relative_file = str(parsed_file.path.relative_to(repo_path))
        symbols = extract_symbols(parsed_file)
        lines = parsed_file.source.splitlines()

        for symbol in symbols:
            # Slice the exact code lines for this function/class
            start = max(0, symbol.line_number - 1)
            end = min(len(lines), symbol.end_line_number)
            code_snippet = "\n".join(lines[start:end])

            chunks.append(
                CodeChunk(
                    symbol_name=symbol.name,
                    file_path=relative_file,
                    line_number=symbol.line_number,
                    end_line_number=symbol.end_line_number,
                    kind=symbol.kind,
                    code=code_snippet,
                )
            )

    return chunks
