from typing import List, Any, Dict, Optional, Union, Literal
import requests
from datetime import datetime, timedelta
import pandas as pd
from langchain.document_loaders.base import BaseLoader
from langchain.schema import Document
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
import itertools

class QueryBuilder:
    """Builder class for constructing BioRxiv/MedRxiv queries."""
    
    def __init__(self):
        self._start_date: Optional[str] = None
        self._end_date: Optional[str] = None
        self._recent_papers: Optional[int] = None
        self._recent_days: Optional[int] = None
        self._servers: List[str] = ["biorxiv"]  # Default to biorxiv
        
    def date_range(self, start_date: str, end_date: str) -> 'QueryBuilder':
        """Set date range for the query."""
        self._validate_date(start_date)
        self._validate_date(end_date)
        self._start_date = start_date
        self._end_date = end_date
        return self
    
    def most_recent(self, count: int) -> 'QueryBuilder':
        """Get most recent N papers."""
        if count <= 0:
            raise ValueError("Count must be positive")
        self._recent_papers = count
        return self
    
    def last_days(self, days: int) -> 'QueryBuilder':
        """Get papers from last N days."""
        if days <= 0:
            raise ValueError("Days must be positive")
        self._recent_days = days
        return self
    
    def from_servers(self, servers: Union[str, List[str]]) -> 'QueryBuilder':
        """Specify which servers to query (biorxiv and/or medrxiv)."""
        if isinstance(servers, str):
            servers = [servers]
        
        for server in servers:
            if server.lower() not in ["biorxiv", "medrxiv"]:
                raise ValueError("Server must be either 'biorxiv' or 'medrxiv'")
        
        self._servers = [s.lower() for s in servers]
        return self
    
    def build(self) -> Dict[str, Any]:
        """Build the query parameters."""
        if sum(x is not None for x in [self._recent_papers, self._recent_days, self._start_date]) > 1:
            raise ValueError("Cannot combine different query types. Use either date_range, most_recent, or last_days.")
        
        query: Optional[str] = None
        start_date: Optional[str] = None
        end_date: Optional[str] = None
        
        if self._recent_papers is not None:
            query = str(self._recent_papers)
        elif self._recent_days is not None:
            query = f"{self._recent_days}d"
        else:
            start_date = self._start_date or (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            end_date = self._end_date or datetime.now().strftime("%Y-%m-%d")
        
        return {
            "query": query,
            "start_date": start_date,
            "end_date": end_date,
            "servers": self._servers
        }
    
    @staticmethod
    def _validate_date(date_str: str) -> None:
        """Validate date format."""
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError as e:
            raise ValueError(
                f"Invalid date format: {date_str}. Date must be in YYYY-MM-DD format"
            ) from e


class BioRxivLoader(BaseLoader):
    """
    Loader for fetching documents from BioRxiv and MedRxiv.
    
    This loader supports both BioRxiv and MedRxiv repositories with robust error handling,
    automatic retries, and comprehensive metadata extraction.
    """
    
    def __init__(
        self,
        query_builder: Optional[Union[QueryBuilder, Dict[str, Any]]] = None,
        query: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        servers: Union[str, List[str]] = "biorxiv",
        max_results: Optional[int] = None,
        timeout: int = 30,
        max_workers: int = 2
    ):
        """
        Initialize the BioRxivLoader.

        Args:
            query_builder (Optional[Union[QueryBuilder, Dict[str, Any]]]): QueryBuilder instance or built query dict
            query (Optional[str]): Simple query string (ignored if query_builder is provided)
            start_date (Optional[str]): Start date (ignored if query_builder is provided)
            end_date (Optional[str]): End date (ignored if query_builder is provided)
            servers (Union[str, List[str]]): Server(s) to query from
            max_results (Optional[int]): Maximum number of results to fetch
            timeout (int): Timeout for API requests in seconds
            max_workers (int): Maximum number of parallel workers for multiple servers
        """
        if query_builder:
            # Handle both QueryBuilder instance and built query dict
            params = query_builder.build() if hasattr(query_builder, 'build') else query_builder
            self.query = params["query"]
            self.start_date = params["start_date"]
            self.end_date = params["end_date"]
            self.servers = params["servers"]
        else:
            self.query = query
            self.start_date = start_date
            self.end_date = end_date
            self.servers = [servers] if isinstance(servers, str) else servers
            self.servers = [s.lower() for s in self.servers]
        
        self.max_results = max_results
        self.timeout = timeout
        self.max_workers = max_workers
        
        # Validate servers
        for server in self.servers:
            if server not in ["biorxiv", "medrxiv"]:
                raise ValueError("Server must be either 'biorxiv' or 'medrxiv'")
        
        # Setup retry strategy
        self.session = self._setup_session()

    def _validate_date(self, date_str: str) -> str:
        """Validate date format."""
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            return date_str
        except ValueError as e:
            raise ValueError(
                f"Invalid date format: {date_str}. Date must be in YYYY-MM-DD format"
            ) from e

    def _validate_server(self, server: str) -> str:
        """Validate server selection."""
        server = server.lower()
        if server not in ["biorxiv", "medrxiv"]:
            raise ValueError("Server must be either 'biorxiv' or 'medrxiv'")
        return server

    def _setup_session(self) -> requests.Session:
        """Setup requests session with retry strategy."""
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session = requests.Session()
        session.mount("https://", adapter)
        return session

    def _build_api_url(self, server: str, cursor: str = "0") -> str:
        """Build the API URL according to the query type."""
        base_url = "https://api.biorxiv.org/details/"
        
        # Determine the interval based on query type
        if self.query and (self.query.isdigit() or self.query.endswith('d')):
            # For N most recent papers or N days, use the query directly as interval
            interval = self.query
        elif self.start_date and self.end_date:
            # For date range, combine dates with '/'
            interval = f"{self.start_date}/{self.end_date}"
        else:
            # Default to last 30 days
            interval = "30d"
        
        # Format: https://api.biorxiv.org/details/[server]/[interval]/[cursor]
        path = f"{server}/{interval}/{cursor}/json"
        url = urllib.parse.urljoin(base_url, path)
        return url

    def _fetch_data(self, url: str) -> Dict[str, Any]:
        """Fetch data from the API with error handling."""
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            
            # Check if we got a valid response with collection
            if not isinstance(data, dict):
                raise ValueError(f"Invalid API response format. Expected dict, got {type(data)}")
            
            if "collection" not in data:
                if "messages" in data and data["messages"]:
                    error_msg = data["messages"][0].get("error", "Unknown error")
                    raise ValueError(f"API error: {error_msg}")
                raise ValueError("API response missing 'collection' field")
            
            return data
            
        except requests.exceptions.JSONDecodeError as e:
            raise ValueError(
                f"Failed to parse API response as JSON: {str(e)}\n"
                f"Response text: {response.text[:500]}..."
            ) from e
            
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Failed to fetch data from API: {str(e)}") from e

    def _process_item(self, item: Dict[str, Any], server: str) -> Document:
        """Process a single API response item into a Document."""
        # Extract content (combine abstract and title for better context)
        content = f"Title: {item.get('title', '')}\n\nAbstract: {item.get('abstract', '')}"
        
        # Prepare comprehensive metadata
        metadata = {
            "title": item.get("title", ""),
            "authors": item.get("authors", ""),
            "author_corresponding": item.get("author_corresponding", ""),
            "author_corresponding_institution": item.get("author_corresponding_institution", ""),
            "doi": item.get("doi", ""),
            "version": item.get("version", ""),
            "date": item.get("date", ""),
            "date_published": item.get("date", ""),
            "category": item.get("category", ""),
            "type": item.get("type", ""),
            "license": item.get("license", ""),
            "published": item.get("published", ""),
            "server": server,
            "link_page": f"https://www.{server}.org/content/{item.get('doi', '')}v{item.get('version', '')}",
            "link_pdf": f"https://www.{server}.org/content/{item.get('doi', '')}v{item.get('version', '')}.full.pdf"
        }
        
        return Document(page_content=content, metadata=metadata)

    def load(self) -> List[Document]:
        """
        Fetch results from the BioRxiv/MedRxiv API and convert them into Document objects.
        If multiple servers are specified, fetches from all servers in parallel.

        Returns:
            List[Document]: A list of documents containing the article content and metadata.

        Raises:
            ConnectionError: If there are network connectivity issues
            ValueError: If there are problems with the input parameters or API response
        """
        if len(self.servers) == 1:
            return self._load_from_server(self.servers[0])
        
        # Fetch from multiple servers in parallel
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            results = list(executor.map(self._load_from_server, self.servers))
        
        # Combine and sort results by date
        combined_docs = list(itertools.chain.from_iterable(results))
        combined_docs.sort(key=lambda x: x.metadata["date"], reverse=True)
        
        # Apply max_results after combining
        if self.max_results:
            combined_docs = combined_docs[:self.max_results]
        
        return combined_docs
    
    def _load_from_server(self, server: str) -> List[Document]:
        """Load documents from a specific server."""
        documents: List[Document] = []
        cursor = "0"
        total_fetched = 0
        
        while True:
            url = self._build_api_url(server, cursor)
            data = self._fetch_data(url)
            
            # Process items
            for item in data.get("collection", []):
                documents.append(self._process_item(item, server))
                total_fetched += 1
                
                if self.max_results and total_fetched >= self.max_results:
                    return documents
            
            # Check if we should continue fetching
            messages = data.get("messages", [])
            if not messages or messages[0].get("cursor") == cursor:
                break
            cursor = messages[0].get("cursor")
        
        return documents
