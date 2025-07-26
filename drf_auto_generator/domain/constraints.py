"""
Constraint analysis domain logic for DRF Auto Generator.

This module contains the core business logic for analyzing and processing
database constraints for Django model generation.
"""

from dataclasses import dataclass
from typing import List, Dict, Set, Optional, Any
from enum import Enum

from drf_auto_generator.domain.models import TableInfo, ConstraintInfo


class ConstraintType(Enum):
    """Types of database constraints."""

    PRIMARY_KEY = "primary_key"
    FOREIGN_KEY = "foreign_key"
    UNIQUE = "unique"
    CHECK = "check"
    INDEX = "index"
    EXCLUSION = "exclusion"
    TRIGGER = "trigger"


@dataclass
class IndexInfo:
    """Information about a database index."""

    name: str
    columns: List[str]
    is_unique: bool = False
    is_partial: bool = False
    condition: Optional[str] = None
    method: Optional[str] = None  # btree, hash, gin, gist, etc.

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'name': self.name,
            'columns': self.columns,
            'is_unique': self.is_unique,
            'is_partial': self.is_partial,
            'condition': self.condition,
            'method': self.method
        }


@dataclass
class UniqueConstraint:
    """Information about a unique constraint."""

    name: str
    columns: List[str]
    condition: Optional[str] = None
    deferrable: bool = False
    initially_deferred: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'name': self.name,
            'columns': self.columns,
            'condition': self.condition,
            'deferrable': self.deferrable,
            'initially_deferred': self.initially_deferred
        }


class ConstraintAnalyzer:
    """
    Analyzes database constraints and converts them to Django model constraints.

    This class encapsulates the logic for detecting and processing various
    types of database constraints for Django model generation.
    """

    def __init__(self):
        """Initialize constraint analyzer."""
        self.analyzed_tables: Set[str] = set()
        self.constraint_cache: Dict[str, List[ConstraintInfo]] = {}

    def analyze_table_constraints(self, table: TableInfo) -> List[ConstraintInfo]:
        """
        Analyze constraints for a single table.

        Args:
            table: Table to analyze

        Returns:
            List of constraint information
        """
        if table.name in self.constraint_cache:
            return self.constraint_cache[table.name]

        constraints = []

        # Analyze primary key constraints
        pk_constraints = self._analyze_primary_key_constraints(table)
        constraints.extend(pk_constraints)

        # Analyze unique constraints
        unique_constraints = self._analyze_unique_constraints(table)
        constraints.extend(unique_constraints)

        # Analyze foreign key constraints
        fk_constraints = self._analyze_foreign_key_constraints(table)
        constraints.extend(fk_constraints)

        # Analyze check constraints
        check_constraints = self._analyze_check_constraints(table)
        constraints.extend(check_constraints)

        # Analyze indexes
        index_constraints = self._analyze_indexes(table)
        constraints.extend(index_constraints)

        # Cache results
        self.constraint_cache[table.name] = constraints
        self.analyzed_tables.add(table.name)

        return constraints

    def _analyze_primary_key_constraints(self, table: TableInfo) -> List[ConstraintInfo]:
        """Analyze primary key constraints."""
        constraints = []

        if table.has_primary_key:
            constraint = ConstraintInfo(
                name=f"{table.name}_pkey",
                constraint_type="primary_key",
                columns=table.primary_key_columns
            )
            constraints.append(constraint)

        return constraints

    def _analyze_unique_constraints(self, table: TableInfo) -> List[ConstraintInfo]:
        """Analyze unique constraints."""
        constraints = []

        # Single column unique constraints
        for column in table.columns:
            if column.is_unique and not column.is_pk:
                constraint = ConstraintInfo(
                    name=f"{table.name}_{column.name}_unique",
                    constraint_type="unique",
                    columns=[column.name]
                )
                constraints.append(constraint)

        # Multi-column unique constraints from raw constraints
        for constraint_name, constraint_data in table.raw_constraints.items():
            if constraint_data.get('unique') and len(constraint_data.get('columns', [])) > 1:
                constraint = ConstraintInfo(
                    name=constraint_name,
                    constraint_type="unique",
                    columns=constraint_data['columns']
                )
                constraints.append(constraint)

        return constraints

    def _analyze_foreign_key_constraints(self, table: TableInfo) -> List[ConstraintInfo]:
        """Analyze foreign key constraints."""
        constraints = []

        for column in table.columns:
            if column.is_foreign_key and column.foreign_key_to:
                target_table, target_column = column.foreign_key_to
                constraint = ConstraintInfo(
                    name=f"{table.name}_{column.name}_fkey",
                    constraint_type="foreign_key",
                    columns=[column.name],
                    definition=f"FOREIGN KEY ({column.name}) REFERENCES {target_table}({target_column})"
                )
                constraints.append(constraint)

        return constraints

    def _analyze_check_constraints(self, table: TableInfo) -> List[ConstraintInfo]:
        """Analyze check constraints."""
        constraints = []

        # Check constraints from raw constraints
        for constraint_name, constraint_data in table.raw_constraints.items():
            if constraint_data.get('check'):
                constraint = ConstraintInfo(
                    name=constraint_name,
                    constraint_type="check",
                    columns=constraint_data.get('columns', []),
                    definition=constraint_data.get('definition', '')
                )
                constraints.append(constraint)

        return constraints

    def _analyze_indexes(self, table: TableInfo) -> List[ConstraintInfo]:
        """Analyze indexes."""
        constraints = []

        # Convert meta_indexes to constraint info
        for index_data in table.meta_indexes:
            constraint = ConstraintInfo(
                name=index_data.get('name', f"{table.name}_idx"),
                constraint_type="index",
                columns=index_data.get('fields', []),
                is_unique_index=index_data.get('unique', False),
                definition=index_data.get('condition', '')
            )
            constraints.append(constraint)

        return constraints

    def generate_django_constraints(self, table: TableInfo) -> List[Dict[str, Any]]:
        """
        Generate Django model Meta constraints from analyzed constraints.

        Args:
            table: Table information

        Returns:
            List of Django constraint definitions
        """
        constraints = self.analyze_table_constraints(table)
        django_constraints = []

        for constraint in constraints:
            django_constraint = self._convert_to_django_constraint(constraint)
            if django_constraint:
                django_constraints.append(django_constraint)

        return django_constraints

    def _convert_to_django_constraint(self, constraint: ConstraintInfo) -> Optional[Dict[str, Any]]:
        """Convert constraint to Django constraint definition."""
        if constraint.constraint_type == "unique" and len(constraint.columns) > 1:
            return {
                'type': 'UniqueConstraint',
                'fields': constraint.columns,
                'name': constraint.name
            }

        elif constraint.constraint_type == "check" and constraint.definition:
            return {
                'type': 'CheckConstraint',
                'check': constraint.definition,
                'name': constraint.name
            }

        # Primary key and foreign key constraints are handled by field definitions
        # Single column unique constraints are handled by field options
        return None

    def get_table_indexes(self, table: TableInfo) -> List[IndexInfo]:
        """
        Get index information for a table.

        Args:
            table: Table information

        Returns:
            List of index information
        """
        indexes = []

        # Convert meta_indexes to IndexInfo objects
        for index_data in table.meta_indexes:
            index = IndexInfo(
                name=index_data.get('name', f"{table.name}_idx"),
                columns=index_data.get('fields', []),
                is_unique=index_data.get('unique', False),
                is_partial=bool(index_data.get('condition')),
                condition=index_data.get('condition'),
                method=index_data.get('method')
            )
            indexes.append(index)

        return indexes

    def get_unique_constraints(self, table: TableInfo) -> List[UniqueConstraint]:
        """
        Get unique constraint information for a table.

        Args:
            table: Table information

        Returns:
            List of unique constraint information
        """
        unique_constraints = []

        # Analyze constraints to find unique constraints
        constraints = self.analyze_table_constraints(table)

        for constraint in constraints:
            if constraint.constraint_type == "unique":
                unique_constraint = UniqueConstraint(
                    name=constraint.name,
                    columns=constraint.columns,
                    deferrable=constraint.is_deferrable,
                    initially_deferred=constraint.initially_deferred
                )
                unique_constraints.append(unique_constraint)

        return unique_constraints

    def optimize_constraints(self, constraints: List[ConstraintInfo]) -> List[ConstraintInfo]:
        """
        Optimize constraint definitions by removing redundant constraints.

        Args:
            constraints: List of constraints to optimize

        Returns:
            Optimized list of constraints
        """
        optimized = []
        seen_constraints = set()

        for constraint in constraints:
            # Create a key for deduplication
            key = (
                constraint.constraint_type,
                tuple(sorted(constraint.columns)),
                constraint.definition
            )

            if key not in seen_constraints:
                seen_constraints.add(key)
                optimized.append(constraint)

        return optimized
