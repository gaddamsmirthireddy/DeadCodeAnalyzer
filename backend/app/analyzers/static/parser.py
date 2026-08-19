from dataclasses import dataclass
from pathlib import Path

from tree_sitter import Language, Parser
import tree_sitter_python


PYTHON_LANGUAGE = Language(tree_sitter_python.language())


@dataclass(frozen=True)
class ParsedFile:
    path: Path
    source: str
    tree: object


def parse_file(path: Path) -> ParsedFile:
    """Parse a Python source file using Tree-sitter."""
    source = path.read_text(encoding="utf-8")

    parser = Parser(PYTHON_LANGUAGE)
    tree = parser.parse(source.encode("utf-8"))

    return ParsedFile(
        path=path,
        source=source,
        tree=tree,
    )


def parse_repository(repository_path: Path) -> list[ParsedFile]:
    """Parse all Python files in a repository."""
    parsed_files: list[ParsedFile] = []

    for path in sorted(repository_path.rglob("*.py")):
        if _should_skip(path):
            continue

        parsed_files.append(parse_file(path))

    return parsed_files


def _should_skip(path: Path) -> bool:
    """Ignore generated/environment directories."""
    ignored_parts = {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
    }

    return any(part in ignored_parts for part in path.parts)