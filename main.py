#!/usr/bin/env python3
"""
Main entry point for the RAG Local System.
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from orchestrator import Orchestrator
from queue_processor.integrated_processor import IntegratedProcessor
from database import VectorStore
from processing import Reranker, QueryExpander, KeywordSearcher, HybridSearcher
from utils import log


class RAGSystem:
    """Main RAG system coordinator."""

    def __init__(self):
        """Initialize RAG system."""
        self.orchestrator = Orchestrator()
        self.processor = IntegratedProcessor()
        self.vector_store = VectorStore()

        # Lazy load advanced search components
        self.reranker = None
        self.query_expander = None
        self.keyword_searcher = None
        self.hybrid_searcher = None

        log.info("RAG System initialized")

    def add_sources(self, user_input: str, interactive: bool = False) -> dict:
        """
        Add sources (URLs or prompt) to the system.

        Args:
            user_input: URLs or text prompt
            interactive: If True, prompt user to select URLs

        Returns:
            Result dictionary
        """
        if interactive:
            return self._add_sources_interactive(user_input)
        else:
            return self.orchestrator.process_input(user_input)

    def _add_sources_interactive(self, user_input: str) -> dict:
        """
        Add sources with interactive URL selection.

        Args:
            user_input: URLs or text prompt

        Returns:
            Result dictionary with selected URLs
        """
        from collections import defaultdict
        from utils import detect_url_type

        # First, discover URLs (but don't add them yet)
        result = self.orchestrator.analyze_input(user_input)

        if not result.get('urls'):
            print("\n⚠️  Aucune URL découverte")
            return {'urls_discovered': 0, 'urls_added': 0, 'urls_skipped': 0}

        # Group URLs by type
        urls_by_type = defaultdict(list)
        type_icons = {
            'youtube_video': '🎥',
            'youtube_channel': '📺',
            'github': '🐙',
            'website': '🌐'
        }

        for url in result['urls']:
            url_type = detect_url_type(url)
            urls_by_type[url_type].append(url)

        # Display discovered URLs
        print("\n" + "="*70)
        print("🔍 URLS DÉCOUVERTES")
        print("="*70 + "\n")

        all_urls = []
        url_index = 1

        for source_type, urls in urls_by_type.items():
            if urls:
                icon = type_icons.get(source_type, '📄')
                type_name = source_type.replace('_', ' ').upper()
                print(f"{icon} {type_name} ({len(urls)} URLs) :")
                for url in urls:
                    print(f"   [{url_index}] {url}")
                    all_urls.append(url)
                    url_index += 1
                print()

        # Check if we have YouTube channels (discovered or extracted)
        youtube_videos = urls_by_type.get('youtube_video', [])
        youtube_channels_found = urls_by_type.get('youtube_channel', [])

        # Diversity filter for YouTube videos
        if youtube_videos and len(youtube_videos) > 5:
            print("💡 FILTRE DE DIVERSITÉ VIDÉOS YOUTUBE")
            print("="*70 + "\n")
            print(f"🎥 {len(youtube_videos)} vidéos YouTube trouvées")

            # Extract unique channels from videos
            from scrapers.youtube_channel_crawler import YouTubeChannelCrawler
            temp_crawler = YouTubeChannelCrawler()
            channels_in_videos = {}

            for video_url in youtube_videos:
                try:
                    channel_url = temp_crawler._get_channel_url_from_video(video_url)
                    if channel_url:
                        if channel_url not in channels_in_videos:
                            channels_in_videos[channel_url] = []
                        channels_in_videos[channel_url].append(video_url)
                except:
                    pass

            if len(channels_in_videos) > 1:
                print(f"   Provenant de {len(channels_in_videos)} chaîne(s) différente(s)")
                print()
                print("Options de filtrage :")
                print("   [K] Keep all     - Garder toutes les vidéos")
                print("   [D] Diversity    - Max 3 vidéos par chaîne")
                print("   [S] Single       - 1 vidéo par chaîne (diversité maximale)")
                print()

                filter_choice = input("Votre choix [K/D/S] : ").strip().upper()

                if filter_choice == 'D':
                    # Keep max 3 videos per channel
                    filtered_videos = []
                    for channel, videos in channels_in_videos.items():
                        filtered_videos.extend(videos[:3])

                    # Update the video list
                    urls_by_type['youtube_video'] = filtered_videos
                    youtube_videos = filtered_videos

                    # Update all_urls
                    all_urls = [url for url in all_urls if detect_url_type(url) != 'youtube_video']
                    all_urls.extend(filtered_videos)

                    print(f"   ✅ Réduit à {len(filtered_videos)} vidéos (max 3 par chaîne)\n")

                elif filter_choice == 'S':
                    # Keep only 1 video per channel
                    filtered_videos = []
                    for channel, videos in channels_in_videos.items():
                        filtered_videos.append(videos[0])

                    # Update the video list
                    urls_by_type['youtube_video'] = filtered_videos
                    youtube_videos = filtered_videos

                    # Update all_urls
                    all_urls = [url for url in all_urls if detect_url_type(url) != 'youtube_video']
                    all_urls.extend(filtered_videos)

                    print(f"   ✅ Réduit à {len(filtered_videos)} vidéos (1 par chaîne)\n")
                else:
                    print("   ✅ Toutes les vidéos conservées\n")

        all_channels = list(youtube_channels_found)  # Start with discovered channels

        # Extract channels from videos if no channels found
        if youtube_videos and not youtube_channels_found:
            print("💡 SUGGESTION : Des vidéos YouTube trouvées mais aucune chaîne.")
            print("   Voulez-vous extraire automatiquement les chaînes depuis ces vidéos ?")
            extract_channels = input("   Extraire les chaînes ? (o/n) : ").strip().lower()

            if extract_channels in ['o', 'oui', 'y', 'yes']:
                from scrapers.youtube_channel_crawler import YouTubeChannelCrawler
                crawler = YouTubeChannelCrawler()

                extracted_channels = set()
                print("   Extraction en cours...")
                for video_url in youtube_videos[:5]:  # Limit to first 5 videos to avoid API quota
                    try:
                        # Extract channel ID from video
                        channel_url = crawler._get_channel_url_from_video(video_url)
                        if channel_url:
                            extracted_channels.add(channel_url)
                    except:
                        pass

                if extracted_channels:
                    all_channels.extend(list(extracted_channels))
                    print(f"   ✅ {len(extracted_channels)} chaîne(s) extraite(s)\n")

        # C/A/S Interactive mode for YouTube channels
        if all_channels:
            print("\n" + "="*70)
            print("📺 CHAÎNES YOUTUBE DÉCOUVERTES")
            print("="*70 + "\n")
            print(f"Trouvé {len(all_channels)} chaîne(s) YouTube")
            print("Pour chaque chaîne, vous pouvez :")
            print("   [C] Crawler 50 vidéos récentes")
            print("   [A] Crawler ALL (jusqu'à 500 vidéos)")
            print("   [S] Skip (ignorer)")
            print("   [Q] Quit (sortir du mode chaînes)\n")

            from scrapers.youtube_channel_crawler import YouTubeChannelCrawler
            crawler = YouTubeChannelCrawler()

            for i, channel_url in enumerate(all_channels, 1):
                print(f"\n📺 Chaîne #{i}/{len(all_channels)} :")
                print(f"   {channel_url}")

                choice = input("   Votre choix [C/A/S/Q] : ").strip().upper()

                if choice == 'Q':
                    print("   ⏭️  Sortie du mode chaînes")
                    break
                elif choice == 'C':
                    print("   🔄 Crawl 50 vidéos...")
                    result = crawler.crawl_channel(channel_url, max_videos=50, crawl_all=False)

                    if result.get('success'):
                        videos = result.get('video_urls', [])
                        print(f"   ✅ {len(videos)} vidéos trouvées")

                        # Add channel URL itself
                        all_urls.append(channel_url)

                        # Add discovered videos to selection
                        for video_url in videos:
                            all_urls.append(video_url)

                    else:
                        print(f"   ❌ Erreur : {result.get('error', 'Unknown')}")

                elif choice == 'A':
                    print("   🔄 Crawl ALL (jusqu'à 500 vidéos)...")
                    result = crawler.crawl_channel(channel_url, max_videos=500, crawl_all=True)

                    if result.get('success'):
                        videos = result.get('video_urls', [])
                        print(f"   ✅ {len(videos)} vidéos trouvées")

                        # Add channel URL itself
                        all_urls.append(channel_url)

                        # Add discovered videos to selection
                        for video_url in videos:
                            all_urls.append(video_url)

                    else:
                        print(f"   ❌ Erreur : {result.get('error', 'Unknown')}")

                elif choice == 'S':
                    print("   ⏭️  Skip")
                    # Add channel URL only (no crawling)
                    all_urls.append(channel_url)
                else:
                    print(f"   ⚠️  Choix invalide '{choice}' - Skip par défaut")
                    all_urls.append(channel_url)

            print("\n" + "="*70)

        # Competitor technologies interactive mode
        if result.get('technologies'):
            print("\n" + "="*70)
            print("🔬 TECHNOLOGIES DÉTECTÉES")
            print("="*70 + "\n")

            technologies = result['technologies'][:5]  # Limit to top 5
            print(f"Technologies principales identifiées :")
            for i, tech in enumerate(technologies, 1):
                print(f"   {i}. {tech}")
            print()

            # Ask if user wants to search for competitors
            search_competitors = input("Rechercher de la documentation sur les concurrents/alternatives ? (o/n) : ").strip().lower()

            if search_competitors in ['o', 'oui', 'y', 'yes']:
                print("\n🔄 Génération des requêtes concurrentes...")

                # Generate competitor queries
                from orchestrator.query_analyzer import QueryAnalyzer
                analyzer = QueryAnalyzer()
                competitor_queries = analyzer._generate_competitor_queries(technologies)

                if competitor_queries:
                    print(f"   ✅ {len(competitor_queries)} requêtes concurrentes générées")
                    print("\n💡 Exemples de concurrents recherchés :")
                    for q in competitor_queries[:5]:  # Show first 5 examples
                        print(f"   - {q}")
                    print()

                    # Ask for confirmation
                    execute_search = input("Exécuter ces recherches avec Brave Search ? (o/n) : ").strip().lower()

                    if execute_search in ['o', 'oui', 'y', 'yes']:
                        print("   🔄 Recherche en cours...")

                        # Execute competitor searches via Brave
                        from orchestrator.brave_searcher import BraveSearcher
                        brave = BraveSearcher()

                        competitor_urls = set()
                        for query in competitor_queries:
                            try:
                                search_result = brave.search(query, max_results=3)  # Limit to 3 per query
                                for url in search_result.get('urls', []):
                                    competitor_urls.add(url)
                            except Exception as e:
                                log.warning(f"Competitor search failed for '{query}': {e}")

                        if competitor_urls:
                            # Add discovered competitor URLs
                            competitor_list = list(competitor_urls)
                            all_urls.extend(competitor_list)

                            print(f"\n   ✅ {len(competitor_list)} URLs concurrentes ajoutées!")
                            print("   Types de contenu trouvé :")

                            # Show distribution by type
                            comp_types = defaultdict(int)
                            for url in competitor_list:
                                url_type = detect_url_type(url)
                                comp_types[url_type] += 1

                            for url_type, count in comp_types.items():
                                icon = type_icons.get(url_type, '📄')
                                print(f"      {icon} {url_type}: {count}")
                            print()
                        else:
                            print("   ⚠️  Aucune URL concurrente trouvée\n")
                    else:
                        print("   ⏭️  Recherche de concurrents ignorée\n")
                else:
                    print("   ⚠️  Impossible de générer des requêtes concurrentes\n")
            else:
                print("   ⏭️  Recherche de concurrents ignorée\n")

        # Final summary with detailed breakdown
        print("="*70)
        print("📊 RÉCAPITULATIF FINAL")
        print("="*70 + "\n")

        # Count by type
        final_summary = defaultdict(int)
        for url in all_urls:
            url_type = detect_url_type(url)
            final_summary[url_type] += 1

        print("URLs par type :")
        for source_type, count in sorted(final_summary.items()):
            icon = type_icons.get(source_type, '📄')
            print(f"   {icon} {source_type:20s}: {count:4d}")

        print(f"\n   📦 TOTAL : {len(all_urls)} URLs")
        print()

        # Ask for selection
        print("\n💡 OPTIONS DE SÉLECTION :")
        print("   - 'all' ou 'tout'     : Tout accepter")
        print("   - 'none' ou 'aucun'   : Tout refuser")
        print("   - Nombres             : Ex: 1,3,5-8,12")
        print("   - Range               : Ex: 1-10")
        print()

        selection = input("Votre sélection : ").strip().lower()

        # Parse selection
        selected_urls = []

        if selection in ['all', 'tout', 'a', 't']:
            selected_urls = all_urls
        elif selection in ['none', 'aucun', 'n']:
            selected_urls = []
        else:
            # Parse number selection
            selected_indices = set()
            parts = selection.split(',')

            for part in parts:
                part = part.strip()
                if '-' in part:
                    # Range: 5-8
                    try:
                        start, end = part.split('-')
                        for i in range(int(start), int(end) + 1):
                            if 1 <= i <= len(all_urls):
                                selected_indices.add(i - 1)
                    except:
                        pass
                else:
                    # Single number: 3
                    try:
                        idx = int(part)
                        if 1 <= idx <= len(all_urls):
                            selected_indices.add(idx - 1)
                    except:
                        pass

            selected_urls = [all_urls[i] for i in sorted(selected_indices)]

        # Show selection summary
        print()
        print("="*70)
        print(f"✅ SÉLECTION : {len(selected_urls)}/{len(all_urls)} URLs")
        print("="*70)

        if selected_urls:
            print()
            for i, url in enumerate(selected_urls, 1):
                url_type = detect_url_type(url)
                icon = type_icons.get(url_type, '📄')
                print(f"   {icon} [{i}] {url}")
            print()

            # Confirm
            confirm = input("\nConfirmer l'ajout ? (o/n) : ").strip().lower()

            if confirm in ['o', 'oui', 'y', 'yes']:
                # Add selected URLs
                urls_text = '\n'.join(selected_urls)
                result = self.orchestrator.process_input(urls_text)

                print(f"\n✅ {result['urls_added']} URLs ajoutées à la queue !")
                return result
            elif confirm in ['n', 'non', 'no']:
                print("\n❌ Ajout annulé")
                return {'urls_discovered': len(all_urls), 'urls_added': 0, 'urls_skipped': len(all_urls)}
            else:
                print(f"\n⚠️  Réponse invalide '{confirm}' - ajout annulé (utilisez 'o' ou 'n')")
                return {'urls_discovered': len(all_urls), 'urls_added': 0, 'urls_skipped': len(all_urls)}
        else:
            print("\n⚠️  Aucune URL sélectionnée")
            return {'urls_discovered': len(all_urls), 'urls_added': 0, 'urls_skipped': len(all_urls)}

    async def process_queue(self, max_batches: int = None):
        """
        Process all pending URLs in queue.

        Args:
            max_batches: Maximum number of batches to process

        Returns:
            Processing results
        """
        return await self.processor.process_all(max_batches=max_batches)

    def search(
        self,
        query: str,
        n_results: int = 5,
        filters: dict = None,
        similarity_threshold: float = 1.5,
        enable_reranking: bool = True,
        enable_hybrid: bool = False,
        enable_query_expansion: bool = False
    ):
        """
        Advanced search with multiple retrieval strategies.

        Features:
        - Semantic search (embeddings)
        - Keyword search (BM25)
        - Hybrid fusion (RRF)
        - Cross-encoder reranking
        - LLM query expansion

        Args:
            query: Search query
            n_results: Number of results to return
            filters: Optional metadata filters
            similarity_threshold: Maximum cosine distance threshold (0-2 range)
            enable_reranking: Use cross-encoder reranking (default: True, +15-25% accuracy)
            enable_hybrid: Use hybrid semantic+keyword search (default: False, +10-20% recall)
            enable_query_expansion: Use LLM to expand query (default: False, +5-15% for short queries)

        Returns:
            Search results with similarity/rerank scores
        """
        from processing import Embedder

        # Stage 0: Query expansion (optional)
        search_query = query
        if enable_query_expansion:
            if self.query_expander is None:
                self.query_expander = QueryExpander()
            search_query = self.query_expander.expand(query)
            if search_query != query:
                log.info(f"Query expanded: '{query}' -> '{search_query}'")

        # Stage 1: Retrieval (semantic and/or keyword)
        if enable_hybrid:
            # Hybrid: semantic + keyword search
            return self._hybrid_search(
                search_query,
                n_results,
                filters,
                enable_reranking,
                similarity_threshold
            )
        else:
            # Semantic-only search
            return self._semantic_search(
                search_query,
                n_results,
                filters,
                enable_reranking,
                similarity_threshold
            )

    def _semantic_search(
        self,
        query: str,
        n_results: int,
        filters: dict,
        enable_reranking: bool,
        similarity_threshold: float
    ):
        """Semantic search using embeddings."""
        from processing import Embedder

        # Generate query embedding
        embedder = Embedder()
        query_embedding = embedder.embed_single(query)

        # Determine initial retrieval size
        initial_k = (n_results * 4) if enable_reranking else (n_results * 2)

        # Vector similarity search
        raw_results = self.vector_store.search(
            query_embedding=query_embedding,
            n_results=initial_k,
            where=filters
        )

        # Extract results
        documents = raw_results.get('documents', [[]])[0]
        metadatas = raw_results.get('metadatas', [[]])[0]
        distances = raw_results.get('distances', [[]])[0]

        if not documents:
            return self._empty_results()

        # Reranking
        if enable_reranking:
            return self._apply_reranking(query, documents, metadatas, n_results)
        else:
            return self._filter_by_threshold(documents, metadatas, distances, n_results, similarity_threshold)

    def _hybrid_search(
        self,
        query: str,
        n_results: int,
        filters: dict,
        enable_reranking: bool,
        similarity_threshold: float
    ):
        """Hybrid search combining semantic and keyword retrieval."""
        from processing import Embedder

        # Build keyword index if not exists
        if self.keyword_searcher is None:
            self.keyword_searcher = KeywordSearcher()
            # Index all documents from vector store
            # Note: This is expensive, ideally done offline
            log.info("Building keyword search index from vector store...")
            all_docs, all_metas = self._get_all_documents()
            if all_docs:
                self.keyword_searcher.index(all_docs, all_metas)

        # Lazy load hybrid searcher
        if self.hybrid_searcher is None:
            self.hybrid_searcher = HybridSearcher()

        # Get semantic results
        embedder = Embedder()
        query_embedding = embedder.embed_single(query)
        semantic_results = self.vector_store.search(
            query_embedding=query_embedding,
            n_results=n_results * 3,  # Get more for fusion
            where=filters
        )

        semantic_docs = semantic_results.get('documents', [[]])[0]
        semantic_metas = semantic_results.get('metadatas', [[]])[0]
        semantic_dists = semantic_results.get('distances', [[]])[0]

        # Convert distances to scores (higher = better)
        semantic_scores = [1 - (d / 2) for d in semantic_dists]

        # Get keyword results
        keyword_docs, keyword_metas, keyword_scores = self.keyword_searcher.search(
            query, top_k=n_results * 3
        )

        # Fuse results
        fused_docs, fused_metas, fused_scores = self.hybrid_searcher.fuse_results(
            semantic_docs, semantic_metas, semantic_scores,
            keyword_docs, keyword_metas, keyword_scores,
            top_k=n_results * 2 if enable_reranking else n_results
        )

        if not fused_docs:
            return self._empty_results()

        # Reranking on fused results
        if enable_reranking:
            return self._apply_reranking(query, fused_docs, fused_metas, n_results)
        else:
            # Return fused results
            return {
                'documents': [fused_docs],
                'metadatas': [fused_metas],
                'distances': [[0.0] * len(fused_docs)],
                'similarities': [fused_scores],
                'rerank_scores': [[]]
            }

    def _apply_reranking(self, query: str, documents: list, metadatas: list, n_results: int):
        """Apply cross-encoder reranking."""
        if self.reranker is None:
            self.reranker = Reranker()

        reranked_docs, reranked_metas, rerank_scores = self.reranker.rerank(
            query=query,
            documents=documents,
            metadatas=metadatas,
            top_k=n_results
        )

        rerank_similarities = self.reranker.normalize_scores(rerank_scores)

        return {
            'documents': [reranked_docs],
            'metadatas': [reranked_metas],
            'distances': [[0.0] * len(reranked_docs)],
            'similarities': [rerank_similarities],
            'rerank_scores': [rerank_scores]
        }

    def _filter_by_threshold(self, documents: list, metadatas: list, distances: list, n_results: int, threshold: float):
        """Filter results by similarity threshold."""
        filtered_docs = []
        filtered_metas = []
        filtered_dists = []
        filtered_sims = []

        for i, distance in enumerate(distances):
            similarity = 1 - (distance / 2)  # Cosine similarity

            if distance <= threshold:
                filtered_docs.append(documents[i])
                filtered_metas.append(metadatas[i])
                filtered_dists.append(distance)
                filtered_sims.append(similarity)

        # Limit to n_results
        return {
            'documents': [filtered_docs[:n_results]],
            'metadatas': [filtered_metas[:n_results]],
            'distances': [filtered_dists[:n_results]],
            'similarities': [filtered_sims[:n_results]],
            'rerank_scores': [[]]
        }

    def _empty_results(self):
        """Return empty search results."""
        return {
            'documents': [[]],
            'metadatas': [[]],
            'distances': [[]],
            'similarities': [[]],
            'rerank_scores': [[]]
        }

    def _get_all_documents(self):
        """Get all documents from vector store for keyword indexing."""
        try:
            # Get a large number of results (or all)
            all_data = self.vector_store.collection.get()
            documents = all_data.get('documents', [])
            metadatas = all_data.get('metadatas', [])
            return documents, metadatas
        except Exception as e:
            log.error(f"Error getting all documents: {e}")
            return [], []

    def get_stats(self) -> dict:
        """Get system statistics."""
        db_stats = self.orchestrator.get_stats()
        vector_stats = self.vector_store.get_stats()

        return {
            'database': db_stats['database'],
            'vector_store': vector_stats
        }

    def close(self):
        """Clean up resources."""
        self.orchestrator.close()
        self.processor.close()
        log.info("RAG System closed")


async def main():
    """Example usage."""
    print("\n" + "="*60)
    print("RAG Local System - Complete Pipeline Demo")
    print("="*60 + "\n")

    # Initialize system
    rag = RAGSystem()

    # Example 1: Add URLs directly
    print("Example 1: Adding URLs directly")
    result = rag.add_sources("""
    https://fastapi.tiangolo.com/tutorial/first-steps/
    """)
    print(f"✅ Added {result['urls_added']} URLs\n")

    # Example 2: Process queue
    print("Example 2: Processing queue")
    print("Starting processing pipeline...")
    process_result = await rag.process_queue(max_batches=1)
    print(f"✅ Processed {process_result['total_processed']} URLs")
    print(f"   Succeeded: {process_result['total_succeeded']}")
    print(f"   Failed: {process_result['total_failed']}\n")

    # Example 3: Search
    if process_result['total_succeeded'] > 0:
        print("Example 3: Searching knowledge base")
        search_results = rag.search("How to create a route in FastAPI?", n_results=3)

        if search_results['documents']:
            print(f"Found {len(search_results['documents'][0])} results:\n")
            for i, (doc, meta) in enumerate(zip(search_results['documents'][0], search_results['metadatas'][0])):
                print(f"Result {i+1}:")
                print(f"  Source: {meta.get('source_url', 'N/A')}")
                print(f"  Topics: {', '.join(meta.get('topics', []))}")
                print(f"  Content: {doc[:200]}...")
                print()

    # Example 4: Stats
    print("Example 4: System statistics")
    stats = rag.get_stats()
    print(f"Database: {stats['database']}")
    print(f"Vector Store: {stats['vector_store']['total_chunks']} chunks\n")

    # Cleanup
    rag.close()

    print("="*60)
    print("Demo complete!")
    print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
