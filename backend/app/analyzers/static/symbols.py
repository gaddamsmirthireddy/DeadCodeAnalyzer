from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Symbol:
    name: str
    kind: str
    file_path: Path
    line_number: int
    end_line_number: int

    @property
    def qualified_name(self) -> str:
        return f"{self.file_path.stem}.{self.name}"


def extract_symbols(parsed_file: Any) -> list[Symbol]:
    """Extract top-level and nested Python definitions."""
    symbols: list[Symbol] = []

    _walk(
        node=parsed_file.tree.root_node,
        parsed_file=parsed_file,
        symbols=symbols,
    )

    return symbols


def _walk(
    node: Any,
    parsed_file: Any,
    symbols: list[Symbol],
) -> None:
    if node.type in {"function_definition", "async_function_definition"}:
        name_node = node.child_by_field_name("name")

        if name_node is not None:
            symbols.append(
                Symbol(
                    name=name_node.text.decode("utf-8"),
                    kind="function",
                    file_path=parsed_file.path,
                    line_number=node.start_point[0] + 1,
                    end_line_number=node.end_point[0] + 1,
                )
            )

    elif node.type == "class_definition":
        name_node = node.child_by_field_name("name")

        if name_node is not None:
            symbols.append(
                Symbol(
                    name=name_node.text.decode("utf-8"),
                    kind="class",
                    file_path=parsed_file.path,
                    line_number=node.start_point[0] + 1,
                    end_line_number=node.end_point[0] + 1,
                )
            )

    for child in node.children:
        _walk(
            node=child,
            parsed_file=parsed_file,
            symbols=symbols,
        )
