from typing import List, Any, Dict, Optional, Literal
import requests
from datetime import datetime
import pandas as pd
from langchain.document_loaders.base import BaseLoader
from langchain.schema import Document
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import urllib.parse

class BioRxivLoader(BaseLoader):
    """
    Loader for fetching documents from BioRxiv and MedRxiv.
    
    This loader supports both BioRxiv and MedRxiv repositories with robust error handling,
    automatic retries, comprehensive metadata extraction, and sorting options.
    """
    
    def __init__(
        self,
        query: str,
        start_date: str = "2020-01-01",
        end_date: str = "2025-12-31",
        server: str = "biorxiv",
        max_results: Optional[int] = None,
        timeout: int = 30,
        sort_by: Literal["date", "rel"] = "date"
    ):
        """
        Initialize the BioRxivLoader.

        Args:
            query (str): The search query.
            start_date (str): The start date for the search (format: YYYY-MM-DD).
            end_date (str): The end date for the search (format: YYYY-MM-DD).
            server (str): The server to query from ('biorxiv' or 'medrxiv').
            max_results (Optional[int]): Maximum number of results to fetch. None for all available.
            timeout (int): Timeout for API requests in seconds.
            sort_by (str): Sort results by 'date' (newest first) or 'rel' (relevance).
        """
        self.query = query
        self.start_date = self._validate_date(start_date)
        self.end_date = self._validate_date(end_date)
        self.server = self._validate_server(server)
        self.max_results = max_results
        self.timeout = timeout
        self.sort_by = self._validate_sort_by(sort_by)
        
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

    def _validate_sort_by(self, sort_by: str) -> str:
        """Validate sort_by parameter."""
        sort_by = sort_by.lower()
        if sort_by not in ["date", "rel"]:
            raise ValueError("sort_by must be either 'date' or 'rel'")
        return sort_by

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

    def _build_api_url(self, cursor: str = "0") -> str:
        """Build the API URL with proper encoding."""
        base_url = "https://api.biorxiv.org/"
        path = f"details/{self.server}/{self.start_date}/{self.end_date}/{cursor}/{self.sort_by}"
        return urllib.parse.urljoin(base_url, path)

    def _fetch_data(self, url: str) -> Dict[str, Any]:
        """Fetch data from the API with error handling."""
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            if "Error : (2002) Connection refused" in response.text:
                raise ConnectionError(
                    "API connection refused. Please try again later."
                )
                
            data = response.json()
            if not data.get("collection"):
                if "no posts found" in str(data).lower():
                    return {"collection": []}
                raise ValueError(
                    "Unexpected API response format. Please check your query parameters."
                )
                
            return data
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Failed to fetch data from API: {str(e)}") from e

    def _process_item(self, item: Dict[str, Any]) -> Document:
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
            "server": self.server,
            "link_page": f"https://www.{self.server}.org/content/{item.get('doi', '')}v{item.get('version', '')}",
            "link_pdf": f"https://www.{self.server}.org/content/{item.get('doi', '')}v{item.get('version', '')}.full.pdf"
        }
        
        return Document(page_content=content, metadata=metadata)

    def load(self) -> List[Document]:
        """
        Fetch results from the BioRxiv/MedRxiv API and convert them into Document objects.

        Returns:
            List[Document]: A list of documents containing the article content and metadata.

        Raises:
            ConnectionError: If there are network connectivity issues
            ValueError: If there are problems with the input parameters or API response
        """
        documents: List[Document] = []
        cursor = "0"
        total_fetched = 0
        
        while True:
            url = self._build_api_url(cursor)
            data = self._fetch_data(url)
            
            # Process items
            for item in data.get("collection", []):
                documents.append(self._process_item(item))
                total_fetched += 1
                
                if self.max_results and total_fetched >= self.max_results:
                    return documents
            
            # Check if we should continue fetching
            messages = data.get("messages", [])
            if not messages or messages[0].get("cursor") == cursor:
                break
            cursor = messages[0].get("cursor")
        
        return documents
