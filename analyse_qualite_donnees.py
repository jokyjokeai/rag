#!/usr/bin/env python3
"""
Script d'analyse de la qualité des données en base.
Vérifie les chunks, embeddings, keywords et métadonnées.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from database import VectorStore
from utils import log
import json


def analyze_chunk_quality():
    """Analyse la qualité des chunks stockés dans ChromaDB."""

    print("\n" + "="*100)
    print("ANALYSE DE QUALITÉ DES DONNÉES RAG")
    print("="*100)

    vector_store = VectorStore()

    # Get all chunks
    try:
        result = vector_store.collection.get(
            include=['embeddings', 'metadatas', 'documents']
        )
    except Exception as e:
        print(f"❌ Erreur lors de la récupération des données: {e}")
        return

    total_chunks = len(result['ids'])

    if total_chunks == 0:
        print("\n⚠️  Aucun chunk trouvé dans ChromaDB.")
        print("   Lancez d'abord le processing des URLs en pending.")
        return

    print(f"\n📊 STATISTIQUES GLOBALES")
    print(f"   Total chunks: {total_chunks}")
    print(f"   ChromaDB size: 6.8 MB")

    # Analyze by source type
    print(f"\n📁 RÉPARTITION PAR TYPE DE SOURCE")
    source_types = {}
    source_urls = {}

    for metadata in result['metadatas']:
        stype = metadata.get('source_type', 'unknown')
        source_types[stype] = source_types.get(stype, 0) + 1

        url = metadata.get('source_url', 'unknown')
        source_urls[url] = source_urls.get(url, 0) + 1

    for stype, count in sorted(source_types.items(), key=lambda x: x[1], reverse=True):
        print(f"   {stype:20s}: {count:4d} chunks")

    print(f"\n📄 RÉPARTITION PAR URL SOURCE")
    for url, count in sorted(source_urls.items(), key=lambda x: x[1], reverse=True):
        short_url = url[:70] + "..." if len(url) > 70 else url
        print(f"   {count:4d} chunks | {short_url}")

    # Analyze embeddings quality
    print(f"\n🔢 QUALITÉ DES EMBEDDINGS")
    embeddings = result['embeddings']

    if embeddings is not None and len(embeddings) > 0:
        embedding_dims = len(embeddings[0]) if len(embeddings) > 0 else 0
        print(f"   Dimension: {embedding_dims} (attendu: 384 pour all-MiniLM-L6-v2)")

        # Check for zero embeddings
        import numpy as np
        zero_embeddings = 0
        for emb in embeddings:
            if np.all(np.array(emb) == 0):
                zero_embeddings += 1

        print(f"   Embeddings valides: {total_chunks - zero_embeddings}/{total_chunks}")

        if zero_embeddings > 0:
            print(f"   ⚠️  {zero_embeddings} embeddings sont à zéro (problème!)")
        else:
            print(f"   ✅ Tous les embeddings sont non-nuls")
    else:
        print(f"   ❌ Aucun embedding trouvé!")

    # Analyze metadata quality
    print(f"\n🏷️  QUALITÉ DES MÉTADONNÉES")

    metadata_fields = {
        'topics': 0,
        'keywords': 0,
        'summary': 0,
        'concepts': 0,
        'difficulty': 0,
        'programming_languages': 0,
        'frameworks': 0,
        'commit_hash': 0,
        'http_last_modified': 0,
        'http_etag': 0
    }

    for metadata in result['metadatas']:
        for field in metadata_fields.keys():
            if field in metadata and metadata[field]:
                # Check if not empty
                value = metadata[field]
                if isinstance(value, list) and len(value) > 0:
                    metadata_fields[field] += 1
                elif isinstance(value, str) and value.strip():
                    metadata_fields[field] += 1

    print(f"\n   Enrichissement LLM (Mistral 7B):")
    llm_fields = ['topics', 'keywords', 'summary', 'concepts', 'difficulty',
                  'programming_languages', 'frameworks']

    for field in llm_fields:
        count = metadata_fields[field]
        percentage = (count / total_chunks * 100) if total_chunks > 0 else 0
        status = "✅" if percentage > 80 else "⚠️" if percentage > 50 else "❌"
        print(f"   {status} {field:25s}: {count:4d}/{total_chunks:4d} ({percentage:5.1f}%)")

    print(f"\n   Headers HTTP/Git:")
    tracking_fields = ['commit_hash', 'http_last_modified', 'http_etag']

    for field in tracking_fields:
        count = metadata_fields[field]
        percentage = (count / total_chunks * 100) if total_chunks > 0 else 0
        print(f"   {field:25s}: {count:4d}/{total_chunks:4d} ({percentage:5.1f}%)")

    # Analyze content quality
    print(f"\n📝 QUALITÉ DU CONTENU")

    documents = result['documents']

    if documents:
        lengths = [len(doc) for doc in documents]
        avg_length = sum(lengths) / len(lengths)
        min_length = min(lengths)
        max_length = max(lengths)

        print(f"   Longueur moyenne: {avg_length:6.0f} caractères")
        print(f"   Longueur min:     {min_length:6d} caractères")
        print(f"   Longueur max:     {max_length:6d} caractères")

        # Check for suspiciously short chunks
        short_chunks = sum(1 for l in lengths if l < 50)
        if short_chunks > 0:
            print(f"   ⚠️  {short_chunks} chunks très courts (<50 chars)")

        # Check for empty chunks
        empty_chunks = sum(1 for doc in documents if not doc or not doc.strip())
        if empty_chunks > 0:
            print(f"   ❌ {empty_chunks} chunks vides!")
        else:
            print(f"   ✅ Aucun chunk vide")

    # Sample analysis - show 3 random chunks with full metadata
    print(f"\n🔍 EXEMPLES DE CHUNKS (3 échantillons)")

    import random
    sample_indices = random.sample(range(min(total_chunks, 10)), min(3, total_chunks))

    for i, idx in enumerate(sample_indices, 1):
        print(f"\n   --- Échantillon {i} ---")

        metadata = result['metadatas'][idx]
        document = result['documents'][idx]

        print(f"   Source: {metadata.get('source_url', 'N/A')[:80]}")
        print(f"   Type: {metadata.get('source_type', 'N/A')}")
        print(f"   Chunk: {metadata.get('chunk_index', '?')}/{metadata.get('total_chunks', '?')}")

        print(f"\n   Topics: {metadata.get('topics', [])}")
        print(f"   Keywords: {metadata.get('keywords', [])}")
        print(f"   Summary: {metadata.get('summary', 'N/A')[:100]}")
        print(f"   Difficulty: {metadata.get('difficulty', 'N/A')}")
        print(f"   Languages: {metadata.get('programming_languages', [])}")
        print(f"   Frameworks: {metadata.get('frameworks', [])}")

        print(f"\n   Contenu ({len(document)} chars):")
        preview = document[:200] + "..." if len(document) > 200 else document
        print(f"   {preview}")

    # Quality score
    print(f"\n" + "="*100)
    print(f"SCORE DE QUALITÉ GLOBAL")
    print(f"="*100)

    scores = {
        'Embeddings valides': 100 if zero_embeddings == 0 else 0,
        'Topics présents': (metadata_fields['topics'] / total_chunks * 100) if total_chunks > 0 else 0,
        'Keywords présents': (metadata_fields['keywords'] / total_chunks * 100) if total_chunks > 0 else 0,
        'Summary présent': (metadata_fields['summary'] / total_chunks * 100) if total_chunks > 0 else 0,
        'Pas de chunks vides': 100 if empty_chunks == 0 else 0,
    }

    for criterion, score in scores.items():
        status = "✅" if score > 80 else "⚠️" if score > 50 else "❌"
        print(f"{status} {criterion:30s}: {score:5.1f}%")

    avg_score = sum(scores.values()) / len(scores)

    print(f"\n{'─'*100}")
    if avg_score >= 90:
        print(f"🎉 SCORE GLOBAL: {avg_score:.1f}/100 - EXCELLENT !")
    elif avg_score >= 70:
        print(f"✅ SCORE GLOBAL: {avg_score:.1f}/100 - BON")
    elif avg_score >= 50:
        print(f"⚠️  SCORE GLOBAL: {avg_score:.1f}/100 - MOYEN")
    else:
        print(f"❌ SCORE GLOBAL: {avg_score:.1f}/100 - NÉCESSITE AMÉLIORATION")

    print(f"="*100)

    # Recommendations
    print(f"\n💡 RECOMMANDATIONS")

    if metadata_fields['topics'] / total_chunks < 0.8:
        print(f"   • Enrichissement LLM incomplet - vérifier Ollama (Mistral 7B)")

    if zero_embeddings > 0:
        print(f"   • Embeddings à zéro détectés - vérifier sentence-transformers")

    if empty_chunks > 0:
        print(f"   • Chunks vides détectés - vérifier chunking logic")

    if short_chunks > total_chunks * 0.1:
        print(f"   • Beaucoup de chunks courts - ajuster min_chunk_size")

    if avg_score >= 90:
        print(f"   ✅ Qualité excellente - système prêt pour production!")

    print()


if __name__ == "__main__":
    try:
        analyze_chunk_quality()
    except Exception as e:
        print(f"\n❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
