"""
Metadata enrichment using Ollama LLM.
"""
import json
from typing import Dict, Any
import ollama
from config import settings
from utils import log


class MetadataEnricher:
    """Enrich chunk metadata using LLM analysis."""

    def __init__(self):
        """Initialize Ollama client."""
        self.client = ollama.Client(host=settings.ollama_host)
        self.model = settings.ollama_metadata_model  # Use Mistral 7B for better quality
        log.info(f"MetadataEnricher initialized with model: {self.model}")

    def enrich(self, chunk_content: str) -> Dict[str, Any]:
        """
        Enrich chunk with extracted metadata.

        Args:
            chunk_content: Text content of the chunk

        Returns:
            Dictionary with enriched metadata
        """
        # Truncate content for analysis (first 1000 chars)
        sample = chunk_content[:1000] if len(chunk_content) > 1000 else chunk_content

        prompt = self._create_prompt(sample)

        try:
            response = self.client.generate(
                model=self.model,
                prompt=prompt,
                options={
                    'temperature': 0.3,
                    'num_predict': 300
                }
            )

            response_text = response['response'].strip()

            # Remove markdown code blocks if present
            if response_text.startswith('```'):
                lines = response_text.split('\n')
                response_text = '\n'.join(lines[1:-1])
                if response_text.startswith('json'):
                    response_text = '\n'.join(response_text.split('\n')[1:])

            # Parse JSON
            metadata = json.loads(response_text)

            log.debug(f"Enriched metadata: {metadata.get('topics', [])}")
            return metadata

        except json.JSONDecodeError as e:
            log.warning(f"Failed to parse metadata JSON: {e}")
            return self._fallback_metadata(chunk_content)

        except Exception as e:
            log.error(f"Error enriching metadata: {e}")
            return self._fallback_metadata(chunk_content)

    def _create_prompt(self, content: str) -> str:
        """
        Create prompt for metadata extraction.

        Args:
            content: Content sample

        Returns:
            Prompt string
        """
        return f"""Extract metadata from this technical content. Analyze carefully and return REAL, SPECIFIC information.

CONTENT:
{content}

INSTRUCTIONS:
You MUST extract REAL metadata from the content above. DO NOT use generic placeholders like "topic1", "keyword1", etc.

Extract:
1. TOPICS (3-5): Main subjects discussed (e.g., "HTTP methods", "API routing", "authentication")
2. KEYWORDS (5-8): Important technical terms found in the text (e.g., "FastAPI", "async", "dependency injection")
3. SUMMARY (1 sentence, max 20 words): Brief description of what this content explains
4. CONCEPTS (3-5): Technical concepts mentioned (e.g., "REST API", "type hints", "middleware")
5. DIFFICULTY: beginner, intermediate, or advanced
6. PROGRAMMING_LANGUAGES: List any mentioned (e.g., ["Python", "JavaScript"])
7. FRAMEWORKS: List any mentioned (e.g., ["FastAPI", "Vue.js"])

CRITICAL RULES:
- Use REAL words from the content, NOT generic placeholders
- Extract ACTUAL topics like "API routing" NOT "topic1"
- Extract ACTUAL keywords like "FastAPI" NOT "keyword1"
- If you cannot extract something, use an empty array []
- Return ONLY valid JSON, no markdown, no code blocks, no extra text

REQUIRED JSON FORMAT:
{{
    "topics": ["actual topic 1", "actual topic 2", "actual topic 3"],
    "keywords": ["actual keyword 1", "actual keyword 2", "actual keyword 3", "actual keyword 4", "actual keyword 5"],
    "summary": "one clear sentence describing the content",
    "concepts": ["actual concept 1", "actual concept 2"],
    "difficulty": "beginner",
    "programming_languages": ["Python"],
    "frameworks": ["FastAPI"]
}}

Return ONLY the JSON object (no other text):"""

    def _fallback_metadata(self, content: str) -> Dict[str, Any]:
        """
        Generate basic metadata when LLM fails.

        Args:
            content: Chunk content

        Returns:
            Basic metadata dictionary
        """
        import re
        from collections import Counter

        # Extract words (alphanumeric, keep case)
        words = re.findall(r'\b[A-Za-z][A-Za-z0-9_]*\b', content)

        # Common programming/tech terms to look for
        tech_terms = {
            'api', 'fastapi', 'python', 'javascript', 'typescript', 'async', 'await',
            'router', 'endpoint', 'request', 'response', 'http', 'get', 'post',
            'delete', 'put', 'patch', 'database', 'sql', 'mongodb', 'redis',
            'authentication', 'authorization', 'jwt', 'oauth', 'middleware',
            'dependency', 'injection', 'pydantic', 'validation', 'schema',
            'cors', 'websocket', 'rest', 'graphql', 'json', 'xml'
        }

        # Count word frequencies (case-insensitive for matching)
        word_freq = Counter(w.lower() for w in words if len(w) > 3)

        # Extract keywords: prioritize tech terms, then frequent words
        keywords = []

        # First, add tech terms found in content
        for term in tech_terms:
            if term in word_freq and word_freq[term] > 0:
                # Get the original case version
                original = next((w for w in words if w.lower() == term), term)
                keywords.append(original)
                if len(keywords) >= 8:
                    break

        # If not enough, add most frequent words
        if len(keywords) < 8:
            for word, _ in word_freq.most_common(20):
                if word not in [k.lower() for k in keywords] and len(word) > 4:
                    # Get original case
                    original = next((w for w in words if w.lower() == word), word)
                    keywords.append(original)
                    if len(keywords) >= 8:
                        break

        # Extract programming languages
        prog_langs = []
        lang_patterns = ['python', 'javascript', 'typescript', 'java', 'rust', 'go', 'c++', 'ruby']
        content_lower = content.lower()
        for lang in lang_patterns:
            if lang in content_lower:
                prog_langs.append(lang.capitalize() if lang != 'c++' else 'C++')

        # Extract frameworks
        frameworks = []
        framework_patterns = ['fastapi', 'django', 'flask', 'vue', 'react', 'angular', 'express']
        for fw in framework_patterns:
            if fw in content_lower:
                frameworks.append(fw.capitalize() if fw != 'fastapi' else 'FastAPI')

        return {
            'topics': [],
            'concepts': [],
            'keywords': keywords[:8],  # Limit to 8
            'difficulty': 'unknown',
            'summary': content[:100],
            'programming_languages': prog_langs,
            'frameworks': frameworks
        }
