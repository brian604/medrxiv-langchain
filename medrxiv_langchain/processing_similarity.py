"""
Semantic similarity engine for ranking BioRxiv/MedRxiv papers.
Uses sentence transformers for embedding-based similarity.
"""

from typing import List, Dict, Tuple, Optional
import logging
import numpy as np

logger = logging.getLogger(__name__)


class SemanticSimilarityEngine:
    """
    Engine for computing semantic similarity between query text and papers.
    Uses sentence transformers for embedding generation.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize semantic similarity engine.

        Args:
            model_name: Name of sentence transformer model
                Common models:
                - all-MiniLM-L6-v2 (fast, good quality, 384 dims)
                - all-mpnet-base-v2 (slower, better quality, 768 dims)
                - multi-qa-MiniLM-L6-cos-v1 (optimized for Q&A)
        """
        self.model_name = model_name
        self.model = None

    def _initialize_model(self):
        """Lazy initialization of the sentence transformer model."""
        if self.model is None:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info(f"Loading sentence transformer model: {self.model_name}")
                self.model = SentenceTransformer(self.model_name)
                logger.info(f"Model loaded successfully")
            except ImportError:
                logger.error(
                    "sentence-transformers package not installed. "
                    "Install with: uv pip install sentence-transformers"
                )
                raise
            except Exception as e:
                logger.error(f"Error loading model {self.model_name}: {e}")
                raise

    def compute_similarity(
        self,
        query_text: str,
        documents: List[str]
    ) -> List[float]:
        """
        Compute similarity scores between query and documents.

        Args:
            query_text: Query text to compare against
            documents: List of document texts

        Returns:
            List of similarity scores (0-1) in same order as documents
        """
        self._initialize_model()

        try:
            from sentence_transformers import util

            # Encode query
            query_embedding = self.model.encode(query_text, convert_to_tensor=True)

            # Encode documents
            doc_embeddings = self.model.encode(documents, convert_to_tensor=True)

            # Compute cosine similarities
            similarities = util.cos_sim(query_embedding, doc_embeddings)[0]

            # Convert to list of floats
            return similarities.cpu().numpy().tolist()

        except Exception as e:
            logger.error(f"Error computing similarity: {e}")
            # Return zeros if computation fails
            return [0.0] * len(documents)

    def rank_papers(
        self,
        query_text: str,
        papers: List[Dict],
        text_field: str = "abstract",
        top_k: Optional[int] = None,
        threshold: Optional[float] = None
    ) -> List[Tuple[Dict, float]]:
        """
        Rank papers by semantic similarity to query.

        Args:
            query_text: Query text
            papers: List of paper dictionaries
            text_field: Field in paper dict to use for comparison (default: 'abstract')
            top_k: Return only top K results
            threshold: Minimum similarity threshold

        Returns:
            List of (paper, score) tuples, sorted by score (highest first)
        """
        if not papers:
            return []

        # Extract text from papers
        documents = []
        valid_papers = []

        for paper in papers:
            text = paper.get(text_field, "")
            if text:
                documents.append(text)
                valid_papers.append(paper)
            else:
                logger.warning(
                    f"Paper {paper.get('doi', 'unknown')} missing {text_field} field"
                )

        if not documents:
            logger.warning("No valid documents found for ranking")
            return []

        # Compute similarities
        similarities = self.compute_similarity(query_text, documents)

        # Combine papers with scores
        results = list(zip(valid_papers, similarities))

        # Sort by score (descending)
        results.sort(key=lambda x: x[1], reverse=True)

        # Apply threshold if specified
        if threshold is not None:
            results = [(paper, score) for paper, score in results if score >= threshold]

        # Apply top_k if specified
        if top_k is not None:
            results = results[:top_k]

        return results

    def rank_papers_multi_field(
        self,
        query_text: str,
        papers: List[Dict],
        text_fields: List[str] = ["title", "abstract"],
        weights: Optional[List[float]] = None,
        top_k: Optional[int] = None,
        threshold: Optional[float] = None
    ) -> List[Tuple[Dict, float, Dict[str, float]]]:
        """
        Rank papers using multiple text fields with optional weighting.

        Args:
            query_text: Query text
            papers: List of paper dictionaries
            text_fields: List of fields to use for comparison
            weights: Optional weights for each field (must sum to 1.0)
            top_k: Return only top K results
            threshold: Minimum similarity threshold

        Returns:
            List of (paper, combined_score, field_scores) tuples
        """
        if not papers:
            return []

        # Default to equal weights
        if weights is None:
            weights = [1.0 / len(text_fields)] * len(text_fields)
        elif len(weights) != len(text_fields):
            raise ValueError("Number of weights must match number of text fields")
        elif not np.isclose(sum(weights), 1.0):
            raise ValueError("Weights must sum to 1.0")

        # Compute similarities for each field
        field_similarities = {}

        for field in text_fields:
            documents = []
            valid_indices = []

            for i, paper in enumerate(papers):
                text = paper.get(field, "")
                if text:
                    documents.append(text)
                    valid_indices.append(i)

            if documents:
                similarities = self.compute_similarity(query_text, documents)
                # Map back to original paper indices
                field_sims = [0.0] * len(papers)
                for idx, sim in zip(valid_indices, similarities):
                    field_sims[idx] = sim
                field_similarities[field] = field_sims
            else:
                field_similarities[field] = [0.0] * len(papers)

        # Combine scores with weights
        results = []
        for i, paper in enumerate(papers):
            field_scores = {
                field: field_similarities[field][i]
                for field in text_fields
            }

            combined_score = sum(
                field_scores[field] * weight
                for field, weight in zip(text_fields, weights)
            )

            results.append((paper, combined_score, field_scores))

        # Sort by combined score (descending)
        results.sort(key=lambda x: x[1], reverse=True)

        # Apply threshold if specified
        if threshold is not None:
            results = [
                (paper, score, field_scores)
                for paper, score, field_scores in results
                if score >= threshold
            ]

        # Apply top_k if specified
        if top_k is not None:
            results = results[:top_k]

        return results


# ============================================================================
# Convenience Functions
# ============================================================================

def rank_papers_by_similarity(
    query_text: str,
    papers: List[Dict],
    model_name: str = "all-MiniLM-L6-v2",
    text_field: str = "abstract",
    top_k: Optional[int] = None,
    threshold: Optional[float] = None
) -> List[Tuple[Dict, float]]:
    """
    Convenience function to rank papers by semantic similarity.

    Args:
        query_text: Query text
        papers: List of paper dictionaries
        model_name: Sentence transformer model name
        text_field: Field to use for comparison
        top_k: Return only top K results
        threshold: Minimum similarity threshold

    Returns:
        List of (paper, score) tuples, sorted by score (highest first)

    Example:
        >>> papers = [
        ...     {"doi": "10.1101/123", "abstract": "Study on COVID vaccines..."},
        ...     {"doi": "10.1101/456", "abstract": "Cancer research..."}
        ... ]
        >>> ranked = rank_papers_by_similarity(
        ...     "COVID-19 vaccination efficacy",
        ...     papers,
        ...     top_k=10
        ... )
        >>> for paper, score in ranked:
        ...     print(f"{paper['doi']}: {score:.3f}")
    """
    engine = SemanticSimilarityEngine(model_name=model_name)
    return engine.rank_papers(
        query_text=query_text,
        papers=papers,
        text_field=text_field,
        top_k=top_k,
        threshold=threshold
    )


def compute_paper_similarity_matrix(
    papers: List[Dict],
    model_name: str = "all-MiniLM-L6-v2",
    text_field: str = "abstract"
) -> np.ndarray:
    """
    Compute pairwise similarity matrix for a set of papers.

    Args:
        papers: List of paper dictionaries
        model_name: Sentence transformer model name
        text_field: Field to use for comparison

    Returns:
        NxN similarity matrix where N = len(papers)

    Example:
        >>> papers = [...]
        >>> sim_matrix = compute_paper_similarity_matrix(papers)
        >>> # Find papers similar to first paper
        >>> similar_indices = np.argsort(sim_matrix[0])[::-1][1:6]  # Top 5 (excluding self)
    """
    engine = SemanticSimilarityEngine(model_name=model_name)
    engine._initialize_model()

    # Extract texts
    documents = [paper.get(text_field, "") for paper in papers]

    try:
        from sentence_transformers import util

        # Encode all documents
        embeddings = engine.model.encode(documents, convert_to_tensor=True)

        # Compute pairwise similarities
        similarity_matrix = util.cos_sim(embeddings, embeddings)

        return similarity_matrix.cpu().numpy()

    except Exception as e:
        logger.error(f"Error computing similarity matrix: {e}")
        # Return identity matrix if computation fails
        n = len(papers)
        return np.eye(n)
