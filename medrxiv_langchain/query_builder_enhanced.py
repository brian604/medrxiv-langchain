"""
Enhanced QueryBuilder for BioRxiv/MedRxiv with compound query support.
Supports keywords, categories, boolean logic (AND/OR/NOT), and date ranges.
"""

from typing import List, Any, Dict, Optional, Union, Literal
from datetime import datetime, timedelta
from enum import Enum


class LogicOperator(str, Enum):
    """Boolean logic operators for compound queries."""
    AND = "AND"
    OR = "OR"
    NOT = "NOT"


class QueryNode:
    """Represents a node in a compound query tree."""

    def __init__(
        self,
        keywords: Optional[List[str]] = None,
        category: Optional[str] = None,
        operator: Optional[LogicOperator] = None,
        children: Optional[List['QueryNode']] = None
    ):
        self.keywords = keywords or []
        self.category = category
        self.operator = operator
        self.children = children or []

    def to_query_string(self) -> str:
        """Convert query node to search query string."""
        if self.operator and self.children:
            # Compound query
            child_queries = [child.to_query_string() for child in self.children]
            if self.operator == LogicOperator.AND:
                return f"({' AND '.join(child_queries)})"
            elif self.operator == LogicOperator.OR:
                return f"({' OR '.join(child_queries)})"
            elif self.operator == LogicOperator.NOT:
                if len(child_queries) == 1:
                    return f"NOT ({child_queries[0]})"
                else:
                    raise ValueError("NOT operator requires exactly one child")
        else:
            # Leaf query
            parts = []
            if self.keywords:
                keyword_str = ' '.join(f'"{kw}"' if ' ' in kw else kw for kw in self.keywords)
                parts.append(keyword_str)
            if self.category:
                parts.append(f'category:"{self.category}"')
            return ' '.join(parts) if parts else ''

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'keywords': self.keywords,
            'category': self.category,
            'operator': self.operator.value if self.operator else None,
            'children': [child.to_dict() for child in self.children]
        }


class EnhancedQueryBuilder:
    """
    Enhanced builder for constructing complex BioRxiv/MedRxiv queries.

    Supports:
    - Keywords and keyword phrases
    - Category filtering
    - Compound queries with AND/OR/NOT logic
    - Absolute and relative date ranges
    - Multi-server selection

    Examples:
        # Simple keyword search
        query = (EnhancedQueryBuilder()
                .with_keywords(['COVID-19', 'vaccine'])
                .date_range('2023-01-01', '2023-12-31')
                .build())

        # Compound query with AND/OR
        query = (EnhancedQueryBuilder()
                .start_group(LogicOperator.AND)
                    .with_keywords(['machine learning'])
                    .with_category('bioinformatics')
                .end_group()
                .from_servers(['biorxiv', 'medrxiv'])
                .build())

        # Complex nested query
        query = (EnhancedQueryBuilder()
                .start_group(LogicOperator.OR)
                    .with_keywords(['CRISPR'])
                    .start_group(LogicOperator.AND)
                        .with_keywords(['genome editing'])
                        .with_category('genetics')
                    .end_group()
                .end_group()
                .last_days(30)
                .build())
    """

    def __init__(self):
        self._root_node: Optional[QueryNode] = None
        self._current_node: Optional[QueryNode] = None
        self._node_stack: List[QueryNode] = []

        # Date/time filters
        self._start_date: Optional[str] = None
        self._end_date: Optional[str] = None
        self._recent_papers: Optional[int] = None
        self._recent_days: Optional[int] = None

        # Server selection
        self._servers: List[str] = ["biorxiv"]

        # Simple keywords (for backward compatibility)
        self._simple_keywords: List[str] = []
        self._simple_category: Optional[str] = None

    def with_keywords(self, keywords: Union[str, List[str]]) -> 'EnhancedQueryBuilder':
        """
        Add keywords to search for.

        Args:
            keywords: Single keyword or list of keywords

        Returns:
            Self for chaining
        """
        if isinstance(keywords, str):
            keywords = [keywords]

        if self._current_node:
            self._current_node.keywords.extend(keywords)
        else:
            self._simple_keywords.extend(keywords)

        return self

    def with_category(self, category: str) -> 'EnhancedQueryBuilder':
        """
        Filter by category/subject area.

        Common categories:
        - bioinformatics
        - genetics
        - immunology
        - microbiology
        - neuroscience
        - epidemiology

        Args:
            category: Category name

        Returns:
            Self for chaining
        """
        if self._current_node:
            self._current_node.category = category
        else:
            self._simple_category = category

        return self

    def start_group(self, operator: LogicOperator) -> 'EnhancedQueryBuilder':
        """
        Start a new query group with the specified logic operator.

        Args:
            operator: AND, OR, or NOT

        Returns:
            Self for chaining
        """
        new_node = QueryNode(operator=operator)

        if self._current_node:
            self._current_node.children.append(new_node)
            self._node_stack.append(self._current_node)
        else:
            self._root_node = new_node

        self._current_node = new_node
        return self

    def end_group(self) -> 'EnhancedQueryBuilder':
        """
        End the current query group and return to parent.

        Returns:
            Self for chaining
        """
        if self._node_stack:
            self._current_node = self._node_stack.pop()
        else:
            self._current_node = None

        return self

    def date_range(self, start_date: str, end_date: str) -> 'EnhancedQueryBuilder':
        """
        Set absolute date range for the query.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format

        Returns:
            Self for chaining
        """
        self._validate_date(start_date)
        self._validate_date(end_date)
        self._start_date = start_date
        self._end_date = end_date
        return self

    def most_recent(self, count: int) -> 'EnhancedQueryBuilder':
        """
        Get most recent N papers.

        Args:
            count: Number of recent papers

        Returns:
            Self for chaining
        """
        if count <= 0:
            raise ValueError("Count must be positive")
        self._recent_papers = count
        return self

    def last_days(self, days: int) -> 'EnhancedQueryBuilder':
        """
        Get papers from last N days (relative date range).

        Args:
            days: Number of days

        Returns:
            Self for chaining
        """
        if days <= 0:
            raise ValueError("Days must be positive")
        self._recent_days = days
        return self

    def last_month(self) -> 'EnhancedQueryBuilder':
        """Get papers from the last month."""
        return self.last_days(30)

    def last_week(self) -> 'EnhancedQueryBuilder':
        """Get papers from the last week."""
        return self.last_days(7)

    def from_servers(self, servers: Union[str, List[str]]) -> 'EnhancedQueryBuilder':
        """
        Specify which servers to query.

        Args:
            servers: 'biorxiv', 'medrxiv', or list of both

        Returns:
            Self for chaining
        """
        if isinstance(servers, str):
            servers = [servers]

        for server in servers:
            if server.lower() not in ["biorxiv", "medrxiv"]:
                raise ValueError("Server must be either 'biorxiv' or 'medrxiv'")

        self._servers = [s.lower() for s in servers]
        return self

    def build(self) -> Dict[str, Any]:
        """
        Build the final query parameters.

        Returns:
            Dictionary with query parameters

        Raises:
            ValueError: If query configuration is invalid
        """
        # Validate that we don't mix different query types
        if sum(x is not None for x in [self._recent_papers, self._recent_days, self._start_date]) > 1:
            raise ValueError(
                "Cannot combine different date query types. "
                "Use either date_range, most_recent, or last_days."
            )

        # Build query string
        query_text: Optional[str] = None
        if self._root_node:
            query_text = self._root_node.to_query_string()
        elif self._simple_keywords or self._simple_category:
            # Simple query without groups
            node = QueryNode(keywords=self._simple_keywords, category=self._simple_category)
            query_text = node.to_query_string()

        # Build date parameters
        query_interval: Optional[str] = None
        start_date: Optional[str] = None
        end_date: Optional[str] = None

        if self._recent_papers is not None:
            query_interval = str(self._recent_papers)
        elif self._recent_days is not None:
            query_interval = f"{self._recent_days}d"
        else:
            start_date = self._start_date or (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            end_date = self._end_date or datetime.now().strftime("%Y-%m-%d")

        return {
            "search_query": query_text,  # Text search query
            "query_interval": query_interval,  # For most_recent/last_days
            "start_date": start_date,
            "end_date": end_date,
            "servers": self._servers,
            "has_search": bool(query_text)
        }

    @staticmethod
    def _validate_date(date_str: str) -> None:
        """Validate date format (YYYY-MM-DD)."""
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError as e:
            raise ValueError(
                f"Invalid date format: {date_str}. Date must be in YYYY-MM-DD format"
            ) from e

    def to_dict(self) -> Dict[str, Any]:
        """
        Export query structure as dictionary for serialization.

        Returns:
            Full query structure including tree and parameters
        """
        return {
            'query_tree': self._root_node.to_dict() if self._root_node else None,
            'simple_keywords': self._simple_keywords,
            'simple_category': self._simple_category,
            'date_filters': {
                'start_date': self._start_date,
                'end_date': self._end_date,
                'recent_papers': self._recent_papers,
                'recent_days': self._recent_days
            },
            'servers': self._servers
        }
