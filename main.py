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
from utils import log


class RAGSystem:
    """Main RAG system coordinator."""

    def __init__(self):
        """Initialize RAG system."""
        self.orchestrator = Orchestrator()
        self.processor = IntegratedProcessor()
        self.vector_store = VectorStore()
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

        print(f"Total : {len(all_urls)} URLs trouvées\n")
        print("="*70)

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

    def search(self, query: str, n_results: int = 5, filters: dict = None, similarity_threshold: float = 1.5):
        """
        Search the knowledge base with similarity threshold filtering.

        Args:
            query: Search query
            n_results: Number of results
            filters: Optional metadata filters
            similarity_threshold: Maximum L2 distance threshold. Results above this are filtered out.
                                 ChromaDB uses L2 distance (lower = more similar).
                                 Typical threshold: 1.0-2.0 (lower = stricter, fewer results)

        Returns:
            Search results with filtered results based on similarity threshold
        """
        from processing import Embedder

        # Generate query embedding
        embedder = Embedder()
        query_embedding = embedder.embed_single(query)

        # Search vector store (get more results to account for filtering)
        raw_results = self.vector_store.search(
            query_embedding=query_embedding,
            n_results=n_results * 2,  # Get 2x results before filtering
            where=filters
        )

        # Filter results by similarity threshold
        # ChromaDB returns distances (lower = more similar)
        # Convert to similarity scores (higher = more similar) for easier understanding
        filtered_documents = []
        filtered_metadatas = []
        filtered_distances = []
        filtered_similarities = []

        if raw_results.get('distances') and raw_results['distances'][0]:
            for i, distance in enumerate(raw_results['distances'][0]):
                # Convert L2 distance to similarity score (0-1 range, higher = more similar)
                # Formula: similarity = 1 / (1 + distance)
                similarity = 1 / (1 + distance)

                # Filter by threshold
                if distance <= similarity_threshold:
                    filtered_documents.append(raw_results['documents'][0][i])
                    filtered_metadatas.append(raw_results['metadatas'][0][i])
                    filtered_distances.append(distance)
                    filtered_similarities.append(similarity)

        # Limit to requested number of results
        filtered_documents = filtered_documents[:n_results]
        filtered_metadatas = filtered_metadatas[:n_results]
        filtered_distances = filtered_distances[:n_results]
        filtered_similarities = filtered_similarities[:n_results]

        return {
            'documents': [filtered_documents],
            'metadatas': [filtered_metadatas],
            'distances': [filtered_distances],
            'similarities': [filtered_similarities]  # Added for easier display
        }

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
