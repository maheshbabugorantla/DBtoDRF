import logging
import ast
from typing import List, Optional, Tuple

from inflect import engine as inflect_engine

logger = logging.getLogger(__name__)

_INFLECT_ENGINE_ = inflect_engine()


def pluralize(word: str) -> str:

    if not isinstance(word, str) or not word:
        return "" # Return empty for non-string or empty input

    try:
        plural = _INFLECT_ENGINE_.plural(word)
        # Handle cases where plural returns False or empty string
        if plural:
            return plural
        else:
            # Standard fallback: append 's' (or 'es' if needed - basic 's' for now)
            return word + "s"
    except Exception as e:
        # Log the error and return a simple fallback
        logger.error(f"Inflect pluralization failed for '{word}': {e}. Falling back to adding 's'.")
        return word + "s"


def add_location(node):
    """Add location info to AST nodes"""
    node.lineno = 1
    node.col_offset = 0
    return node


def create_docstring(content: str) -> ast.Expr:
    """Creates an AST node for a docstring."""
    docstring_node = ast.Expr(value=ast.Constant(value=content))
    docstring_node.lineno = 1
    docstring_node.col_offset = 0
    return docstring_node


def create_import(module: str, names: Optional[List[str]] = None) -> ast.Import | ast.ImportFrom:
    """Creates an AST node for an import statement."""
    if names:
        node = ast.ImportFrom(
            module=module,
            names=[ast.alias(name=name, lineno=1, col_offset=0) for name in names],
            level=0
        )
    else:
        node = ast.Import(names=[ast.alias(name=module, lineno=1, col_offset=0)])

    # Set location info
    node.lineno = 1
    node.col_offset = 0
    return node


def create_assign(target: str, value: ast.expr) -> ast.Assign:
    """Creates an AST node for an assignment."""
    node = ast.Assign(
        targets=[ast.Name(id=target, ctx=ast.Store(), lineno=1, col_offset=0)],
        value=value
    )
    node.lineno = 1
    node.col_offset = 0
    return node


def create_call(func_name: str, args: Optional[List[ast.expr]] = None, keywords: Optional[List[ast.keyword]] = None) -> ast.Call:
    """Creates an AST node for a function call."""
    node = ast.Call(
        func=ast.Name(id=func_name, ctx=ast.Load(), lineno=1, col_offset=0),
        args=args or [],
        keywords=keywords or []
    )
    node.lineno = 1
    node.col_offset = 0
    return node


def create_attribute_call(obj_name: str, attr_name: str, args: Optional[List[ast.expr]] = None, keywords: Optional[List[ast.keyword]] = None) -> ast.Call:
    """Creates an AST node for a method call on an object."""
    attr = ast.Attribute(
        value=ast.Name(id=obj_name, ctx=ast.Load(), lineno=1, col_offset=0),
        attr=attr_name,
        ctx=ast.Load()
    )
    attr.lineno = 1
    attr.col_offset = 0

    node = ast.Call(
        func=attr,
        args=args or [],
        keywords=keywords or []
    )
    node.lineno = 1
    node.col_offset = 0
    return node


def create_class_def(name: str, bases: List[str], body: List[ast.stmt], decorator_list: Optional[List[ast.expr]] = None) -> ast.ClassDef:
    """Creates an AST node for a class definition."""
    node = ast.ClassDef(
        name=name,
        bases=[ast.Name(id=base, ctx=ast.Load(), lineno=1, col_offset=0) for base in bases],
        keywords=[],
        body=body,
        decorator_list=decorator_list or []
    )
    node.lineno = 1
    node.col_offset = 0
    return node


def create_meta_class(options: List[Tuple[str, ast.expr]]) -> ast.ClassDef:
    """Creates an AST node for an inner Meta class."""
    return create_class_def(
        name="Meta",
        bases=[],
        body=[create_assign(target=key, value=val) for key, val in options]
    )


def create_list_of_strings(items: List[str]) -> ast.List:
    """Creates an AST List node containing string constants."""
    node = ast.List(
        elts=[create_string_constant(item) for item in items],
        ctx=ast.Load()
    )
    node.lineno = 1
    node.col_offset = 0
    return node


def create_tuple_of_strings(items: List[str]) -> ast.Tuple:
    """Creates an AST Tuple node containing string constants."""
    node = ast.Tuple(
        elts=[create_string_constant(item) for item in items],
        ctx=ast.Load()
    )
    node.lineno = 1
    node.col_offset = 0
    return node


def create_string_constant(value: str, escape_newlines: bool = False) -> ast.Constant:
    """Creates an AST Constant node for a string."""
    if escape_newlines:
        value = value.replace("\n", "\\n")
    node = ast.Constant(value=value)
    node.lineno = 1
    node.col_offset = 0
    return node


def create_boolean_constant(value: bool) -> ast.Constant:
    """Creates an AST Constant node for a boolean."""
    node = ast.Constant(value=value)
    node.lineno = 1
    node.col_offset = 0
    return node

def create_integer_constant(value: int) -> ast.Constant:
    """Creates an AST Constant node for an integer."""
    node = ast.Constant(value=value)
    node.lineno = 1
    node.col_offset = 0
    return node

def create_none_constant() -> ast.Constant:
    """Creates an AST Constant node for None."""
    node = ast.Constant(value=None)
    node.lineno = 1
    node.col_offset = 0
    return node

def create_keyword(arg: str, value: ast.expr) -> ast.keyword:
    """Creates an AST keyword argument."""
    node = ast.keyword(arg=arg, value=value)
    node.lineno = 1
    node.col_offset = 0
    return node
