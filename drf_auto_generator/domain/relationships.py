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

        # Check if this table is a potential M2M through table
        if self._is_many_to_many_through_table(table, all_tables):
            fk_columns = self._get_foreign_key_columns(table)

            if len(fk_columns) == 2:
                table1_fk = fk_columns[0]
                table2_fk = fk_columns[1]

                if (table1_fk.foreign_key_to and table2_fk.foreign_key_to):
                    table1_name = table1_fk.foreign_key_to[0]
                    table2_name = table2_fk.foreign_key_to[0]

                    if table1_name in all_tables and table2_name in all_tables:
                        # Mark this table as M2M through table
                        table.is_m2m_through_table = True

                        # Handle self-referential M2M
                        if table1_name == table2_name:
                            self._create_self_referential_m2m(
                                table, table1_name, table1_fk, table2_fk,
                                all_tables, relationships
                            )
                        else:
                            # Create bidirectional M2M relationships
                            self._create_bidirectional_m2m(
                                table, table1_name, table2_name,
                                table1_fk, table2_fk, all_tables, relationships
                            )

        return relationships

    def _is_many_to_many_through_table(self, table: TableInfo, all_tables: Dict[str, TableInfo]) -> bool:
        """Determine if a table is a M2M through table using sophisticated heuristics."""
        fk_columns = self._get_foreign_key_columns(table)

        # Must have exactly 2 FKs
        if len(fk_columns) != 2:
            return False

        # Get PK fields
        pk_fields = [col for col in table.columns if col.is_pk]

        # Check if PK consists of both FK columns (composite key)
        if len(pk_fields) >= 2:
            pk_field_names = [col.name for col in pk_fields]
            fk_field_names = [col.name for col in fk_columns]
            has_pk_consisting_of_fks = all(name in fk_field_names for name in pk_field_names)

            if has_pk_consisting_of_fks:
                return True

        # Alternative check: table only has 2 FKs and minimal other fields
        substantial_fields = [
            col for col in table.columns
            if not col.is_pk and not col.is_foreign_key and
            col.name.lower() not in (
                "created_at", "updated_at", "created", "modified",
                "creation_date", "modification_date", "timestamp"
            )
        ]

        return len(substantial_fields) <= 1

    def _get_foreign_key_columns(self, table: TableInfo):
        """Get foreign key columns from a table."""
        return [col for col in table.columns if col.is_foreign_key]

    def _create_self_referential_m2m(
        self, through_table: TableInfo, target_table_name: str,
        fk1, fk2, all_tables: Dict[str, TableInfo], relationships: List[RelationshipInfo]
    ):
        """Create self-referential M2M relationship."""
        # Generate descriptive field name based on through table or column names
        rel_name = through_table.name

        # Try to create better names based on column names
        if any(s in fk1.name.lower() for s in ["from", "source", "follower"]):
            rel_name = "followers"
        elif any(s in fk1.name.lower() for s in ["to", "target", "following"]):
            rel_name = "following"
        else:
            # Use plural form of through table name
            rel_name = f"{through_table.name}s"

        relationship = RelationshipInfo(
            name=rel_name,
            relationship_type=RelationshipType.MANY_TO_MANY,
            source_table=target_table_name,
            target_table=target_table_name,
            source_columns=[fk1.name],
            target_columns=[fk2.name],
            through_table=through_table.name,
            through_fields=(fk1.name, fk2.name),
            related_name=f"{rel_name}_of",
            symmetrical=False  # Most self-referential relationships aren't symmetrical
        )
        relationships.append(relationship)

    def _create_bidirectional_m2m(
        self, through_table: TableInfo, table1_name: str, table2_name: str,
        table1_fk, table2_fk, all_tables: Dict[str, TableInfo], relationships: List[RelationshipInfo]
    ):
        """Create bidirectional M2M relationships."""
        # Only create one M2M field (on the lexicographically first table)
        # to avoid duplicate relationships
        if table1_name <= table2_name:
            # Put M2M field on table1 pointing to table2
            rel_name = f"{table2_name}s"  # Plural of target table
            related_name = f"{table1_name}s"  # Plural of source table for reverse

            relationship = RelationshipInfo(
                name=rel_name,
                relationship_type=RelationshipType.MANY_TO_MANY,
                source_table=table1_name,
                target_table=table2_name,
                source_columns=[table1_fk.name],
                target_columns=[table2_fk.name],
                through_table=through_table.name,
                through_fields=(table1_fk.name, table2_fk.name),
                related_name=related_name
            )
        else:
            # Put M2M field on table2 pointing to table1
            rel_name = f"{table1_name}s"  # Plural of target table
            related_name = f"{table2_name}s"  # Plural of source table for reverse

            relationship = RelationshipInfo(
                name=rel_name,
                relationship_type=RelationshipType.MANY_TO_MANY,
                source_table=table2_name,
                target_table=table1_name,
                source_columns=[table2_fk.name],
                target_columns=[table1_fk.name],
                through_table=through_table.name,
                through_fields=(table2_fk.name, table1_fk.name),
                related_name=related_name
            )

        relationships.append(relationship)

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
