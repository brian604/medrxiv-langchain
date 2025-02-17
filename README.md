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
