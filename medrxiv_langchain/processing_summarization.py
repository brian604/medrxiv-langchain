"""
Summarization engine for BioRxiv/MedRxiv papers.
Supports multiple backends: OpenAI, HuggingFace, and LangChain.
"""

from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)


class SummarizationEngine(ABC):
    """Abstract base class for summarization engines."""

    @abstractmethod
    def summarize(self, text: str, max_length: int = 150) -> str:
        """
        Summarize text.

        Args:
            text: Text to summarize
            max_length: Maximum summary length in words

        Returns:
            Summary text
        """
        pass

    @abstractmethod
    def summarize_batch(self, texts: List[str], max_length: int = 150) -> List[str]:
        """
        Summarize multiple texts.

        Args:
            texts: List of texts to summarize
            max_length: Maximum summary length in words

        Returns:
            List of summaries
        """
        pass


class LangChainSummarizer(SummarizationEngine):
    """
    LangChain-based summarization using load_summarize_chain.
    This is a local option that doesn't require API keys.
    """

    def __init__(self, model_name: str = "gpt-3.5-turbo", temperature: float = 0.7):
        """
        Initialize LangChain summarizer.

        Args:
            model_name: LLM model name (if using LLM backend)
            temperature: Temperature for generation
        """
        self.model_name = model_name
        self.temperature = temperature

    def summarize(self, text: str, max_length: int = 150) -> str:
        """Summarize a single text."""
        try:
            from langchain.text_splitter import RecursiveCharacterTextSplitter
            from langchain.chains.summarize import load_summarize_chain
            from langchain.schema import Document
            from langchain.llms import OpenAI

            # Split text if too long
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=4000,
                chunk_overlap=200
            )

            # Create documents
            docs = [Document(page_content=text)]

            # Initialize LLM
            llm = OpenAI(temperature=self.temperature, model_name=self.model_name)

            # Create summarization chain
            chain = load_summarize_chain(llm, chain_type="map_reduce")

            # Generate summary
            summary = chain.run(docs)

            # Truncate to max_length words
            words = summary.split()
            if len(words) > max_length:
                summary = ' '.join(words[:max_length]) + '...'

            return summary.strip()

        except ImportError as e:
            logger.error(f"Missing dependencies for LangChain summarization: {e}")
            # Fallback to simple truncation
            return self._simple_truncate(text, max_length)
        except Exception as e:
            logger.error(f"Error in LangChain summarization: {e}")
            return self._simple_truncate(text, max_length)

    def summarize_batch(self, texts: List[str], max_length: int = 150) -> List[str]:
        """Summarize multiple texts."""
        return [self.summarize(text, max_length) for text in texts]

    @staticmethod
    def _simple_truncate(text: str, max_length: int) -> str:
        """Simple fallback: truncate to max_length words."""
        words = text.split()
        if len(words) > max_length:
            return ' '.join(words[:max_length]) + '...'
        return text


class OpenAISummarizer(SummarizationEngine):
    """OpenAI-based summarization using GPT models."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-3.5-turbo", temperature: float = 0.7):
        """
        Initialize OpenAI summarizer.

        Args:
            api_key: OpenAI API key
            model: Model name (gpt-3.5-turbo, gpt-4, etc.)
            temperature: Temperature for generation
        """
        self.api_key = api_key
        self.model = model
        self.temperature = temperature

    def summarize(self, text: str, max_length: int = 150) -> str:
        """Summarize a single text using OpenAI."""
        try:
            from openai import OpenAI

            client = OpenAI(api_key=self.api_key)

            prompt = f"""Summarize the following scientific abstract in approximately {max_length} words.
Focus on the main findings and significance:

{text}

Summary:"""

            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a scientific summarization assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                max_tokens=max_length * 2  # Approximate token count
            )

            summary = response.choices[0].message.content.strip()
            return summary

        except ImportError:
            logger.error("OpenAI package not installed. Install with: uv pip install openai")
            return self._simple_truncate(text, max_length)
        except Exception as e:
            logger.error(f"Error in OpenAI summarization: {e}")
            return self._simple_truncate(text, max_length)

    def summarize_batch(self, texts: List[str], max_length: int = 150) -> List[str]:
        """Summarize multiple texts."""
        return [self.summarize(text, max_length) for text in texts]

    @staticmethod
    def _simple_truncate(text: str, max_length: int) -> str:
        """Simple fallback: truncate to max_length words."""
        words = text.split()
        if len(words) > max_length:
            return ' '.join(words[:max_length]) + '...'
        return text


class HuggingFaceSummarizer(SummarizationEngine):
    """HuggingFace-based summarization using transformers."""

    def __init__(self, model_name: str = "facebook/bart-large-cnn"):
        """
        Initialize HuggingFace summarizer.

        Args:
            model_name: HuggingFace model name for summarization
        """
        self.model_name = model_name
        self.pipeline = None

    def _initialize_pipeline(self):
        """Lazy initialization of the summarization pipeline."""
        if self.pipeline is None:
            try:
                from transformers import pipeline
                self.pipeline = pipeline("summarization", model=self.model_name)
            except ImportError:
                logger.error("Transformers package not installed. Install with: uv pip install transformers torch")
                raise
            except Exception as e:
                logger.error(f"Error initializing HuggingFace pipeline: {e}")
                raise

    def summarize(self, text: str, max_length: int = 150) -> str:
        """Summarize a single text using HuggingFace."""
        try:
            self._initialize_pipeline()

            # BART has a max input length of 1024 tokens
            # Truncate if needed
            max_input_length = 1000
            words = text.split()
            if len(words) > max_input_length:
                text = ' '.join(words[:max_input_length])

            summary = self.pipeline(
                text,
                max_length=max_length,
                min_length=30,
                do_sample=False
            )

            return summary[0]['summary_text'].strip()

        except ImportError:
            logger.error("Transformers not available. Falling back to simple truncation.")
            return self._simple_truncate(text, max_length)
        except Exception as e:
            logger.error(f"Error in HuggingFace summarization: {e}")
            return self._simple_truncate(text, max_length)

    def summarize_batch(self, texts: List[str], max_length: int = 150) -> List[str]:
        """Summarize multiple texts."""
        try:
            self._initialize_pipeline()

            # Truncate texts if needed
            max_input_length = 1000
            truncated_texts = []
            for text in texts:
                words = text.split()
                if len(words) > max_input_length:
                    text = ' '.join(words[:max_input_length])
                truncated_texts.append(text)

            summaries = self.pipeline(
                truncated_texts,
                max_length=max_length,
                min_length=30,
                do_sample=False,
                batch_size=8
            )

            return [s['summary_text'].strip() for s in summaries]

        except Exception as e:
            logger.error(f"Error in batch summarization: {e}")
            return [self._simple_truncate(text, max_length) for text in texts]

    @staticmethod
    def _simple_truncate(text: str, max_length: int) -> str:
        """Simple fallback: truncate to max_length words."""
        words = text.split()
        if len(words) > max_length:
            return ' '.join(words[:max_length]) + '...'
        return text


class SummarizationFactory:
    """Factory for creating summarization engines."""

    @staticmethod
    def create_engine(
        engine_type: str,
        **kwargs
    ) -> SummarizationEngine:
        """
        Create a summarization engine.

        Args:
            engine_type: Type of engine ('openai', 'huggingface', 'langchain')
            **kwargs: Engine-specific parameters

        Returns:
            SummarizationEngine instance

        Raises:
            ValueError: If engine_type is not supported
        """
        engine_type = engine_type.lower()

        if engine_type == 'openai':
            return OpenAISummarizer(
                api_key=kwargs.get('api_key'),
                model=kwargs.get('model', 'gpt-3.5-turbo'),
                temperature=kwargs.get('temperature', 0.7)
            )
        elif engine_type == 'huggingface':
            return HuggingFaceSummarizer(
                model_name=kwargs.get('model_name', 'facebook/bart-large-cnn')
            )
        elif engine_type == 'langchain':
            return LangChainSummarizer(
                model_name=kwargs.get('model_name', 'gpt-3.5-turbo'),
                temperature=kwargs.get('temperature', 0.7)
            )
        else:
            raise ValueError(
                f"Unsupported engine type: {engine_type}. "
                f"Choose from: 'openai', 'huggingface', 'langchain'"
            )


# ============================================================================
# Convenience Functions
# ============================================================================

def summarize_paper(
    abstract: str,
    engine: str = 'langchain',
    max_length: int = 150,
    **engine_kwargs
) -> str:
    """
    Summarize a paper abstract.

    Args:
        abstract: Paper abstract text
        engine: Summarization engine ('openai', 'huggingface', 'langchain')
        max_length: Maximum summary length in words
        **engine_kwargs: Engine-specific parameters

    Returns:
        Summary text
    """
    summarizer = SummarizationFactory.create_engine(engine, **engine_kwargs)
    return summarizer.summarize(abstract, max_length=max_length)


def summarize_papers_batch(
    abstracts: List[str],
    engine: str = 'langchain',
    max_length: int = 150,
    **engine_kwargs
) -> List[str]:
    """
    Summarize multiple paper abstracts.

    Args:
        abstracts: List of paper abstracts
        engine: Summarization engine ('openai', 'huggingface', 'langchain')
        max_length: Maximum summary length in words
        **engine_kwargs: Engine-specific parameters

    Returns:
        List of summaries
    """
    summarizer = SummarizationFactory.create_engine(engine, **engine_kwargs)
    return summarizer.summarize_batch(abstracts, max_length=max_length)
