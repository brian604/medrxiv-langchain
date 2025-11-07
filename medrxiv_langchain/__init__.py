"""
BioRxiv/MedRxiv LangChain Loader and API package.

This package provides:
- BioRxivLoader: LangChain loader for fetching papers
- QueryBuilder: Simple query builder (legacy)
- EnhancedQueryBuilder: Advanced query builder with compound queries
- API models and endpoints for REST API access
- Processing utilities for summarization and semantic similarity
"""

from .loader import BioRxivLoader, QueryBuilder
from .query_builder_enhanced import EnhancedQueryBuilder, QueryNode, LogicOperator

__version__ = "1.0.0"

__all__ = [
    # Core loaders
    "BioRxivLoader",
    "QueryBuilder",

    # Enhanced query building
    "EnhancedQueryBuilder",
    "QueryNode",
    "LogicOperator",
]

# API components are available but not exported by default
# Import them explicitly if needed:
# from medrxiv_langchain.api_main import app
# from medrxiv_langchain.api_models import SearchRequest, SearchResponse, etc.
# from medrxiv_langchain.processing_summarization import SummarizationFactory
# from medrxiv_langchain.processing_similarity import SemanticSimilarityEngine
