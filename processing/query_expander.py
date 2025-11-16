"""
Query expansion using LLM to improve search recall.

Expands user queries with synonyms, related terms, and clarifications
to improve matching against the knowledge base.
"""
from typing import Optional
import requests
from utils import log
from config import settings


class QueryExpander:
    """LLM-based query expander for improved search recall."""

    def __init__(self, model_name: Optional[str] = None):
        """
        Initialize query expander.

        Args:
            model_name: Ollama model name (defaults to settings.ollama_model)
        """
        self.model_name = model_name or settings.ollama_model
        self.ollama_host = settings.ollama_host
        log.info(f"QueryExpander initialized with model: {self.model_name}")

    def expand(self, query: str, max_expansion_words: int = 10) -> str:
        """
        Expand query with related terms and synonyms.

        Args:
            query: Original search query
            max_expansion_words: Maximum number of words to add

        Returns:
            Expanded query string
        """
        # For very short queries (1-2 words), expansion is most beneficial
        # For long queries, skip expansion to avoid noise
        if len(query.split()) > 15:
            log.debug(f"Query too long ({len(query.split())} words), skipping expansion")
            return query

        log.debug(f"Expanding query: '{query}'")

        prompt = f"""Expand this search query with related technical terms and synonyms.
Keep it concise (max {max_expansion_words} additional words).
Focus on technical keywords that would appear in documentation.

Original query: {query}

Expanded query (add related terms only, keep original meaning):"""

        try:
            response = requests.post(
                f"{self.ollama_host}/api/generate",
                json={
                    "model": self.model_name,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,  # Low temperature for focused expansion
                        "num_predict": 50    # Limit output length
                    }
                },
                timeout=10  # Quick timeout (expansion should be fast)
            )

            if response.status_code == 200:
                expanded = response.json().get('response', '').strip()

                # Fallback if LLM output is empty or too long
                if not expanded or len(expanded.split()) > len(query.split()) + max_expansion_words + 5:
                    log.debug("LLM expansion invalid, using original query")
                    return query

                log.debug(f"Expanded to: '{expanded}'")
                return expanded
            else:
                log.warning(f"Ollama API error: {response.status_code}, using original query")
                return query

        except requests.exceptions.Timeout:
            log.warning("Query expansion timeout, using original query")
            return query
        except Exception as e:
            log.warning(f"Query expansion failed: {e}, using original query")
            return query

    def close(self):
        """Clean up resources."""
        # No resources to clean up
        pass
