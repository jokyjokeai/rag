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
        More robust to typos and missing spaces.

        Args:
            text: Input text (possibly very long specification)

        Returns:
            List of detected technologies/frameworks
        """
        import re

        # Technology patterns with their canonical names
        # Using more flexible patterns to catch typos and missing spaces
        tech_patterns = {
            # Web frameworks
            'FastAPI': [r'fastapi', r'fast\s*api'],
            'Django': [r'django'],
            'Flask': [r'flask'],
            'Vue.js': [r'vue\.?js', r'vuejs'],
            'React': [r'react\.?js', r'reactjs'],
            'Angular': [r'angular'],
            # Databases
            'ChromaDB': [r'chroma\s*db', r'chromadb'],
            'Qdrant': [r'qdrant'],
            'Pinecone': [r'pinecone'],
            'PostgreSQL': [r'postgres(?:ql)?'],
            'Redis': [r'redis'],
            'MongoDB': [r'mongo(?:db)?'],
            'MySQL': [r'mysql'],
            # AI/ML
            'Whisper': [r'whisper'],
            'Ollama': [r'ollama'],
            'Llama': [r'llama'],
            'GPT': [r'gpt[-\s]?\d*'],
            'TTS': [r'tts', r'text\s*to\s*speech'],
            'Coqui': [r'coqui'],
            'ElevenLabs': [r'eleven\s*labs'],
            'SentenceTransformers': [r'sentence[\s-]?transformers?'],
            # Telephony/Audio
            'FreeSWITCH': [r'free\s*switch', r'freeswitch'],
            'Asterisk': [r'asterisk'],
            'WebRTC': [r'web\s*rtc', r'webrtc'],
            'SIP': [r'\bsip\b'],
            'VoIP': [r'vo\s*ip', r'voip'],
            # Other
            'Docker': [r'docker'],
            'Kubernetes': [r'kubernetes', r'k8s'],
            'RabbitMQ': [r'rabbit\s*mq', r'rabbitmq'],
            'WebSocket': [r'web\s*socket', r'websocket'],
            'Nginx': [r'nginx'],
            'Apache': [r'apache'],
        }

        detected = []
        text_lower = text.lower()

        # Try all patterns for each technology
        for tech_name, patterns in tech_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    if tech_name not in detected:
                        detected.append(tech_name)
                    break  # Found this tech, move to next

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

    def analyze_prompt(self, prompt: str, interactive: bool = False) -> Dict[str, Any]:
        """
        Analyze a text prompt and generate a search strategy.

        Args:
            prompt: User's text prompt
            interactive: If True, don't auto-add competitor queries (let UI handle it)

        Returns:
            Dictionary with:
                - search_queries: List of search queries to execute
                - topics: Main topics identified
                - keywords: Important keywords
                - technologies: Detected technologies
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

        # Generate dynamic examples based on detected technologies
        example_techs = technologies[:3] if len(technologies) >= 3 else ['TechnologyA', 'TechnologyB', 'TechnologyC']
        tech_examples = ', '.join(example_techs)

        system_prompt = f"""You are a search strategy generator for a RAG system.
Your task is to analyze user queries and generate effective web search queries to find relevant resources.

CRITICAL: You MUST extract ALL technical components, frameworks, and technologies mentioned in the user's query.
For EACH component found, generate AT LEAST ONE search query.

IMPORTANT: Generate a MIX of different query types with STRICT ratios:
- 20% Documentation/official sites (e.g., "TechName official documentation", "TechName API docs")
- 70% YouTube content (videos/channels/masterclass/playlists) - MANDATORY MINIMUM
  * 30% YouTube CHANNELS (e.g., "@TechName channel tutorials", "TechName YouTube channel")
  * 20% MASTERCLASS/Long videos (e.g., "TechName masterclass YouTube", "TechName complete course 1 hour")
  * 10% PLAYLISTS (e.g., "TechName playlist series", "TechName tutorial playlist")
  * 10% Regular videos (e.g., "TechName quick tutorial video")
- 10% GitHub repositories (e.g., "TechName GitHub", "TechName examples GitHub")

🎥 YOUTUBE IS MANDATORY (70% MINIMUM):
- You MUST include YouTube-related keywords in at least 70% of queries
- PRIORITIZE: Channels > Masterclass > Playlists > Individual videos
- Channel queries: "TechName YouTube channel tutorials", "@TechName channel", "TechName channel complete guide"
- Masterclass queries: "TechName masterclass YouTube", "TechName complete course 1 hour+", "TechName full tutorial"
- Playlist queries: "TechName playlist series", "TechName tutorial playlist YouTube"
- For every technology, create at least 1 CHANNEL query and 1 MASTERCLASS query

MANDATORY RULES:
1. Extract ALL technologies mentioned (libraries, frameworks, tools, databases)
2. For EACH technology, create at least 3 specific search queries:
   - 1 CHANNEL query (e.g., "TechName YouTube channel")
   - 1 MASTERCLASS query (e.g., "TechName masterclass complete course")
   - 1 DOCS/GitHub query
3. Prioritize YouTube content (70%), especially channels and masterclass
4. Generate diverse search queries to cover all components
5. Include technical keywords in queries (e.g., "streaming", "real-time", "API", "tutorial")

Example: If user mentions "{tech_examples}":
You MUST generate queries ONLY for these {len(example_techs)} technologies.
DO NOT add queries for technologies NOT mentioned in the user's request.

Sample queries for the FIRST technology ({example_techs[0]}):
- "{example_techs[0]} YouTube channel tutorials" (channel) ✅
- "{example_techs[0]} masterclass complete course" (masterclass) ✅
- "{example_techs[0]} official documentation" (docs)
- "{example_techs[0]} GitHub repository" (GitHub)

Then repeat for each detected technology. DO NOT invent extra technologies.

Return ONLY a valid JSON object with this structure:
{{
    "search_queries": ["query 1", "query 2", "query 3", ..., "query N"],
    "topics": ["topic1", "topic2", "topic3"],
    "keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"]
}}

Do not include any markdown formatting, code blocks, or additional text. Return only the raw JSON object."""

        # Build dynamic example based on detected technologies
        if len(technologies) > 0:
            tech_example_text = f"""- Example based on YOUR analysis: If you detect "{tech_examples}":
  * {example_techs[0]}: "{example_techs[0]} official docs", "{example_techs[0]} tutorial YouTube complete" ✅"""
            if len(example_techs) > 1:
                tech_example_text += f"""
  * {example_techs[1]}: "{example_techs[1]} YouTube channel" ✅, "{example_techs[1]} GitHub" """
        else:
            tech_example_text = "- For EACH technology detected, create queries following the patterns above"

        user_prompt = f"""User request: "{condensed_prompt}"

TASK: Extract ALL technical components, frameworks, libraries, databases, and tools mentioned above.
Then generate {recommended_queries} diverse search queries covering EVERY component.

⚠️ CRITICAL: Generate queries ONLY for technologies mentioned in the user's request above.
DO NOT add queries for unrelated technologies like FastAPI, Whisper, ChromaDB unless they appear in the request.

CRITICAL STRATEGY:
- Think PER TECHNICAL COMPONENT found in the user's request
- For EACH technology/framework/tool detected, create at least 2 queries (one MUST be YouTube)
{tech_example_text}

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

            # Add detected technologies to strategy
            strategy['technologies'] = technologies

            # Add competitor queries (if enabled and not interactive)
            if settings.enable_competitor_queries and not interactive:
                competitor_queries = self._generate_competitor_queries(technologies)
                if competitor_queries:
                    strategy['search_queries'].extend(competitor_queries)
                    log.info(f"Added {len(competitor_queries)} competitor queries")
                log.info(f"Generated {len(strategy.get('search_queries', []))} total search queries (including competitors)")
            elif interactive:
                log.info(f"Interactive mode: Generated {len(strategy.get('search_queries', []))} search queries (competitors will be prompted)")
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
            'keywords': keywords,
            'technologies': []  # Empty in fallback mode
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
