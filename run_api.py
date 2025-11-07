#!/usr/bin/env python3
"""
Startup script for the BioRxiv/MedRxiv API server.
"""

import uvicorn
import argparse
import logging
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Run BioRxiv/MedRxiv API server")
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to (default: 8000)"
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development"
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="info",
        choices=["debug", "info", "warning", "error", "critical"],
        help="Logging level (default: info)"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes (default: 1)"
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    logger = logging.getLogger(__name__)

    logger.info(f"Starting BioRxiv/MedRxiv API server...")
    logger.info(f"Host: {args.host}")
    logger.info(f"Port: {args.port}")
    logger.info(f"Workers: {args.workers}")
    logger.info(f"Log level: {args.log_level}")

    if args.reload:
        logger.info("Auto-reload enabled (development mode)")

    # Check if optional dependencies are installed
    try:
        import sentence_transformers
        logger.info("✓ sentence-transformers available")
    except ImportError:
        logger.warning("✗ sentence-transformers not available (semantic similarity will not work)")

    try:
        import openai
        logger.info("✓ openai available")
    except ImportError:
        logger.warning("✗ openai not available (OpenAI summarization will not work)")

    try:
        import transformers
        logger.info("✓ transformers available")
    except ImportError:
        logger.warning("✗ transformers not available (HuggingFace summarization will not work)")

    # Start server
    uvicorn.run(
        "medrxiv_langchain.api_main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
        workers=args.workers if not args.reload else 1  # reload doesn't work with multiple workers
    )


if __name__ == "__main__":
    main()
