from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.analyzers.static.symbols import Symbol


@dataclass(frozen=True)
class Reference:
    name: str
    file_path: Path
    line_number: int


@dataclass(frozen=True)
class Import:
    module: str
    name: str | None
    alias: str | None
    file_path: Path
    line_number: int


def extract_references(parsed_file: Any) -> list[Reference]:
    """Extract symbol references from a parsed Python file."""

    references: list[Reference] = []

    _walk_references(
        node=parsed_file.tree.root_node,
        parsed_file=parsed_file,
        references=references,
    )

    return references


def extract_imports(parsed_file: Any) -> list[Import]:
    """Extract Python import statements."""

    imports: list[Import] = []

    _walk_imports(
        node=parsed_file.tree.root_node,
        parsed_file=parsed_file,
        imports=imports,
    )

    return imports


def _walk_references(
    node: Any,
    parsed_file: Any,
    references: list[Reference],
) -> None:

    # Example:
    #
    # users.create_user()
    #
    # becomes:
    #
    # Reference("users.create_user", ...)
    if node.type == "attribute":

        object_node = node.child_by_field_name("object")
        attribute_node = node.child_by_field_name("attribute")

        if object_node is not None and attribute_node is not None:

            object_name = _node_text(object_node)
            attribute_name = _node_text(attribute_node)

            references.append(
                Reference(
                    name=f"{object_name}.{attribute_name}",
                    file_path=parsed_file.path,
                    line_number=node.start_point[0] + 1,
                )
            )

            return

    # Normal reference:
    #
    # create_user()
    if node.type == "identifier":

        if (
            not _is_definition_name(node)
            and not _is_import_name(node)
        ):
            references.append(
                Reference(
                    name=_node_text(node),
                    file_path=parsed_file.path,
                    line_number=node.start_point[0] + 1,
                )
            )

    for child in node.children:
        _walk_references(
            node=child,
            parsed_file=parsed_file,
            references=references,
        )


def _walk_imports(
    node: Any,
    parsed_file: Any,
    imports: list[Import],
) -> None:

    if node.type == "import_from_statement":

        _extract_import_from(
            node=node,
            parsed_file=parsed_file,
            imports=imports,
        )

    elif node.type == "import_statement":

        _extract_import_statement(
            node=node,
            parsed_file=parsed_file,
            imports=imports,
        )

    for child in node.children:
        _walk_imports(
            node=child,
            parsed_file=parsed_file,
            imports=imports,
        )


def _extract_import_from(
    node: Any,
    parsed_file: Any,
    imports: list[Import],
) -> None:

    module_node = node.child_by_field_name("module_name")
    name_node = node.child_by_field_name("name")

    if module_node is None or name_node is None:
        return

    module = _node_text(module_node)

    if name_node.type == "aliased_import":

        imported_name_node = name_node.child_by_field_name("name")
        alias_node = name_node.child_by_field_name("alias")

        if imported_name_node is None:
            return

        imports.append(
            Import(
                module=module,
                name=_node_text(imported_name_node),
                alias=(
                    _node_text(alias_node)
                    if alias_node is not None
                    else None
                ),
                file_path=parsed_file.path,
                line_number=node.start_point[0] + 1,
            )
        )

        return

    imports.append(
        Import(
            module=module,
            name=_node_text(name_node),
            alias=None,
            file_path=parsed_file.path,
            line_number=node.start_point[0] + 1,
        )
    )


def _extract_import_statement(
    node: Any,
    parsed_file: Any,
    imports: list[Import],
) -> None:
    """Extract:

    import users
    import users as u
    """

    name_node = node.child_by_field_name("name")

    if name_node is None:
        return

    if name_node.type == "aliased_import":

        module_node = name_node.child_by_field_name("name")
        alias_node = name_node.child_by_field_name("alias")

        if module_node is None:
            return

        imports.append(
            Import(
                module=_node_text(module_node),
                name=None,
                alias=(
                    _node_text(alias_node)
                    if alias_node is not None
                    else None
                ),
                file_path=parsed_file.path,
                line_number=node.start_point[0] + 1,
            )
        )

        return

    imports.append(
        Import(
            module=_node_text(name_node),
            name=None,
            alias=None,
            file_path=parsed_file.path,
            line_number=node.start_point[0] + 1,
        )
    )


def _node_text(node: Any) -> str:
    return node.text.decode("utf-8")


def _is_definition_name(node: Any) -> bool:
    parent = node.parent

    if parent is None:
        return False

    if parent.type in {
        "function_definition",
        "async_function_definition",
        "class_definition",
    }:
        return parent.child_by_field_name("name") == node

    return False


def _is_import_name(node: Any) -> bool:
    parent = node.parent

    if parent is None:
        return False

    return parent.type in {
        "import_statement",
        "import_from_statement",
        "aliased_import",
    }


def resolve_reference_name(
    reference: Reference,
    imports: list[Import],
) -> str:
    """Resolve imported aliases."""

    for imported in imports:

        # from users import create_user as create
        #
        # create()
        #
        # -> create_user
        if imported.alias == reference.name:

            if imported.name is not None:
                return imported.name

        # from users import create_user
        #
        # create_user()
        if (
            imported.alias is None
            and imported.name == reference.name
        ):
            return imported.name

    return reference.name


def resolve_module_reference(
    reference: Reference,
    imports: list[Import],
) -> str:
    """Resolve:

    import users
    users.create_user()

    OR:

    import users as u
    u.create_user()

    -> create_user
    """

    if "." not in reference.name:
        return reference.name

    module_name, symbol_name = reference.name.split(
        ".",
        1,
    )

    for imported in imports:

        # import users
        if (
            imported.name is None
            and imported.alias is None
            and imported.module == module_name
        ):
            return symbol_name

        # import users as u
        if (
            imported.name is None
            and imported.alias == module_name
        ):
            return symbol_name

    return reference.name


def resolve_reference_to_symbol(
    reference: Reference,
    imports: list[Import],
    symbols: list[Symbol],
) -> Symbol | None:
    """
    Resolve a reference to the exact symbol it refers to.

    Handles:

        from users import process
        process()

    -> users.py:process

    Also handles:

        from users import create_user as create
        create()

    -> users.py:create_user

    And:

        import users
        users.create_user()

    -> users.py:create_user
    """

    # ---------------------------------------------------------
    # Step 1: Resolve aliases / imported names
    # ---------------------------------------------------------

    resolved_name = resolve_reference_name(
        reference=reference,
        imports=imports,
    )

    # ---------------------------------------------------------
    # Step 2: Resolve module-qualified references
    # ---------------------------------------------------------

    resolved_name = resolve_module_reference(
        reference=Reference(
            name=resolved_name,
            file_path=reference.file_path,
            line_number=reference.line_number,
        ),
        imports=imports,
    )

    # ---------------------------------------------------------
    # Step 3: Find the import that caused this reference
    # ---------------------------------------------------------

    matching_import = None

    for imported in imports:

        # from users import process
        if imported.name == resolved_name:
            matching_import = imported
            break

        # from users import process as p
        if imported.alias == reference.name:
            matching_import = imported
            break

    # ---------------------------------------------------------
    # Step 4: If the symbol came from an import,
    # resolve it using the imported module.
    # ---------------------------------------------------------

    if matching_import is not None:

        module_name = matching_import.module.split(".")[-1]

        for symbol in symbols:

            if symbol.name != resolved_name:
                continue

            if symbol.file_path.stem == module_name:
                return symbol

    # ---------------------------------------------------------
    # Step 5: Handle module-qualified imports directly.
    #
    # import users
    # users.process()
    # ---------------------------------------------------------

    if "." in reference.name:

        module_name, symbol_name = reference.name.split(
            ".",
            1,
        )

        for imported in imports:

            imported_module = imported.module.split(".")[-1]

            if (
                imported_module == module_name
                or imported.alias == module_name
            ):

                for symbol in symbols:

                    if (
                        symbol.name == symbol_name
                        and symbol.file_path.stem
                        == imported_module
                    ):
                        return symbol

    # ---------------------------------------------------------
    # Step 6: Local reference.
    #
    # If a function references another function in the
    # same file, prefer that symbol.
    # ---------------------------------------------------------

    for symbol in symbols:

        if symbol.name != resolved_name:
            continue

        if symbol.file_path == reference.file_path:
            return symbol

    # ---------------------------------------------------------
    # Step 7: Only use a globally unique symbol as a fallback.
    # ---------------------------------------------------------

    matches = [
        symbol
        for symbol in symbols
        if symbol.name == resolved_name
    ]

    if len(matches) == 1:
        return matches[0]

    return None