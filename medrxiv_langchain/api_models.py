"""
Pydantic models for the BioRxiv/MedRxiv API.
Defines request and response schemas for all endpoints.
"""

from typing import List, Optional, Dict, Any, Literal, Union
from pydantic import BaseModel, Field, validator
from datetime import datetime
from enum import Enum


# ============================================================================
# Enums
# ============================================================================

class LogicOperator(str, Enum):
    """Boolean logic operators for compound queries."""
    AND = "AND"
    OR = "OR"
    NOT = "NOT"


class SummarizationEngine(str, Enum):
    """Supported summarization engines."""
    OPENAI = "openai"
    HUGGINGFACE = "huggingface"
    LANGCHAIN = "langchain"


class ExportFormat(str, Enum):
    """Supported export formats."""
    JSON = "json"
    CSV = "csv"


class ServerName(str, Enum):
    """Supported servers."""
    BIORXIV = "biorxiv"
    MEDRXIV = "medrxiv"


class JobStatus(str, Enum):
    """Status of async jobs."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


# ============================================================================
# Query Models
# ============================================================================

class QueryNodeModel(BaseModel):
    """Represents a node in a compound query tree."""
    keywords: List[str] = Field(default_factory=list, description="Keywords to search for")
    category: Optional[str] = Field(None, description="Category/subject area filter")
    operator: Optional[LogicOperator] = Field(None, description="Logic operator for children")
    children: List['QueryNodeModel'] = Field(default_factory=list, description="Child query nodes")

    class Config:
        use_enum_values = True


# Update forward reference
QueryNodeModel.model_rebuild()


class SearchRequest(BaseModel):
    """Request model for /search endpoint."""

    # Simple search parameters
    keywords: Optional[List[str]] = Field(None, description="Keywords to search for")
    category: Optional[str] = Field(None, description="Category/subject area")

    # Compound query (alternative to simple search)
    query_tree: Optional[QueryNodeModel] = Field(None, description="Compound query tree")

    # Date filters (mutually exclusive)
    start_date: Optional[str] = Field(None, description="Start date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="End date (YYYY-MM-DD)")
    recent_papers: Optional[int] = Field(None, description="Number of most recent papers", gt=0)
    recent_days: Optional[int] = Field(None, description="Papers from last N days", gt=0)

    # Server selection
    servers: List[ServerName] = Field(
        default=[ServerName.BIORXIV],
        description="Servers to query"
    )

    # Result limits
    max_results: Optional[int] = Field(None, description="Maximum number of results", gt=0)

    @validator('start_date', 'end_date')
    def validate_date_format(cls, v):
        """Validate date format."""
        if v:
            try:
                datetime.strptime(v, "%Y-%m-%d")
            except ValueError:
                raise ValueError("Date must be in YYYY-MM-DD format")
        return v

    @validator('servers')
    def validate_servers(cls, v):
        """Ensure at least one server is selected."""
        if not v:
            raise ValueError("At least one server must be specified")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "keywords": ["COVID-19", "vaccine"],
                "category": "immunology",
                "start_date": "2023-01-01",
                "end_date": "2023-12-31",
                "servers": ["biorxiv", "medrxiv"],
                "max_results": 100
            }
        }


class PaperMetadata(BaseModel):
    """Metadata for a single paper."""
    doi: str = Field(..., description="Digital Object Identifier")
    title: str = Field(..., description="Paper title")
    authors: str = Field(..., description="Authors (comma-separated)")
    author_corresponding: Optional[str] = Field(None, description="Corresponding author")
    author_corresponding_institution: Optional[str] = Field(None, description="Corresponding author institution")
    date: str = Field(..., description="Publication date")
    version: Optional[str] = Field(None, description="Version number")
    category: Optional[str] = Field(None, description="Subject category")
    type: Optional[str] = Field(None, description="Article type")
    license: Optional[str] = Field(None, description="License type")
    published: Optional[str] = Field(None, description="Journal publication status")
    server: str = Field(..., description="Source server (biorxiv/medrxiv)")
    abstract: Optional[str] = Field(None, description="Paper abstract")
    link_page: Optional[str] = Field(None, description="URL to paper page")
    link_pdf: Optional[str] = Field(None, description="URL to PDF")

    class Config:
        json_schema_extra = {
            "example": {
                "doi": "10.1101/2023.01.01.123456",
                "title": "Novel approach to COVID-19 vaccination",
                "authors": "Smith J, Doe A, Johnson B",
                "date": "2023-01-15",
                "category": "immunology",
                "server": "biorxiv",
                "abstract": "We present a novel approach...",
                "link_pdf": "https://www.biorxiv.org/content/10.1101/2023.01.01.123456v1.full.pdf"
            }
        }


class SearchResponse(BaseModel):
    """Response model for /search endpoint."""
    query_id: str = Field(..., description="Unique query identifier")
    total_results: int = Field(..., description="Total number of results found")
    papers: List[PaperMetadata] = Field(..., description="List of papers")
    servers_queried: List[str] = Field(..., description="Servers that were queried")
    execution_time_ms: float = Field(..., description="Query execution time in milliseconds")
    errors: Optional[List[str]] = Field(None, description="Any errors encountered")


# ============================================================================
# Fetch Models
# ============================================================================

class FetchRequest(BaseModel):
    """Request model for /fetch endpoint."""
    query_id: Optional[str] = Field(None, description="Query ID from previous search")
    dois: Optional[List[str]] = Field(None, description="List of DOIs to fetch")
    search_params: Optional[SearchRequest] = Field(None, description="Search parameters (alternative to query_id)")
    async_execution: bool = Field(False, description="Execute asynchronously")

    @validator('dois', 'search_params', 'query_id')
    def validate_input(cls, v, values):
        """Ensure at least one input method is provided."""
        if not any([values.get('query_id'), values.get('dois'), v]):
            raise ValueError("Must provide either query_id, dois, or search_params")
        return v


class FetchResponse(BaseModel):
    """Response model for /fetch endpoint."""
    job_id: Optional[str] = Field(None, description="Job ID for async requests")
    status: JobStatus = Field(..., description="Job status")
    papers: Optional[List[PaperMetadata]] = Field(None, description="Fetched papers")
    total_fetched: int = Field(0, description="Number of papers fetched")
    errors: Optional[List[str]] = Field(None, description="Errors encountered")
    retry_attempts: Optional[Dict[str, int]] = Field(None, description="Retry attempts per server")


# ============================================================================
# Metadata Extraction Models
# ============================================================================

class MetadataExtractionRequest(BaseModel):
    """Request model for /extract_metadata endpoint."""
    dois: List[str] = Field(..., description="List of DOIs to extract metadata for")
    fields: Optional[List[str]] = Field(
        None,
        description="Specific metadata fields to extract (all if not specified)"
    )


class MetadataExtractionResponse(BaseModel):
    """Response model for /extract_metadata endpoint."""
    papers: List[PaperMetadata] = Field(..., description="Papers with extracted metadata")
    total_processed: int = Field(..., description="Total papers processed")
    errors: Optional[List[str]] = Field(None, description="Errors encountered")


# ============================================================================
# Summarization Models
# ============================================================================

class SummarizeRequest(BaseModel):
    """Request model for /summarize endpoint."""
    dois: Optional[List[str]] = Field(None, description="DOIs to summarize")
    paper_ids: Optional[List[str]] = Field(None, description="Internal paper IDs")
    query_id: Optional[str] = Field(None, description="Query ID from search")

    engine: SummarizationEngine = Field(
        default=SummarizationEngine.LANGCHAIN,
        description="Summarization engine to use"
    )
    max_length: Optional[int] = Field(150, description="Maximum summary length (words)", gt=0)
    include_abstract: bool = Field(True, description="Include abstract in summary source")
    include_fulltext: bool = Field(False, description="Include full text (if available)")

    # Engine-specific parameters
    openai_model: Optional[str] = Field("gpt-3.5-turbo", description="OpenAI model name")
    temperature: Optional[float] = Field(0.7, description="Temperature for generation", ge=0, le=2)

    @validator('dois', 'paper_ids', 'query_id')
    def validate_input(cls, v, values):
        """Ensure at least one input method is provided."""
        if not any([values.get('query_id'), values.get('dois'), values.get('paper_ids'), v]):
            raise ValueError("Must provide either query_id, dois, or paper_ids")
        return v


class PaperSummary(BaseModel):
    """Summary of a single paper."""
    doi: str = Field(..., description="Paper DOI")
    title: str = Field(..., description="Paper title")
    summary: str = Field(..., description="Generated summary")
    engine_used: str = Field(..., description="Summarization engine used")
    word_count: int = Field(..., description="Summary word count")


class SummarizeResponse(BaseModel):
    """Response model for /summarize endpoint."""
    summaries: List[PaperSummary] = Field(..., description="Generated summaries")
    total_processed: int = Field(..., description="Total papers processed")
    engine_used: str = Field(..., description="Summarization engine used")
    errors: Optional[List[str]] = Field(None, description="Errors encountered")


# ============================================================================
# Semantic Similarity Models
# ============================================================================

class SemanticSimilarityRequest(BaseModel):
    """Request model for /semantic_similarity endpoint."""
    query_text: str = Field(..., description="Text to compare against")
    dois: Optional[List[str]] = Field(None, description="DOIs to rank")
    query_id: Optional[str] = Field(None, description="Query ID from search")

    model_name: str = Field(
        default="all-MiniLM-L6-v2",
        description="Sentence transformer model name"
    )
    top_k: Optional[int] = Field(None, description="Return only top K results", gt=0)
    threshold: Optional[float] = Field(None, description="Minimum similarity threshold", ge=0, le=1)

    @validator('dois', 'query_id')
    def validate_input(cls, v, values):
        """Ensure at least one input method is provided."""
        if not any([values.get('query_id'), values.get('dois'), v]):
            raise ValueError("Must provide either query_id or dois")
        return v


class PaperSimilarity(BaseModel):
    """Similarity score for a single paper."""
    doi: str = Field(..., description="Paper DOI")
    title: str = Field(..., description="Paper title")
    similarity_score: float = Field(..., description="Similarity score (0-1)", ge=0, le=1)
    rank: int = Field(..., description="Rank by similarity", gt=0)
    abstract: Optional[str] = Field(None, description="Paper abstract")


class SemanticSimilarityResponse(BaseModel):
    """Response model for /semantic_similarity endpoint."""
    query_text: str = Field(..., description="Original query text")
    ranked_papers: List[PaperSimilarity] = Field(..., description="Papers ranked by similarity")
    total_compared: int = Field(..., description="Total papers compared")
    model_used: str = Field(..., description="Model used for similarity")
    errors: Optional[List[str]] = Field(None, description="Errors encountered")


# ============================================================================
# Export Models
# ============================================================================

class ExportRequest(BaseModel):
    """Request model for /export endpoint."""
    query_id: Optional[str] = Field(None, description="Query ID to export")
    dois: Optional[List[str]] = Field(None, description="Specific DOIs to export")

    format: ExportFormat = Field(default=ExportFormat.JSON, description="Export format")
    include_abstracts: bool = Field(True, description="Include abstracts in export")
    include_metadata: bool = Field(True, description="Include full metadata")

    # CSV-specific options
    csv_delimiter: str = Field(",", description="CSV delimiter character")
    csv_include_header: bool = Field(True, description="Include header row in CSV")

    @validator('dois', 'query_id')
    def validate_input(cls, v, values):
        """Ensure at least one input method is provided."""
        if not any([values.get('query_id'), values.get('dois'), v]):
            raise ValueError("Must provide either query_id or dois")
        return v


# ============================================================================
# Health Check Models
# ============================================================================

class ServerHealth(BaseModel):
    """Health status of a single server."""
    server: str = Field(..., description="Server name")
    status: str = Field(..., description="Status (up/down)")
    response_time_ms: Optional[float] = Field(None, description="Response time in milliseconds")
    last_checked: datetime = Field(..., description="Last health check timestamp")


class HealthResponse(BaseModel):
    """Response model for /health endpoint."""
    status: str = Field(..., description="Overall API status")
    version: str = Field(..., description="API version")
    servers: List[ServerHealth] = Field(..., description="Server health status")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Current timestamp")


# ============================================================================
# Error Models
# ============================================================================

class ErrorDetail(BaseModel):
    """Detailed error information."""
    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: ErrorDetail = Field(..., description="Error information")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")


# ============================================================================
# Job Status Models (for async operations)
# ============================================================================

class JobStatusResponse(BaseModel):
    """Response model for job status queries."""
    job_id: str = Field(..., description="Job identifier")
    status: JobStatus = Field(..., description="Current job status")
    progress: Optional[float] = Field(None, description="Progress percentage (0-100)", ge=0, le=100)
    result: Optional[Any] = Field(None, description="Job result (if completed)")
    error: Optional[str] = Field(None, description="Error message (if failed)")
    created_at: datetime = Field(..., description="Job creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
