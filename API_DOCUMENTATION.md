# BioRxiv/MedRxiv API Documentation

## Overview

The BioRxiv/MedRxiv API provides a comprehensive REST API for fetching, processing, and analyzing preprints from BioRxiv and MedRxiv repositories.

**Base URL**: `http://localhost:8000/api/v1`

**API Version**: 1.0.0

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Authentication](#authentication)
3. [Endpoints](#endpoints)
   - [Health Check](#health-check)
   - [Search](#search)
   - [Fetch](#fetch)
   - [Summarize](#summarize)
   - [Semantic Similarity](#semantic-similarity)
   - [Export](#export)
   - [Job Status](#job-status)
4. [Data Models](#data-models)
5. [Examples](#examples)
6. [Error Handling](#error-handling)

---

## Getting Started

### Installation

```bash
# Install with API dependencies
uv pip install -e ".[api]"

# Or install all dependencies
uv pip install -r requirements-api.txt
```

### Running the API Server

```bash
# Basic usage
python run_api.py

# With custom settings
python run_api.py --host 0.0.0.0 --port 8000 --workers 4

# Development mode (auto-reload)
python run_api.py --reload --log-level debug
```

### Interactive Documentation

Once the server is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## Authentication

Authentication is **optional** and disabled by default.

To enable authentication:
1. Set `API_KEYS` environment variable or in `.env` file
2. Include `Authorization: Bearer <your_api_key>` header in requests

Example with authentication:
```bash
curl -H "Authorization: Bearer your_api_key_here" \
     http://localhost:8000/api/v1/search
```

---

## Endpoints

### Health Check

**GET** `/api/v1/health`

Check API and server connectivity.

**Response**:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "servers": [
    {
      "server": "biorxiv",
      "status": "up",
      "response_time_ms": 234.5,
      "last_checked": "2024-01-15T10:30:00Z"
    },
    {
      "server": "medrxiv",
      "status": "up",
      "response_time_ms": 198.3,
      "last_checked": "2024-01-15T10:30:00Z"
    }
  ],
  "timestamp": "2024-01-15T10:30:00Z"
}
```

---

### Search

**POST** `/api/v1/search`

Search for papers with flexible query construction.

**Request Body**:
```json
{
  "keywords": ["COVID-19", "vaccine"],
  "category": "immunology",
  "start_date": "2023-01-01",
  "end_date": "2023-12-31",
  "servers": ["biorxiv", "medrxiv"],
  "max_results": 100
}
```

**Parameters**:
- `keywords` (array[string], optional): Keywords to search for
- `category` (string, optional): Category/subject area filter
- `start_date` (string, optional): Start date (YYYY-MM-DD)
- `end_date` (string, optional): End date (YYYY-MM-DD)
- `recent_papers` (integer, optional): Number of most recent papers
- `recent_days` (integer, optional): Papers from last N days
- `servers` (array[string]): Servers to query (`biorxiv`, `medrxiv`)
- `max_results` (integer, optional): Maximum number of results

**Response**:
```json
{
  "query_id": "query_abc123def456",
  "total_results": 42,
  "papers": [
    {
      "doi": "10.1101/2023.01.01.123456",
      "title": "Novel COVID-19 vaccination strategy",
      "authors": "Smith J, Doe A, Johnson B",
      "date": "2023-01-15",
      "category": "immunology",
      "server": "biorxiv",
      "abstract": "We present a novel approach...",
      "link_pdf": "https://www.biorxiv.org/content/10.1101/2023.01.01.123456v1.full.pdf"
    }
  ],
  "servers_queried": ["biorxiv", "medrxiv"],
  "execution_time_ms": 1234.5,
  "errors": null
}
```

---

### Fetch

**POST** `/api/v1/fetch`

Fetch papers based on query ID, DOIs, or search parameters. Supports async execution.

**Request Body**:
```json
{
  "query_id": "query_abc123def456",
  "async_execution": false
}
```

**Parameters**:
- `query_id` (string, optional): Query ID from previous search
- `dois` (array[string], optional): List of DOIs to fetch
- `search_params` (object, optional): Search parameters
- `async_execution` (boolean): Execute asynchronously (default: false)

**Synchronous Response**:
```json
{
  "job_id": null,
  "status": "completed",
  "papers": [...],
  "total_fetched": 42,
  "errors": null,
  "retry_attempts": null
}
```

**Asynchronous Response**:
```json
{
  "job_id": "job_xyz789abc123",
  "status": "pending",
  "papers": null,
  "total_fetched": 0,
  "errors": null
}
```

---

### Summarize

**POST** `/api/v1/summarize`

Generate summaries for papers using various summarization engines.

**Request Body**:
```json
{
  "query_id": "query_abc123def456",
  "engine": "langchain",
  "max_length": 150,
  "openai_model": "gpt-3.5-turbo",
  "temperature": 0.7
}
```

**Parameters**:
- `query_id` (string, optional): Query ID from search
- `dois` (array[string], optional): List of DOIs
- `engine` (string): Summarization engine (`openai`, `huggingface`, `langchain`)
- `max_length` (integer): Maximum summary length in words (default: 150)
- `include_abstract` (boolean): Include abstract in source (default: true)
- `openai_model` (string): OpenAI model name (default: "gpt-3.5-turbo")
- `temperature` (float): Temperature for generation (0-2, default: 0.7)

**Response**:
```json
{
  "summaries": [
    {
      "doi": "10.1101/2023.01.01.123456",
      "title": "Novel COVID-19 vaccination strategy",
      "summary": "This study presents a novel approach to COVID-19 vaccination that demonstrates improved efficacy...",
      "engine_used": "langchain",
      "word_count": 42
    }
  ],
  "total_processed": 10,
  "engine_used": "langchain",
  "errors": null
}
```

---

### Semantic Similarity

**POST** `/api/v1/semantic_similarity`

Rank papers by semantic similarity to a query text.

**Request Body**:
```json
{
  "query_text": "novel approaches to genome sequencing",
  "query_id": "query_abc123def456",
  "model_name": "all-MiniLM-L6-v2",
  "top_k": 10,
  "threshold": 0.5
}
```

**Parameters**:
- `query_text` (string, required): Text to compare against
- `query_id` (string, optional): Query ID from search
- `dois` (array[string], optional): List of DOIs to rank
- `model_name` (string): Sentence transformer model (default: "all-MiniLM-L6-v2")
- `top_k` (integer, optional): Return only top K results
- `threshold` (float, optional): Minimum similarity threshold (0-1)

**Response**:
```json
{
  "query_text": "novel approaches to genome sequencing",
  "ranked_papers": [
    {
      "doi": "10.1101/2023.01.01.123456",
      "title": "Advanced genome sequencing methodology",
      "similarity_score": 0.89,
      "rank": 1,
      "abstract": "We present an advanced approach..."
    },
    {
      "doi": "10.1101/2023.02.02.234567",
      "title": "Next-generation sequencing techniques",
      "similarity_score": 0.76,
      "rank": 2,
      "abstract": "This work describes..."
    }
  ],
  "total_compared": 50,
  "model_used": "all-MiniLM-L6-v2",
  "errors": null
}
```

---

### Export

**GET** `/api/v1/export`

Export papers in bulk (JSON or CSV format).

**Query Parameters**:
- `query_id` (string, required): Query ID to export
- `format` (string): Export format (`json` or `csv`, default: `json`)
- `include_abstracts` (boolean): Include abstracts (default: true)

**JSON Export**:
```bash
GET /api/v1/export?query_id=query_abc123def456&format=json
```

Response:
```json
{
  "papers": [...]
}
```

**CSV Export**:
```bash
GET /api/v1/export?query_id=query_abc123def456&format=csv
```

Response: CSV file download

---

### Job Status

**GET** `/api/v1/jobs/{job_id}`

Get status of an async job.

**Response**:
```json
{
  "job_id": "job_xyz789abc123",
  "status": "completed",
  "progress": 100.0,
  "result": {...},
  "error": null,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:31:00Z",
  "completed_at": "2024-01-15T10:31:00Z"
}
```

---

## Data Models

### PaperMetadata

```json
{
  "doi": "string",
  "title": "string",
  "authors": "string",
  "author_corresponding": "string",
  "author_corresponding_institution": "string",
  "date": "string",
  "version": "string",
  "category": "string",
  "type": "string",
  "license": "string",
  "published": "string",
  "server": "string",
  "abstract": "string",
  "link_page": "string",
  "link_pdf": "string"
}
```

### JobStatus

- `pending`: Job created, not yet started
- `in_progress`: Job currently running
- `completed`: Job finished successfully
- `failed`: Job failed with error

---

## Examples

### Example 1: Simple Search

```python
import requests

response = requests.post('http://localhost:8000/api/v1/search', json={
    'keywords': ['CRISPR', 'gene editing'],
    'recent_days': 30,
    'servers': ['biorxiv'],
    'max_results': 10
})

data = response.json()
print(f"Found {data['total_results']} papers")
for paper in data['papers']:
    print(f"- {paper['title']}")
```

### Example 2: Search, Summarize, and Export

```python
import requests

# 1. Search for papers
search_response = requests.post('http://localhost:8000/api/v1/search', json={
    'keywords': ['COVID-19', 'vaccine'],
    'start_date': '2023-01-01',
    'end_date': '2023-12-31',
    'servers': ['biorxiv', 'medrxiv'],
    'max_results': 20
})
query_id = search_response.json()['query_id']

# 2. Summarize papers
summarize_response = requests.post('http://localhost:8000/api/v1/summarize', json={
    'query_id': query_id,
    'engine': 'langchain',
    'max_length': 100
})
summaries = summarize_response.json()['summaries']

# 3. Export to CSV
export_response = requests.get(
    f'http://localhost:8000/api/v1/export?query_id={query_id}&format=csv'
)
with open('papers.csv', 'wb') as f:
    f.write(export_response.content)
```

### Example 3: Semantic Similarity Ranking

```python
import requests

# 1. Search for papers
search_response = requests.post('http://localhost:8000/api/v1/search', json={
    'keywords': ['genomics'],
    'recent_days': 60,
    'servers': ['biorxiv'],
    'max_results': 50
})
query_id = search_response.json()['query_id']

# 2. Rank by similarity
similarity_response = requests.post('http://localhost:8000/api/v1/semantic_similarity', json={
    'query_text': 'novel approaches to whole genome sequencing',
    'query_id': query_id,
    'top_k': 10
})

ranked_papers = similarity_response.json()['ranked_papers']
for paper in ranked_papers:
    print(f"{paper['rank']}. {paper['title']} (score: {paper['similarity_score']:.2f})")
```

### Example 4: Async Fetch

```python
import requests
import time

# 1. Start async fetch
fetch_response = requests.post('http://localhost:8000/api/v1/fetch', json={
    'query_id': 'query_abc123',
    'async_execution': True
})
job_id = fetch_response.json()['job_id']

# 2. Poll for completion
while True:
    status_response = requests.get(f'http://localhost:8000/api/v1/jobs/{job_id}')
    status = status_response.json()['status']

    if status == 'completed':
        result = status_response.json()['result']
        print(f"Fetch complete! Got {len(result)} papers")
        break
    elif status == 'failed':
        print(f"Fetch failed: {status_response.json()['error']}")
        break

    time.sleep(2)  # Wait 2 seconds before checking again
```

---

## Error Handling

All errors follow a consistent format:

```json
{
  "error": {
    "code": "404",
    "message": "Query ID not found",
    "details": null
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Common Error Codes

- **400 Bad Request**: Invalid request parameters
- **401 Unauthorized**: Missing or invalid authentication
- **404 Not Found**: Resource not found (e.g., invalid query_id)
- **422 Unprocessable Entity**: Validation error
- **500 Internal Server Error**: Server error

### Retry Logic

The API implements automatic retry logic for external API calls:
- **Retry count**: 3 attempts
- **Backoff factor**: 1 second
- **Retry on**: 500, 502, 503, 504 status codes

---

## Rate Limiting

Rate limiting is **disabled by default** but can be enabled in configuration.

When enabled:
- Default: 60 requests per minute
- Returns `429 Too Many Requests` when exceeded
- Response includes `Retry-After` header

---

## Best Practices

1. **Cache query results**: Use `query_id` to reference previous searches
2. **Use async execution** for large queries (>100 results)
3. **Implement exponential backoff** when polling job status
4. **Specify `max_results`** to limit response size
5. **Use semantic similarity** to filter and rank results
6. **Export to data lake**: Use CSV/JSON export for bulk storage

---

## Support

For issues, questions, or feature requests:
- GitHub Issues: [github.com/yourusername/medrxiv-langchain/issues](https://github.com/yourusername/medrxiv-langchain/issues)
- Documentation: [API_DOCUMENTATION.md](./API_DOCUMENTATION.md)
