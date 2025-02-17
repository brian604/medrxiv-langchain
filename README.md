# MedRxiv Langchain Loader

A LangChain document loader for fetching and processing papers from BioRxiv and MedRxiv preprint servers.

## Features

- 🔍 Fetch papers from both BioRxiv and MedRxiv servers
- 🛠 Flexible query builder for constructing complex queries
- ⚡️ Parallel fetching from multiple servers
- 📅 Support for date range, most recent papers, and time window queries
- 🔄 Automatic retry mechanism for robust API calls
- 📄 Rich metadata including DOIs, versions, and direct links to PDFs

## Installation

```bash
pip install medrxiv-langchain
```

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

### Using QueryBuilder

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
