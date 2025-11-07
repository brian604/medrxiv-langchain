# BioRxiv/MedRxiv API & LangChain Loader

A comprehensive solution for fetching, processing, and analyzing papers from BioRxiv and MedRxiv preprint servers.

**Two ways to use this package:**
1. **LangChain Loader** - Python library for fetching papers
2. **REST API** - Full-featured API backend for production deployments

## Features

### Core Features
- 🔍 Fetch papers from both BioRxiv and MedRxiv servers
- 🛠 Flexible query builder for constructing complex queries
- ⚡️ Parallel fetching from multiple servers
- 📅 Support for date range, most recent papers, and time window queries
- 🔄 Automatic retry mechanism for robust API calls
- 📄 Rich metadata including DOIs, versions, and direct links to PDFs

### API Features (NEW!)
- 🌐 **REST API** with FastAPI backend
- 🔎 **Advanced Search** with compound queries (AND/OR/NOT)
- 📝 **Summarization** using OpenAI, HuggingFace, or LangChain
- 🎯 **Semantic Similarity** ranking with sentence transformers
- 📊 **Export** to JSON/CSV for data lakes
- 🔐 **Optional Authentication** with API keys
- 📚 **Interactive API Docs** with Swagger/ReDoc

## Installation

### Basic Installation (LangChain Loader only)

```bash
pip install medrxiv-langchain
```

### API Installation (includes all features)

```bash
# Install with API dependencies
pip install -e ".[api]"

# Or install all dependencies
pip install -r requirements-api.txt
```

## Quick Start

### Option 1: Using the REST API

```bash
# Start the API server
python run_api.py

# Or with custom settings
python run_api.py --host 0.0.0.0 --port 8000 --workers 4

# Development mode (auto-reload)
python run_api.py --reload --log-level debug
```

Visit http://localhost:8000/docs for interactive API documentation.

#### API Example: Search and Export

```python
import requests

# Search for papers
response = requests.post('http://localhost:8000/api/v1/search', json={
    'keywords': ['COVID-19', 'vaccine'],
    'recent_days': 30,
    'servers': ['biorxiv', 'medrxiv'],
    'max_results': 100
})

query_id = response.json()['query_id']
print(f"Found {response.json()['total_results']} papers")

# Export to CSV
export = requests.get(
    f'http://localhost:8000/api/v1/export?query_id={query_id}&format=csv'
)
with open('papers.csv', 'wb') as f:
    f.write(export.content)
```

See [API_DOCUMENTATION.md](./API_DOCUMENTATION.md) for complete API reference.

### Option 2: Using as Python Library

## Usage

### Basic Usage

```python
from medrxiv_langchain import BioRxivLoader

# Simple loader for recent papers
loader = BioRxivLoader(
    query="30d",  # Last 30 days
    servers="biorxiv",  # or "medrxiv", or ["biorxiv", "medrxiv"]
    max_results=100
)

documents = loader.load()
```

### Using Enhanced QueryBuilder (NEW!)

The new `EnhancedQueryBuilder` supports compound queries with AND/OR/NOT logic, keywords, and categories:

```python
from medrxiv_langchain import EnhancedQueryBuilder, BioRxivLoader

# Complex compound query
query = (EnhancedQueryBuilder()
    .with_keywords(['CRISPR', 'gene editing'])
    .with_category('genetics')
    .date_range('2023-01-01', '2023-12-31')
    .from_servers(['biorxiv', 'medrxiv'])
    .build())

loader = BioRxivLoader(**query)
papers = loader.load()

# Search with keyword combinations
query = (EnhancedQueryBuilder()
    .with_keywords(['machine learning', 'genomics'])
    .last_month()
    .build())
```

### Using QueryBuilder (Legacy)

The QueryBuilder provides a fluent interface for constructing complex queries:

```python
from medrxiv_langchain import QueryBuilder, BioRxivLoader

# Create a query for papers from both servers in a date range
query = (QueryBuilder()
         .date_range("2024-01-01", "2024-02-17")
         .from_servers(["biorxiv", "medrxiv"])
         .build())

# Create loader with the query
loader = BioRxivLoader(query_builder=query, max_results=100)
docs = loader.load()

# Print results
for doc in docs:
    print(f"Title: {doc.metadata['title']}")
    print(f"Server: {doc.metadata['server']}")
    print(f"Date: {doc.metadata['date']}")
    print(f"PDF: {doc.metadata['link_pdf']}")
    print("---")
```

### Query Types

1. **Date Range Query**:
```python
query = (QueryBuilder()
         .date_range("2024-01-01", "2024-02-17")
         .from_servers(["biorxiv", "medrxiv"])
         .build())
```

2. **Most Recent Papers**:
```python
query = (QueryBuilder()
         .most_recent(50)  # Get 50 most recent papers
         .from_servers("medrxiv")
         .build())
```

3. **Last N Days**:
```python
query = (QueryBuilder()
         .last_days(7)  # Get papers from last week
         .from_servers(["biorxiv", "medrxiv"])
         .build())
```

### Document Metadata

Each document contains rich metadata:

- `title`: Paper title
- `authors`: List of authors
- `doi`: Digital Object Identifier
- `date`: Publication date
- `version`: Paper version
- `category`: Paper category
- `abstract`: Paper abstract
- `server`: Source server (biorxiv or medrxiv)
- `link_page`: URL to the paper's webpage
- `link_pdf`: URL to the paper's PDF
- `published`: Publication status
- `type`: Paper type
- `license`: Paper license

## Advanced Configuration

```python
loader = BioRxivLoader(
    query_builder=query,
    max_results=100,
    timeout=30,  # API request timeout in seconds
    max_workers=2  # Number of parallel workers for multi-server queries
)
```

## Error Handling

The loader includes robust error handling:
- Automatic retries for failed API requests
- Validation of input parameters
- Clear error messages for API and network issues

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Integration Examples

### 1. Paper Summarization with LangChain

```python
from langchain.chat_models import ChatOpenAI
from langchain.prompts import PromptTemplate
from medrxiv_langchain import QueryBuilder, BioRxivLoader

# Get recent AI papers from both servers
query = (QueryBuilder()
         .last_days(30)
         .from_servers(["biorxiv", "medrxiv"])
         .build())

loader = BioRxivLoader(query_builder=query, max_results=5)
documents = loader.load()

# Create a summarization chain
llm = ChatOpenAI(temperature=0.7)
prompt = PromptTemplate(
    input_variables=["title", "abstract"],
    template="""
    Summarize this scientific paper in 3-4 bullet points:
    Title: {title}
    Abstract: {abstract}
    
    Key Points:"""
)

chain = prompt | llm

# Generate summaries
for doc in documents:
    summary = chain.run(
        title=doc.metadata["title"],
        abstract=doc.page_content
    )
    print(f"\nPaper: {doc.metadata['title']}")
    print(f"Authors: {doc.metadata['authors']}")
    print(f"Link: {doc.metadata['link_page']}")
    print(f"Summary:\n{summary}")
```

## API-Specific Features

### Summarization

Generate summaries using multiple engines:

```python
import requests

# Summarize papers using LangChain
response = requests.post('http://localhost:8000/api/v1/summarize', json={
    'query_id': 'query_abc123',
    'engine': 'langchain',  # or 'openai', 'huggingface'
    'max_length': 150
})

summaries = response.json()['summaries']
for summary in summaries:
    print(f"{summary['title']}: {summary['summary']}")
```

### Semantic Similarity Ranking

Rank papers by semantic similarity to a query:

```python
import requests

# Rank papers by relevance
response = requests.post('http://localhost:8000/api/v1/semantic_similarity', json={
    'query_text': 'novel approaches to genome sequencing',
    'query_id': 'query_abc123',
    'top_k': 10,
    'threshold': 0.5
})

ranked = response.json()['ranked_papers']
for paper in ranked:
    print(f"{paper['rank']}. {paper['title']} (score: {paper['similarity_score']:.2f})")
```

### Data Lake Export

Export papers for bulk storage and analytics:

```bash
# Export as JSON
curl "http://localhost:8000/api/v1/export?query_id=query_abc123&format=json" > papers.json

# Export as CSV
curl "http://localhost:8000/api/v1/export?query_id=query_abc123&format=csv" > papers.csv
```

### Health Monitoring

Check API and server status:

```python
import requests

response = requests.get('http://localhost:8000/api/v1/health')
health = response.json()

print(f"API Status: {health['status']}")
for server in health['servers']:
    print(f"- {server['server']}: {server['status']} ({server['response_time_ms']:.0f}ms)")
```

## Best Practices

1. **Rate Limiting**: The loader includes automatic retries, but be mindful of API rate limits:
   ```python
   loader = BioRxivLoader(
       query_builder=query,
       timeout=30,
       max_workers=2  # Limit parallel requests
   )
   ```

2. **Error Handling**: Always handle potential errors:
   ```python
   try:
       loader = BioRxivLoader(query_builder=query)
       documents = loader.load()
   except ValueError as e:
       print(f"Invalid parameters: {e}")
   except ConnectionError as e:
       print(f"API connection error: {e}")
   ```

3. **Efficient Queries**: Use specific date ranges or limits to avoid fetching too much data:
   ```python
   # Good: Specific date range
   query = QueryBuilder().date_range("2024-01-01", "2024-02-17").build()
   
   # Good: Limited recent papers
   query = QueryBuilder().most_recent(100).build()
   
   # Avoid: Very large date ranges without limits
   # query = QueryBuilder().date_range("2000-01-01", "2024-02-17").build()
   ```

4. **Metadata Usage**: Make use of rich metadata for better analysis:
   ```python
   for doc in documents:
       # Check if paper is published
       if doc.metadata['published']:
           print(f"Published paper: {doc.metadata['title']}")
           
       # Get PDF link for latest version
       pdf_link = doc.metadata['link_pdf']
       
       # Check paper category
       if doc.metadata['category'] == 'bioinformatics':
           print(f"Bioinformatics paper: {doc.metadata['title']}")
   ```
