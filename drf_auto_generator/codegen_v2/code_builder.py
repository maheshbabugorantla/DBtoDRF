"""
CodeBuilder - A clean, Pythonic way to generate Python code with proper indentation.

This replaces the verbose AST-based code generation with a simple, readable approach
that handles Python's indentation sensitivity correctly.

Example usage:
    builder = PythonCodeBuilder()
    builder.line("from django.db import models")
    builder.line()
    with builder.class_("User", bases=["models.Model"]):
        builder.line("name = models.CharField(max_length=255)")
        with builder.class_("Meta"):
            builder.line('db_table = "users"')

    code = builder.build()  # Returns formatted, validated Python code
"""

import ast
from contextlib import contextmanager
from typing import Any, Optional


class PythonCodeBuilder:
    """
    A builder for generating Python code with automatic indentation handling.

    This class solves the indentation problems that make Jinja2 templates
    difficult for Python code generation, while being much simpler than AST.
    """

    INDENT = "    "  # 4 spaces

    def __init__(self):
        self.lines: list[str] = []
        self._indent_level: int = 0

    # --- Core Methods ---

    def line(self, code: str = "") -> "PythonCodeBuilder":
        """
        Add a line of code at the current indentation level.

        Args:
            code: The code to add. Empty string for blank lines.

        Returns:
            self for method chaining
        """
        if code:
            self.lines.append(self.INDENT * self._indent_level + code)
        else:
            self.lines.append("")
        return self

    def lines_from(self, code_lines: list[str]) -> "PythonCodeBuilder":
        """Add multiple lines of code."""
        for code in code_lines:
            self.line(code)
        return self

    def indent(self) -> "PythonCodeBuilder":
        """Increase indentation level."""
        self._indent_level += 1
        return self

    def dedent(self) -> "PythonCodeBuilder":
        """Decrease indentation level."""
        self._indent_level = max(0, self._indent_level - 1)
        return self

    # --- Context Managers for Blocks ---

    @contextmanager
    def block(self, header: str):
        """
        Context manager for indented blocks.

        Usage:
            with builder.block("if x > 0:"):
                builder.line("print('positive')")
        """
        self.line(header)
        self.indent()
        try:
            yield
        finally:
            self.dedent()

    @contextmanager
    def class_(self, name: str, bases: Optional[list[str]] = None, decorators: Optional[list[str]] = None):
        """
        Context manager for class definitions.

        Usage:
            with builder.class_("User", bases=["models.Model"]):
                builder.line("name = models.CharField()")
        """
        # Add decorators
        if decorators:
            for decorator in decorators:
                self.line(f"@{decorator}")

        # Build class header
        if bases:
            bases_str = ", ".join(bases)
            header = f"class {name}({bases_str}):"
        else:
            header = f"class {name}:"

        with self.block(header):
            yield

    @contextmanager
    def function(
        self,
        name: str,
        params: Optional[list[str]] = None,
        returns: Optional[str] = None,
        decorators: Optional[list[str]] = None,
        is_async: bool = False
    ):
        """
        Context manager for function definitions.

        Usage:
            with builder.function("get_name", params=["self"], returns="str"):
                builder.line("return self.name")
        """
        # Add decorators
        if decorators:
            for decorator in decorators:
                self.line(f"@{decorator}")

        # Build function signature
        params_str = ", ".join(params or [])
        prefix = "async def" if is_async else "def"

        if returns:
            header = f"{prefix} {name}({params_str}) -> {returns}:"
        else:
            header = f"{prefix} {name}({params_str}):"

        with self.block(header):
            yield

    @contextmanager
    def method(
        self,
        name: str,
        params: Optional[list[str]] = None,
        returns: Optional[str] = None,
        decorators: Optional[list[str]] = None,
        is_async: bool = False
    ):
        """Context manager for method definitions (automatically adds 'self')."""
        all_params = ["self"] + (params or [])
        with self.function(name, params=all_params, returns=returns, decorators=decorators, is_async=is_async):
            yield

    @contextmanager
    def if_(self, condition: str):
        """Context manager for if blocks."""
        with self.block(f"if {condition}:"):
            yield

    @contextmanager
    def elif_(self, condition: str):
        """Context manager for elif blocks."""
        with self.block(f"elif {condition}:"):
            yield

    @contextmanager
    def else_(self):
        """Context manager for else blocks."""
        with self.block("else:"):
            yield

    @contextmanager
    def for_(self, var: str, iterable: str):
        """Context manager for for loops."""
        with self.block(f"for {var} in {iterable}:"):
            yield

    @contextmanager
    def while_(self, condition: str):
        """Context manager for while loops."""
        with self.block(f"while {condition}:"):
            yield

    @contextmanager
    def try_(self):
        """Context manager for try blocks."""
        with self.block("try:"):
            yield

    @contextmanager
    def except_(self, exception: str = "Exception", as_var: Optional[str] = None):
        """Context manager for except blocks."""
        if as_var:
            header = f"except {exception} as {as_var}:"
        else:
            header = f"except {exception}:"
        with self.block(header):
            yield

    @contextmanager
    def finally_(self):
        """Context manager for finally blocks."""
        with self.block("finally:"):
            yield

    @contextmanager
    def with_(self, expression: str, as_var: Optional[str] = None):
        """Context manager for with blocks."""
        if as_var:
            header = f"with {expression} as {as_var}:"
        else:
            header = f"with {expression}:"
        with self.block(header):
            yield

    # --- Helper Methods ---

    def docstring(self, text: str, multiline: bool = False) -> "PythonCodeBuilder":
        """Add a docstring."""
        if multiline or "\n" in text:
            self.line('"""')
            for doc_line in text.strip().split("\n"):
                self.line(doc_line)
            self.line('"""')
        else:
            self.line(f'"""{text}"""')
        return self

    def comment(self, text: str) -> "PythonCodeBuilder":
        """Add a comment."""
        self.line(f"# {text}")
        return self

    def import_(self, module: str, names: Optional[list[str]] = None) -> "PythonCodeBuilder":
        """
        Add an import statement.

        Usage:
            builder.import_("django.db", ["models"])  # from django.db import models
            builder.import_("os")  # import os
        """
        if names:
            names_str = ", ".join(names)
            self.line(f"from {module} import {names_str}")
        else:
            self.line(f"import {module}")
        return self

    def assign(self, target: str, value: str) -> "PythonCodeBuilder":
        """Add an assignment statement."""
        self.line(f"{target} = {value}")
        return self

    def return_(self, value: str) -> "PythonCodeBuilder":
        """Add a return statement."""
        self.line(f"return {value}")
        return self

    def pass_(self) -> "PythonCodeBuilder":
        """Add a pass statement."""
        self.line("pass")
        return self

    # --- Output Methods ---

    def build(self, validate: bool = True, format_code: bool = True) -> str:
        """
        Build the final Python code string.

        Args:
            validate: Whether to validate the code with ast.parse()
            format_code: Whether to format with Black (if available)

        Returns:
            The generated Python code as a string

        Raises:
            SyntaxError: If validation is enabled and code is invalid
        """
        code = "\n".join(self.lines)

        # Validate syntax
        if validate:
            try:
                ast.parse(code)
            except SyntaxError as e:
                raise SyntaxError(f"Generated code has syntax errors: {e}\n\nCode:\n{code}")

        # Format with Black if available
        if format_code:
            try:
                import black
                code = black.format_str(code, mode=black.Mode())
            except ImportError:
                pass  # Black not available, skip formatting
            except Exception:
                pass  # Formatting failed, return unformatted code

        return code

    def __str__(self) -> str:
        """Get the current code without validation."""
        return "\n".join(self.lines)

    # --- Static Helpers for Value Formatting ---

    @staticmethod
    def repr_value(value: Any) -> str:
        """Convert a Python value to its repr for code generation."""
        if isinstance(value, str):
            return repr(value)
        elif isinstance(value, bool):
            return "True" if value else "False"
        elif value is None:
            return "None"
        elif isinstance(value, (list, tuple)):
            items = ", ".join(PythonCodeBuilder.repr_value(v) for v in value)
            if isinstance(value, tuple):
                return f"({items})" if len(value) != 1 else f"({items},)"
            return f"[{items}]"
        elif isinstance(value, dict):
            items = ", ".join(
                f"{PythonCodeBuilder.repr_value(k)}: {PythonCodeBuilder.repr_value(v)}"
                for k, v in value.items()
            )
            return f"{{{items}}}"
        else:
            return str(value)

    @staticmethod
    def format_kwargs(kwargs: dict[str, Any], skip_none: bool = True) -> str:
        """Format keyword arguments for a function call."""
        items = []
        for key, value in kwargs.items():
            if skip_none and value is None:
                continue
            # Special handling for models.CASCADE, etc.
            if isinstance(value, str) and value.startswith("models."):
                items.append(f"{key}={value}")
            else:
                items.append(f"{key}={PythonCodeBuilder.repr_value(value)}")
        return ", ".join(items)

    @staticmethod
    def format_field_call(field_type: str, *args: str, **kwargs: Any) -> str:
        """
        Format a Django field definition.

        Usage:
            format_field_call("CharField", max_length=255, null=True)
            # Returns: 'models.CharField(max_length=255, null=True)'
        """
        parts = []
        if args:
            parts.extend(args)

        kwargs_str = PythonCodeBuilder.format_kwargs(kwargs)
        if kwargs_str:
            parts.append(kwargs_str)

        args_str = ", ".join(parts)
        return f"models.{field_type}({args_str})"
