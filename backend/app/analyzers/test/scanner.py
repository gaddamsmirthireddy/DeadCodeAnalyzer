from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.analyzers.static.dependencies import (
    Reference,
    extract_imports,
    extract_references,
    resolve_reference_to_symbol,
)

from app.analyzers.static.symbols import Symbol
from app.analyzers.static.parser import ParsedFile, parse_file


TEST_DIRECTORIES = {
    "tests",
    "test",
    "testing",
    "spec",
}


TEST_FILE_NAMES = {
    "conftest.py",
}


@dataclass(frozen=True)
class TestReference:
    name: str
    file_path: Path
    line_number: int
    caller_test_function: str | None
    is_mock_patch: bool


def is_test_file(
    path: Path,
    repository_path: Path | None = None,
) -> bool:
    """
    Determine whether a Python file belongs to the test suite.

    When repository_path is provided, test-directory detection
    is performed relative to the repository root. This prevents
    parent directories such as:

        backend/tests/fixtures/Static_repo

    from causing every file inside the fixture repository to
    be classified as a test file.
    """

    if path.name in TEST_FILE_NAMES:
        return True

    if path.name.startswith("test_") and path.suffix == ".py":
        return True

    if path.name.endswith("_test.py"):
        return True

    # Use paths relative to the repository root when possible.
    # This prevents an outer "tests" directory from affecting
    # repositories stored inside backend/tests/fixtures/.
    path_to_check = path

    if repository_path is not None:
        try:
            path_to_check = path.relative_to(repository_path)
        except ValueError:
            # If the path is not inside the repository,
            # fall back to checking the original path.
            path_to_check = path

    return any(
        directory in TEST_DIRECTORIES
        for directory in path_to_check.parts
    )


def discover_test_files(
    repository_path: Path,
) -> list[Path]:
    """
    Discover Python test files in a repository.
    """

    test_files: list[Path] = []

    for path in sorted(repository_path.rglob("*.py")):

        if is_test_file(path,repository_path):
            test_files.append(path)

    return test_files


def parse_test_files(
    repository_path: Path,
) -> list[ParsedFile]:
    """
    Discover and parse all test files.
    """

    parsed_files: list[ParsedFile] = []

    for path in discover_test_files(repository_path):
        parsed_files.append(parse_file(path))

    return parsed_files

def extract_test_references(
    parsed_file: ParsedFile,
) -> list[TestReference]:
    """
    Extract references to symbols from a test file.

    Import statements are excluded because importing a symbol
    does not mean the test actually uses it.
    """

    references = extract_references(parsed_file)
    imports = extract_imports(parsed_file)

    import_lines = {
        imported.line_number
        for imported in imports
    }

    test_references: list[TestReference] = []

    for reference in references:

        # Ignore references occurring on import statements.
        if reference.line_number in import_lines:
            continue

        caller_test_function = _find_containing_test_function(
            parsed_file.tree.root_node,
            reference.line_number,
        )

        test_references.append(
            TestReference(
                name=reference.name,
                file_path=reference.file_path,
                line_number=reference.line_number,
                caller_test_function=caller_test_function,
                is_mock_patch=False,
            )
        )
    test_references.extend(_extract_mock_patch_references(parsed_file))
    return test_references

def _extract_mock_patch_references(
    parsed_file: ParsedFile,
) -> list[TestReference]:
    """
    Extract @patch('target') and patch.object(...) mock references from a test file AST.
    """
    mock_references: list[TestReference] = []
    root = getattr(parsed_file.tree, "root_node", None)
    if root is None:
        return mock_references

    def visit(node: Any) -> None:
        if node.type == "call":
            func_node = node.child_by_field_name("function")
            func_text = func_node.text.decode("utf-8") if func_node is not None else ""

            # Check if call is a patch (e.g. patch, mock.patch, mocker.patch, patch.object)
            if "patch" in func_text:
                args_node = node.child_by_field_name("arguments")
                if args_node is not None:
                    for child in args_node.children:
                        if child.type == "string":
                            raw_text = child.text.decode("utf-8")
                            target_name = raw_text.strip("'\"")
                            line_number = child.start_point[0] + 1
                            caller_func = _find_containing_test_function(
                                root,
                                line_number,
                            )
                            mock_references.append(
                                TestReference(
                                    name=target_name,
                                    file_path=parsed_file.path,
                                    line_number=line_number,
                                    caller_test_function=caller_func,
                                    is_mock_patch=True,
                                )
                            )

        for child in node.children:
            visit(child)

    visit(root)
    return mock_references

def _find_containing_test_function(
    root_node: Any,
    line_number: int,
) -> str | None:
    """
    Find the test function containing a reference.
    """

    return _find_test_function_recursive(
        node=root_node,
        line_number=line_number,
    )


def _find_test_function_recursive(
    node: Any,
    line_number: int,
) -> str | None:
    """
    Recursively search for the test function containing a line.
    """

    if node.type in {
        "function_definition",
        "async_function_definition",
    }:
        name_node = node.child_by_field_name("name")

        if name_node is not None:
            function_name = name_node.text.decode("utf-8")

            start_line = node.start_point[0] + 1
            end_line = node.end_point[0] + 1

            if (
                start_line <= line_number <= end_line
                and function_name.startswith("test_")
            ):
                return function_name

    for child in node.children:
        result = _find_test_function_recursive(
            node=child,
            line_number=line_number,
        )

        if result is not None:
            return result

    return None

def resolve_test_references(
    parsed_test_file: ParsedFile,
    symbols: list[Symbol],
) -> list[tuple[TestReference, Symbol]]:
    """
    Resolve references found inside a test file to production symbols.
    """

    test_references = extract_test_references(
        parsed_file=parsed_test_file,
    )

    imports = extract_imports(
        parsed_test_file,
    )

    resolved: list[tuple[TestReference, Symbol]] = []

    for test_reference in test_references:

        # Mock patch references often target module.symbol via string directly
        if test_reference.is_mock_patch:
            target = test_reference.name
            matched_symbol = None
            if "." in target:
                mod_part, sym_name = target.rsplit(".", 1)
                mod_name = mod_part.split(".")[-1]
                for s in symbols:
                    if s.name == sym_name and s.file_path.stem == mod_name:
                        matched_symbol = s
                        break

            if matched_symbol is not None:
                resolved.append((test_reference, matched_symbol))
                continue

        reference = Reference(
            name=test_reference.name,
            file_path=test_reference.file_path,
            line_number=test_reference.line_number,
        )

        symbol = resolve_reference_to_symbol(
            reference=reference,
            imports=imports,
            symbols=symbols,
        )

        if symbol is None:
            continue

        resolved.append(
            (
                test_reference,
                symbol,
            )
        )

    return resolved