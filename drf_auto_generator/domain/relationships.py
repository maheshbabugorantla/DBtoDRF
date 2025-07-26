"""
Relationship analysis domain logic for DRF Auto Generator.

This module contains the core business logic for analyzing and resolving
database relationships for Django model generation.
"""

from typing import List, Dict, Set
from drf_auto_generator.domain.models import TableInfo, RelationshipInfo, RelationshipType


class RelationshipAnalyzer:
    """
    Analyzes database relationships and converts them to Django relationships.

    This class encapsulates the logic for detecting and resolving relationships
    between database tables.
    """

    def __init__(self):
        """Initialize relationship analyzer."""
        self.analyzed_tables: Set[str] = set()
        self.relationship_cache: Dict[str, List[RelationshipInfo]] = {}

    def analyze_relationships(self, tables: List[TableInfo]) -> List[RelationshipInfo]:
        """
        Analyze relationships across all tables.

        Args:
            tables: List of table information

        Returns:
            List of discovered relationships
        """
        relationships = []
        table_map = {table.name: table for table in tables}

        for table in tables:
            table_relationships = self.analyze_table_relationships(table, table_map)
            relationships.extend(table_relationships)

        # Deduplicate and resolve conflicts
        relationships = self._deduplicate_relationships(relationships)

        return relationships

    def analyze_table_relationships(
        self,
        table: TableInfo,
        all_tables: Dict[str, TableInfo]
    ) -> List[RelationshipInfo]:
        """
        Analyze relationships for a single table.

        Args:
            table: Table to analyze
            all_tables: Map of all available tables

        Returns:
            List of relationships originating from this table
        """
        relationships = []

        # Analyze foreign key relationships
        fk_relationships = self._analyze_foreign_keys(table, all_tables)
        relationships.extend(fk_relationships)

        # Analyze many-to-many relationships
        m2m_relationships = self._analyze_many_to_many(table, all_tables)
        relationships.extend(m2m_relationships)

        return relationships

    def _analyze_foreign_keys(
        self,
        table: TableInfo,
        all_tables: Dict[str, TableInfo]
    ) -> List[RelationshipInfo]:
        """Analyze foreign key relationships."""
        relationships = []

        for column in table.columns:
            if column.is_foreign_key and column.foreign_key_to:
                target_table, target_column = column.foreign_key_to

                if target_table in all_tables:
                    # Generate consistent related_name using model_name_field_name_set convention
                    relationship_name = self._generate_relationship_name(column.name)
                    related_name = f"{table.name}_{relationship_name}_set"
                    
                    relationship = RelationshipInfo(
                        name=self._generate_relationship_name(column.name),
                        relationship_type=RelationshipType.MANY_TO_ONE,
                        source_table=table.name,
                        target_table=target_table,
                        source_columns=[column.name],
                        target_columns=[target_column],
                        related_name=related_name
                    )
                    relationships.append(relationship)

        return relationships

    def _analyze_many_to_many(
        self,
        table: TableInfo,
        all_tables: Dict[str, TableInfo]
    ) -> List[RelationshipInfo]:
        """Analyze many-to-many relationships via through tables."""
        relationships = []

        # Check if this table is a many-to-many through table
        if table.is_many_to_many_through_table():
            fk_columns = table.foreign_key_columns

            if len(fk_columns) == 2:
                # Create many-to-many relationships between the two referenced tables
                table1_fk = fk_columns[0]
                table2_fk = fk_columns[1]

                if (table1_fk.foreign_key_to and table2_fk.foreign_key_to):
                    table1_name = table1_fk.foreign_key_to[0]
                    table2_name = table2_fk.foreign_key_to[0]

                    if table1_name in all_tables and table2_name in all_tables:
                        # Create relationship from table1 to table2
                        relationship = RelationshipInfo(
                            name=f"{table2_name}s",
                            relationship_type=RelationshipType.MANY_TO_MANY,
                            source_table=table1_name,
                            target_table=table2_name,
                            source_columns=[table1_fk.name],
                            target_columns=[table2_fk.name],
                            through_table=table.name,
                            through_fields=(table1_fk.name, table2_fk.name),
                            related_name=f"{table1_name}_set"
                        )
                        relationships.append(relationship)

        return relationships

    def _generate_relationship_name(self, column_name: str) -> str:
        """Generate a relationship field name from column name."""
        # Remove common suffixes like '_id'
        if column_name.endswith('_id'):
            return column_name[:-3]
        return column_name

    def _deduplicate_relationships(
        self,
        relationships: List[RelationshipInfo]
    ) -> List[RelationshipInfo]:
        """Remove duplicate relationships."""
        seen = set()
        unique_relationships = []

        for rel in relationships:
            # Create a unique key for the relationship
            key = (
                rel.source_table,
                rel.target_table,
                rel.relationship_type,
                tuple(rel.source_columns),
                tuple(rel.target_columns)
            )

            if key not in seen:
                seen.add(key)
                unique_relationships.append(rel)

        return unique_relationships


class RelationshipResolver:
    """
    Resolves relationship conflicts and optimizes relationship definitions.

    This class handles complex scenarios like circular dependencies,
    self-referential relationships, and relationship naming conflicts.
    """

    def __init__(self):
        """Initialize relationship resolver."""
        pass

    def resolve_relationships(
        self,
        relationships: List[RelationshipInfo],
        tables: List[TableInfo]
    ) -> List[RelationshipInfo]:
        """
        Resolve relationship conflicts and optimize definitions.

        Args:
            relationships: List of discovered relationships
            tables: List of table information

        Returns:
            List of resolved relationships
        """
        resolved = relationships.copy()

        # Resolve naming conflicts
        resolved = self._resolve_naming_conflicts(resolved)

        # Handle self-referential relationships
        resolved = self._handle_self_referential(resolved)

        # Optimize relationship definitions
        resolved = self._optimize_relationships(resolved)

        return resolved

    def _resolve_naming_conflicts(
        self,
        relationships: List[RelationshipInfo]
    ) -> List[RelationshipInfo]:
        """Resolve naming conflicts between relationships."""
        # Group relationships by source table
        by_source = {}
        for rel in relationships:
            if rel.source_table not in by_source:
                by_source[rel.source_table] = []
            by_source[rel.source_table].append(rel)

        # Check for naming conflicts within each table
        for source_table, rels in by_source.items():
            names_used = set()

            for rel in rels:
                original_name = rel.name
                counter = 1

                while rel.name in names_used:
                    rel.name = f"{original_name}_{counter}"
                    counter += 1

                names_used.add(rel.name)

        return relationships

    def _handle_self_referential(
        self,
        relationships: List[RelationshipInfo]
    ) -> List[RelationshipInfo]:
        """Handle self-referential relationships."""
        for rel in relationships:
            if rel.source_table == rel.target_table:
                rel.is_self_referential = True

                # Adjust related_name to avoid conflicts
                if not rel.related_name.endswith('_children'):
                    rel.related_name = f"{rel.name}_children"

        return relationships

    def _optimize_relationships(
        self,
        relationships: List[RelationshipInfo]
    ) -> List[RelationshipInfo]:
        """Optimize relationship definitions."""
        # This is where we could add optimizations like:
        # - Combining multiple foreign keys into single relationships
        # - Detecting and handling polymorphic relationships
        # - Optimizing through table relationships

        return relationships
