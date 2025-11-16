"""
Query analyzer using Ollama to generate search strategies from text prompts.
"""
import json
from typing import Dict, List, Any
import ollama
from config import settings
from utils import log


class QueryAnalyzer:
    """Uses Ollama to analyze text prompts and generate search strategies."""

    # Known competitors by technology domain
    COMPETITORS = {
        'freeswitch': ['Jambonz', 'Asterisk', 'Kamailio', 'OpenSIPS'],
        'whisper': ['DeepSpeech', 'Wav2Vec', 'Vosk', 'AssemblyAI'],
        'tts': ['Bark', 'VALL-E', 'Tortoise-TTS', 'MMS-TTS'],
        'fastapi': ['Flask', 'Django', 'Quart', 'Starlette'],
        'chromadb': ['Qdrant', 'Pinecone', 'Weaviate', 'Milvus'],
        'redis': ['Memcached', 'Dragonfly', 'KeyDB', 'Valkey'],
        'postgresql': ['MySQL', 'MariaDB', 'CockroachDB', 'TimescaleDB'],
    }

    def __init__(self):
        """Initialize Ollama client."""
        self.client = ollama.Client(host=settings.ollama_host)
        self.model = settings.ollama_model
        log.info(f"QueryAnalyzer initialized with model: {self.model}")

    def _extract_technologies(self, text: str) -> List[str]:
        """
        Extract technical components from a long text using simple pattern matching.

        Args:
            text: Input text (possibly very long specification)

        Returns:
            List of detected technologies/frameworks
        """
        import re

        # Common technical terms to detect
        tech_patterns = [
            # Web frameworks
            r'\bFastAPI\b', r'\bDjango\b', r'\bFlask\b', r'\bVue\.?js\b', r'\bReact\b', r'\bAngular\b',
            # Databases
            r'\bChromaDB\b', r'\bQdrant\b', r'\bPinecone\b', r'\bPostgreSQL\b', r'\bRedis\b',
            r'\bMongoDB\b', r'\bMySQL\b',
            # AI/ML
            r'\bWhisper\b', r'\bOllama\b', r'\bLlama\b', r'\bGPT\b', r'\bTTS\b',
            r'\bCoqui\b', r'\bElevenLabs\b', r'\bsentence-transformers?\b',
            # Telephony/Audio
            r'\bFreeSWITCH\b', r'\bAsterisk\b', r'\bWebRTC\b', r'\bSIP\b', r'\bVoIP\b',
            # Other
            r'\bDocker\b', r'\bKubernetes\b', r'\bRabbitMQ\b', r'\bWebSocket\b',
            r'\bNginx\b', r'\bApache\b',
        ]

        detected = []
        text_lower = text.lower()

        for pattern in tech_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                tech = match.group(0)
                if tech not in detected and tech.lower() not in [d.lower() for d in detected]:
                    detected.append(tech)

        # Also extract words in ALL CAPS or CamelCase (likely tech names)
        camel_case = re.findall(r'\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b', text)
        for word in camel_case:
            if word not in detected and len(word) > 3:
                detected.append(word)

        return detected

    def _generate_competitor_queries(self, technologies: List[str]) -> List[str]:
        """
        Generate search queries for competitor technologies using Ollama.

        Args:
            technologies: List of detected technologies

        Returns:
            List of competitor-focused search queries
        """
        if not technologies:
            return []

        # Ask Ollama to identify competitors for these technologies
        tech_list = ', '.join(technologies[:10])  # Limit to first 10 techs

        competitor_prompt = f"""For these technologies: {tech_list}

List 2-3 main competitors or alternatives for EACH technology.

Return ONLY a JSON object:
{{
    "tech_name": ["competitor1", "competitor2", "competitor3"]
}}

Example:
{{
    "FreeSWITCH": ["Jambonz", "Asterisk"],
    "Whisper": ["DeepSpeech", "Wav2Vec"],
    "WhatsApp": ["Telegram", "Signal", "Matrix"]
}}"""

        try:
            response = self.client.generate(
                model=self.model,
                prompt=competitor_prompt,
                options={'temperature': 0.2, 'num_predict': 300}
            )

            response_text = response['response'].strip()

            # Remove markdown if present
            if response_text.startswith('```'):
                lines = response_text.split('\n')
                response_text = '\n'.join(lines[1:-1])
                if response_text.startswith('json'):
                    response_text = '\n'.join(response_text.split('\n')[1:])

            competitors_map = json.loads(response_text)
            log.info(f"Ollama identified competitors for {len(competitors_map)} technologies")

        except Exception as e:
            log.warning(f"Ollama competitor detection failed: {e}, using fallback")
            # Fallback to static dictionary
            competitors_map = {}
            for tech in technologies:
                tech_lower = tech.lower()
                for key, comp_list in self.COMPETITORS.items():
                    if key in tech_lower or tech_lower in key:
                        competitors_map[tech] = comp_list[:2]
                        break

        # Generate queries for competitors
        competitor_queries = []
        for tech, competitors in competitors_map.items():
            for competitor in competitors[:2]:  # Limit to top 2 per tech
                competitor_queries.append(f"{competitor} official documentation")
                competitor_queries.append(f"{competitor} GitHub repository")
                competitor_queries.append(f"{competitor} tutorial YouTube")

        log.info(f"Generated {len(competitor_queries)} competitor queries")
        return competitor_queries

    def analyze_prompt(self, prompt: str) -> Dict[str, Any]:
        """
        Analyze a text prompt and generate a search strategy.

        Args:
            prompt: User's text prompt

        Returns:
            Dictionary with:
                - search_queries: List of search queries to execute
                - topics: Main topics identified
                - keywords: Important keywords
        """
        # For very long prompts, extract technologies first
        technologies = []
        if len(prompt) > 2000:
            log.info(f"Long prompt detected ({len(prompt)} chars), extracting technologies first")
            technologies = self._extract_technologies(prompt)

            # Create a condensed version
            if technologies:
                condensed_prompt = f"Technologies: {', '.join(technologies[:15])}"
                log.info(f"Condensed prompt: {condensed_prompt}")
            else:
                # Fallback: use first 500 chars + last 200 chars
                condensed_prompt = prompt[:500] + "..." + prompt[-200:]
                log.info("No technologies extracted, using truncated prompt")
        else:
            condensed_prompt = prompt
            # Extract technologies for short prompts too
            technologies = self._extract_technologies(condensed_prompt)

        # Calculate recommended number of queries based on complexity
        num_techs = len(technologies)

        # Adaptive query count: 2 queries per technology, min 10, max 25
        recommended_queries = max(10, min(25, num_techs * 2))

        log.info(f"Detected {num_techs} technologies: {', '.join(technologies[:5])}{'...' if len(technologies) > 5 else ''}")
        log.info(f"Recommending {recommended_queries} search queries")

        system_prompt = """You are a search strategy generator for a RAG system.
Your task is to analyze user queries and generate effective web search queries to find relevant resources.

CRITICAL: You MUST extract ALL technical components, frameworks, and technologies mentioned in the user's query.
For EACH component found, generate AT LEAST ONE search query.

IMPORTANT: Generate a MIX of different query types with STRICT ratios:
- 20% Documentation/official sites (e.g., "FreeSWITCH official documentation", "Whisper API docs")
- 70% YouTube content (videos/channels/masterclass/playlists) - MANDATORY MINIMUM
  * 30% YouTube CHANNELS (e.g., "@FastAPI channel tutorials", "Whisper YouTube channel")
  * 20% MASTERCLASS/Long videos (e.g., "FastAPI masterclass YouTube", "Whisper complete course 1 hour")
  * 10% PLAYLISTS (e.g., "FastAPI playlist series", "Whisper tutorial playlist")
  * 10% Regular videos (e.g., "FastAPI quick tutorial video")
- 10% GitHub repositories (e.g., "faster-whisper GitHub", "FreeSWITCH examples GitHub")

🎥 YOUTUBE IS MANDATORY (70% MINIMUM):
- You MUST include YouTube-related keywords in at least 70% of queries
- PRIORITIZE: Channels > Masterclass > Playlists > Individual videos
- Channel queries: "{tech} YouTube channel tutorials", "@{tech} channel", "{tech} channel complete guide"
- Masterclass queries: "{tech} masterclass YouTube", "{tech} complete course 1 hour+", "{tech} full tutorial"
- Playlist queries: "{tech} playlist series", "{tech} tutorial playlist YouTube"
- For every technology, create at least 1 CHANNEL query and 1 MASTERCLASS query

MANDATORY RULES:
1. Extract ALL technologies mentioned (libraries, frameworks, tools, databases)
2. For EACH technology, create at least 3 specific search queries:
   - 1 CHANNEL query (e.g., "{tech} YouTube channel")
   - 1 MASTERCLASS query (e.g., "{tech} masterclass complete course")
   - 1 DOCS/GitHub query
3. Prioritize YouTube content (70%), especially channels and masterclass
4. Generate diverse search queries to cover all components
5. Include technical keywords in queries (e.g., "streaming", "real-time", "API", "tutorial")

Example: If user mentions "FreeSWITCH, Whisper, FastAPI, ChromaDB, Redis":
MUST generate at least 15 queries with 10+ YouTube (70%):
- "FreeSWITCH YouTube channel tutorials" (channel) ✅
- "FreeSWITCH masterclass complete course 1 hour" (masterclass) ✅
- "FreeSWITCH official documentation" (docs)
- "Whisper YouTube channel Python streaming" (channel) ✅
- "Whisper masterclass full tutorial" (masterclass) ✅
- "faster-whisper GitHub repository" (GitHub)
- "FastAPI YouTube channel WebSocket tutorials" (channel) ✅
- "FastAPI masterclass complete guide" (masterclass) ✅
- "FastAPI playlist series YouTube" (playlist) ✅
- "ChromaDB YouTube channel vector database" (channel) ✅
- "ChromaDB complete course" (masterclass) ✅
- "Redis YouTube channel async tutorials" (channel) ✅
- "Redis masterclass YouTube" (masterclass) ✅
- "Coqui TTS YouTube channel" (channel) ✅
- etc.

Return ONLY a valid JSON object with this structure:
{
    "search_queries": ["query 1", "query 2", "query 3", ..., "query N"],
    "topics": ["topic1", "topic2", "topic3"],
    "keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"]
}

Do not include any markdown formatting, code blocks, or additional text. Return only the raw JSON object."""

        user_prompt = f"""User request: "{condensed_prompt}"

TASK: Extract ALL technical components, frameworks, libraries, databases, and tools mentioned above.
Then generate {recommended_queries} diverse search queries covering EVERY component.

CRITICAL STRATEGY:
- Think PER TECHNICAL COMPONENT, not globally
- For EACH technology/framework/tool, create at least 2 queries (one MUST be YouTube)
- Example: If you detect "FreeSWITCH, Whisper, FastAPI, ChromaDB":
  * FreeSWITCH: "FreeSWITCH official docs", "FreeSWITCH tutorial YouTube complete" ✅
  * Whisper: "Whisper streaming video tutorial" ✅, "faster-whisper GitHub"
  * FastAPI: "FastAPI WebSocket YouTube guide" ✅, "FastAPI async docs"
  * ChromaDB: "ChromaDB vector database YouTube" ✅

MANDATORY requirements (STRICT RATIO):
1. Create at least 3 queries for EACH technology mentioned:
   - 1 CHANNEL query (e.g., "TechName YouTube channel complete tutorials")
   - 1 MASTERCLASS query (e.g., "TechName masterclass 1 hour+ full course")
   - 1 DOCS/GitHub query
2. 70% of queries MUST include YouTube keywords:
   - 30% CHANNEL queries ("YouTube channel", "@channel", "channel tutorials")
   - 20% MASTERCLASS queries ("masterclass", "complete course", "1 hour+", "full tutorial")
   - 10% PLAYLIST queries ("playlist", "series", "tutorial playlist")
   - 10% Regular video queries ("tutorial", "video guide")
3. 20% Documentation/official sites
4. 10% GitHub repositories
5. Use specific technical keywords (e.g., "streaming", "real-time", "async", "WebSocket")

🎥 REMEMBER: At least {int(recommended_queries * 0.70)} queries MUST contain YouTube keywords!
📺 PRIORITIZE: Channels ({int(recommended_queries * 0.30)}+) > Masterclass ({int(recommended_queries * 0.20)}+) > Playlists > Videos

Generate exactly {recommended_queries} queries now."""

        try:
            response = self.client.generate(
                model=self.model,
                prompt=user_prompt,
                system=system_prompt,
                options={
                    'temperature': 0.3,  # Lower temperature for more focused results
                    'num_predict': 1000  # Increased to allow longer JSON responses
                }
            )

            # Parse JSON response
            response_text = response['response'].strip()

            # Remove markdown code blocks if present
            if response_text.startswith('```'):
                # Extract content between ``` markers
                lines = response_text.split('\n')
                response_text = '\n'.join(lines[1:-1])
                if response_text.startswith('json'):
                    response_text = '\n'.join(response_text.split('\n')[1:])

            strategy = json.loads(response_text)

            # Add competitor queries (if enabled)
            if settings.enable_competitor_queries:
                competitor_queries = self._generate_competitor_queries(technologies)
                if competitor_queries:
                    strategy['search_queries'].extend(competitor_queries)
                    log.info(f"Added {len(competitor_queries)} competitor queries")
                log.info(f"Generated {len(strategy.get('search_queries', []))} total search queries (including competitors)")
            else:
                log.info(f"Competitor queries disabled. Generated {len(strategy.get('search_queries', []))} search queries")
            return strategy

        except json.JSONDecodeError as e:
            log.error(f"Failed to parse Ollama response as JSON: {e}")
            log.debug(f"Raw response: {response_text}")

            # Fallback: generate basic search queries from the prompt
            return self._fallback_strategy(prompt)

        except Exception as e:
            log.error(f"Error analyzing prompt with Ollama: {e}")
            return self._fallback_strategy(prompt)

    def _fallback_strategy(self, prompt: str) -> Dict[str, Any]:
        """
        Generate a basic search strategy when Ollama fails.

        Args:
            prompt: Original user prompt

        Returns:
            Basic search strategy dictionary
        """
        # Extract keywords (simple approach)
        words = prompt.split()
        keywords = [w for w in words if len(w) > 3][:5]

        # Generate basic search queries
        search_queries = [
            f"{prompt} tutorial",
            f"{prompt} documentation",
            f"{prompt} examples"
        ]

        return {
            'search_queries': search_queries,
            'topics': keywords[:3],
            'keywords': keywords
        }

    def should_search_web(self, prompt: str) -> bool:
        """
        Determine if the prompt requires web searching.

        Args:
            prompt: User prompt

        Returns:
            True if web search is needed, False otherwise
        """
        # Simple heuristic: if prompt is very short or looks like a URL, skip
        if len(prompt.strip()) < 3:
            return False

        # Check if it looks like a URL
        if prompt.startswith('http://') or prompt.startswith('https://'):
            return False

        return True
