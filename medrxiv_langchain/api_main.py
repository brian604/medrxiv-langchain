"""
FastAPI application for BioRxiv/MedRxiv paper fetching and processing.
Implements the API-first architecture defined in the PRD.
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, status
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, List, Optional, Any
import uuid
import time
import logging
import io
import csv
import json
from datetime import datetime
from contextlib import asynccontextmanager

# Import models
from .api_models import (
    SearchRequest, SearchResponse, PaperMetadata,
    FetchRequest, FetchResponse,
    MetadataExtractionRequest, MetadataExtractionResponse,
    SummarizeRequest, SummarizeResponse, PaperSummary,
    SemanticSimilarityRequest, SemanticSimilarityResponse, PaperSimilarity,
    ExportRequest, ExportFormat,
    HealthResponse, ServerHealth,
    ErrorResponse, ErrorDetail,
    JobStatus, JobStatusResponse
)

# Import query builders and loaders
from .query_builder_enhanced import EnhancedQueryBuilder
from .loader import BioRxivLoader

# Import processing modules
from .processing_summarization import SummarizationFactory
from .processing_similarity import SemanticSimilarityEngine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# In-Memory Storage (for demo; use Redis/database in production)
# ============================================================================

# Store query results
query_cache: Dict[str, Dict[str, Any]] = {}

# Store async jobs
job_store: Dict[str, Dict[str, Any]] = {}

# Authentication (optional)
API_KEYS = set()  # Add keys here or load from environment


# ============================================================================
# Lifespan Management
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan events for startup and shutdown."""
    # Startup
    logger.info("Starting BioRxiv/MedRxiv API...")
    logger.info("API ready to receive requests")

    yield

    # Shutdown
    logger.info("Shutting down API...")
    query_cache.clear()
    job_store.clear()


# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(
    title="BioRxiv/MedRxiv API",
    description="API-first backend for fetching and processing preprints from BioRxiv and MedRxiv",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Optional security
security = HTTPBearer(auto_error=False)


# ============================================================================
# Authentication (Optional)
# ============================================================================

async def verify_token(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    """
    Verify API token (optional authentication).
    To enable authentication, set API_KEYS environment variable.
    """
    if not API_KEYS:
        # Authentication disabled
        return None

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials"
        )

    if credentials.credentials not in API_KEYS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )

    return credentials.credentials


# ============================================================================
# Helper Functions
# ============================================================================

def create_query_id() -> str:
    """Generate unique query ID."""
    return f"query_{uuid.uuid4().hex[:16]}"


def create_job_id() -> str:
    """Generate unique job ID."""
    return f"job_{uuid.uuid4().hex[:16]}"


def paper_to_metadata(paper_dict: Dict[str, Any]) -> PaperMetadata:
    """Convert paper dictionary to PaperMetadata model."""
    return PaperMetadata(
        doi=paper_dict.get('doi', ''),
        title=paper_dict.get('title', ''),
        authors=paper_dict.get('authors', ''),
        author_corresponding=paper_dict.get('author_corresponding'),
        author_corresponding_institution=paper_dict.get('author_corresponding_institution'),
        date=paper_dict.get('date', ''),
        version=paper_dict.get('version'),
        category=paper_dict.get('category'),
        type=paper_dict.get('type'),
        license=paper_dict.get('license'),
        published=paper_dict.get('published'),
        server=paper_dict.get('server', 'biorxiv'),
        abstract=paper_dict.get('page_content', '').split('\n\n')[-1] if 'page_content' in paper_dict else None,
        link_page=paper_dict.get('link_page'),
        link_pdf=paper_dict.get('link_pdf')
    )


# ============================================================================
# Endpoints
# ============================================================================

@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": "BioRxiv/MedRxiv API",
        "version": "1.0.0",
        "description": "API for fetching and processing preprints",
        "endpoints": {
            "docs": "/docs",
            "health": "/api/v1/health",
            "search": "/api/v1/search",
            "fetch": "/api/v1/fetch",
            "extract_metadata": "/api/v1/extract_metadata",
            "summarize": "/api/v1/summarize",
            "semantic_similarity": "/api/v1/semantic_similarity",
            "export": "/api/v1/export"
        }
    }


@app.get("/api/v1/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    Check API and server health.
    Tests connectivity to BioRxiv and MedRxiv APIs.
    """
    import requests

    servers_status = []

    for server_name in ['biorxiv', 'medrxiv']:
        try:
            start_time = time.time()
            response = requests.get(
                f"https://api.biorxiv.org/details/{server_name}/2024-01-01/2024-01-02/0/json",
                timeout=5
            )
            response_time = (time.time() - start_time) * 1000

            servers_status.append(ServerHealth(
                server=server_name,
                status="up" if response.status_code == 200 else "degraded",
                response_time_ms=response_time,
                last_checked=datetime.utcnow()
            ))
        except Exception as e:
            logger.error(f"Health check failed for {server_name}: {e}")
            servers_status.append(ServerHealth(
                server=server_name,
                status="down",
                response_time_ms=None,
                last_checked=datetime.utcnow()
            ))

    overall_status = "healthy" if all(s.status == "up" for s in servers_status) else "degraded"

    return HealthResponse(
        status=overall_status,
        version="1.0.0",
        servers=servers_status,
        timestamp=datetime.utcnow()
    )


@app.post("/api/v1/search", response_model=SearchResponse, tags=["Search"])
async def search_papers(
    request: SearchRequest,
    token: Optional[str] = Depends(verify_token)
):
    """
    Search for papers with flexible query construction.

    Supports:
    - Keyword search
    - Category filtering
    - Compound queries (AND/OR/NOT)
    - Date range filtering
    - Multi-server queries
    """
    try:
        start_time = time.time()
        query_id = create_query_id()

        # Build query using EnhancedQueryBuilder
        builder = EnhancedQueryBuilder()

        # Add keywords
        if request.keywords:
            builder.with_keywords(request.keywords)

        # Add category
        if request.category:
            builder.with_category(request.category)

        # Add date filters (mutually exclusive)
        if request.start_date and request.end_date:
            builder.date_range(request.start_date, request.end_date)
        elif request.recent_papers:
            builder.most_recent(request.recent_papers)
        elif request.recent_days:
            builder.last_days(request.recent_days)
        else:
            # Default: last month
            builder.last_month()

        # Add servers
        if request.servers:
            builder.from_servers([s.value for s in request.servers])

        # Build query
        query_params = builder.build()

        # Create loader
        loader = BioRxivLoader(**query_params, max_results=request.max_results)

        # Fetch papers
        papers = loader.load()

        # Convert to metadata models
        paper_metadata = [paper_to_metadata(p.metadata) for p in papers]

        # Store in cache
        query_cache[query_id] = {
            'request': request.dict(),
            'papers': paper_metadata,
            'timestamp': datetime.utcnow()
        }

        execution_time = (time.time() - start_time) * 1000

        return SearchResponse(
            query_id=query_id,
            total_results=len(paper_metadata),
            papers=paper_metadata,
            servers_queried=[s.value for s in request.servers],
            execution_time_ms=execution_time,
            errors=None
        )

    except Exception as e:
        logger.error(f"Error in search endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {str(e)}"
        )


@app.post("/api/v1/fetch", response_model=FetchResponse, tags=["Fetch"])
async def fetch_papers(
    request: FetchRequest,
    background_tasks: BackgroundTasks,
    token: Optional[str] = Depends(verify_token)
):
    """
    Fetch papers based on query ID, DOIs, or search parameters.
    Supports async execution for large queries.
    """
    try:
        if request.async_execution:
            # Create background job
            job_id = create_job_id()

            job_store[job_id] = {
                'status': JobStatus.PENDING,
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow(),
                'result': None,
                'error': None
            }

            # Add background task
            background_tasks.add_task(fetch_papers_background, job_id, request)

            return FetchResponse(
                job_id=job_id,
                status=JobStatus.PENDING,
                papers=None,
                total_fetched=0,
                errors=None
            )
        else:
            # Synchronous execution
            papers = _fetch_papers_sync(request)

            return FetchResponse(
                job_id=None,
                status=JobStatus.COMPLETED,
                papers=papers,
                total_fetched=len(papers),
                errors=None
            )

    except Exception as e:
        logger.error(f"Error in fetch endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Fetch failed: {str(e)}"
        )


def _fetch_papers_sync(request: FetchRequest) -> List[PaperMetadata]:
    """Synchronous paper fetching logic."""
    if request.query_id:
        # Fetch from cache
        if request.query_id not in query_cache:
            raise HTTPException(status_code=404, detail="Query ID not found")
        return query_cache[request.query_id]['papers']

    elif request.search_params:
        # Execute search
        # This is a simplified version; in production, reuse search endpoint logic
        raise HTTPException(status_code=501, detail="Search params not yet implemented in fetch")

    elif request.dois:
        # Fetch specific DOIs
        # Note: BioRxiv API doesn't support DOI-based fetch directly
        # This would require iterating or caching
        raise HTTPException(status_code=501, detail="DOI-based fetch not yet implemented")

    else:
        raise HTTPException(status_code=400, detail="Must provide query_id, dois, or search_params")


async def fetch_papers_background(job_id: str, request: FetchRequest):
    """Background task for async paper fetching."""
    try:
        job_store[job_id]['status'] = JobStatus.IN_PROGRESS
        job_store[job_id]['updated_at'] = datetime.utcnow()

        papers = _fetch_papers_sync(request)

        job_store[job_id]['status'] = JobStatus.COMPLETED
        job_store[job_id]['result'] = [p.dict() for p in papers]
        job_store[job_id]['updated_at'] = datetime.utcnow()

    except Exception as e:
        logger.error(f"Background fetch failed for job {job_id}: {e}")
        job_store[job_id]['status'] = JobStatus.FAILED
        job_store[job_id]['error'] = str(e)
        job_store[job_id]['updated_at'] = datetime.utcnow()


@app.post("/api/v1/extract_metadata", response_model=MetadataExtractionResponse, tags=["Processing"])
async def extract_metadata(
    request: MetadataExtractionRequest,
    token: Optional[str] = Depends(verify_token)
):
    """
    Extract structured metadata from papers.
    Currently returns metadata already fetched; can be extended for additional extraction.
    """
    try:
        # In the current implementation, metadata is already extracted during fetch
        # This endpoint can be extended to add additional processing (e.g., NER, entity extraction)

        raise HTTPException(
            status_code=501,
            detail="Metadata extraction endpoint not yet fully implemented"
        )

    except Exception as e:
        logger.error(f"Error in metadata extraction: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Metadata extraction failed: {str(e)}"
        )


@app.post("/api/v1/summarize", response_model=SummarizeResponse, tags=["Processing"])
async def summarize_papers(
    request: SummarizeRequest,
    token: Optional[str] = Depends(verify_token)
):
    """
    Generate summaries for papers using various summarization engines.
    """
    try:
        # Get papers to summarize
        papers = []

        if request.query_id:
            if request.query_id not in query_cache:
                raise HTTPException(status_code=404, detail="Query ID not found")
            papers = query_cache[request.query_id]['papers']
        elif request.dois:
            # Find papers by DOI in cache
            for query_data in query_cache.values():
                for paper in query_data['papers']:
                    if paper.doi in request.dois:
                        papers.append(paper)
        else:
            raise HTTPException(status_code=400, detail="Must provide query_id or dois")

        if not papers:
            raise HTTPException(status_code=404, detail="No papers found to summarize")

        # Create summarization engine
        summarizer = SummarizationFactory.create_engine(
            request.engine.value,
            model=request.openai_model,
            temperature=request.temperature
        )

        # Generate summaries
        summaries = []
        for paper in papers:
            # Use abstract as source (full text not yet supported)
            text = paper.abstract if paper.abstract else paper.title

            summary_text = summarizer.summarize(text, max_length=request.max_length)

            summaries.append(PaperSummary(
                doi=paper.doi,
                title=paper.title,
                summary=summary_text,
                engine_used=request.engine.value,
                word_count=len(summary_text.split())
            ))

        return SummarizeResponse(
            summaries=summaries,
            total_processed=len(summaries),
            engine_used=request.engine.value,
            errors=None
        )

    except Exception as e:
        logger.error(f"Error in summarization: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Summarization failed: {str(e)}"
        )


@app.post("/api/v1/semantic_similarity", response_model=SemanticSimilarityResponse, tags=["Processing"])
async def semantic_similarity(
    request: SemanticSimilarityRequest,
    token: Optional[str] = Depends(verify_token)
):
    """
    Rank papers by semantic similarity to a query text.
    """
    try:
        # Get papers to rank
        papers = []

        if request.query_id:
            if request.query_id not in query_cache:
                raise HTTPException(status_code=404, detail="Query ID not found")
            papers = query_cache[request.query_id]['papers']
        elif request.dois:
            # Find papers by DOI in cache
            for query_data in query_cache.values():
                for paper in query_data['papers']:
                    if paper.doi in request.dois:
                        papers.append(paper)
        else:
            raise HTTPException(status_code=400, detail="Must provide query_id or dois")

        if not papers:
            raise HTTPException(status_code=404, detail="No papers found to rank")

        # Create similarity engine
        similarity_engine = SemanticSimilarityEngine(model_name=request.model_name)

        # Convert to dicts for ranking
        paper_dicts = [p.dict() for p in papers]

        # Rank papers
        ranked = similarity_engine.rank_papers(
            query_text=request.query_text,
            papers=paper_dicts,
            text_field='abstract',
            top_k=request.top_k,
            threshold=request.threshold
        )

        # Convert to response model
        ranked_papers = [
            PaperSimilarity(
                doi=paper['doi'],
                title=paper['title'],
                similarity_score=score,
                rank=i + 1,
                abstract=paper.get('abstract')
            )
            for i, (paper, score) in enumerate(ranked)
        ]

        return SemanticSimilarityResponse(
            query_text=request.query_text,
            ranked_papers=ranked_papers,
            total_compared=len(papers),
            model_used=request.model_name,
            errors=None
        )

    except Exception as e:
        logger.error(f"Error in semantic similarity: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Semantic similarity failed: {str(e)}"
        )


@app.get("/api/v1/export", tags=["Export"])
async def export_papers(
    query_id: Optional[str] = None,
    format: ExportFormat = ExportFormat.JSON,
    include_abstracts: bool = True,
    token: Optional[str] = Depends(verify_token)
):
    """
    Export papers in bulk (JSON or CSV format).
    """
    try:
        # Get papers to export
        if not query_id:
            raise HTTPException(status_code=400, detail="Must provide query_id")

        if query_id not in query_cache:
            raise HTTPException(status_code=404, detail="Query ID not found")

        papers = query_cache[query_id]['papers']

        if format == ExportFormat.JSON:
            # Export as JSON
            data = [p.dict() for p in papers]
            if not include_abstracts:
                for paper in data:
                    paper.pop('abstract', None)

            return JSONResponse(content={"papers": data})

        elif format == ExportFormat.CSV:
            # Export as CSV
            output = io.StringIO()
            if papers:
                fieldnames = ['doi', 'title', 'authors', 'date', 'category', 'server', 'link_pdf']
                if include_abstracts:
                    fieldnames.append('abstract')

                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()

                for paper in papers:
                    row = {
                        'doi': paper.doi,
                        'title': paper.title,
                        'authors': paper.authors,
                        'date': paper.date,
                        'category': paper.category or '',
                        'server': paper.server,
                        'link_pdf': paper.link_pdf or ''
                    }
                    if include_abstracts:
                        row['abstract'] = paper.abstract or ''

                    writer.writerow(row)

            output.seek(0)
            return StreamingResponse(
                iter([output.getvalue()]),
                media_type="text/csv",
                headers={
                    "Content-Disposition": f"attachment; filename=papers_{query_id}.csv"
                }
            )

    except Exception as e:
        logger.error(f"Error in export: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Export failed: {str(e)}"
        )


@app.get("/api/v1/jobs/{job_id}", response_model=JobStatusResponse, tags=["Jobs"])
async def get_job_status(
    job_id: str,
    token: Optional[str] = Depends(verify_token)
):
    """
    Get status of an async job.
    """
    if job_id not in job_store:
        raise HTTPException(status_code=404, detail="Job not found")

    job = job_store[job_id]

    return JobStatusResponse(
        job_id=job_id,
        status=job['status'],
        progress=None,  # Can be implemented for long-running jobs
        result=job.get('result'),
        error=job.get('error'),
        created_at=job['created_at'],
        updated_at=job['updated_at'],
        completed_at=job.get('completed_at')
    )


# ============================================================================
# Exception Handlers
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Custom handler for HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": str(exc.status_code),
                "message": exc.detail,
                "details": None
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Custom handler for general exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "500",
                "message": "Internal server error",
                "details": str(exc) if logger.level == logging.DEBUG else None
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    )


# ============================================================================
# Run Server (for development)
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
