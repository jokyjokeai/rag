#!/usr/bin/env python3
"""
Script interactif pour tester le système RAG.
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime
sys.path.insert(0, str(Path(__file__).parent))

from main import RAGSystem
from processing import Embedder


async def main():
    """Test interactif du système RAG."""

    print("\n" + "="*80)
    print("🚀 SYSTÈME RAG LOCAL - TEST INTERACTIF")
    print("="*80 + "\n")

    # Initialiser le système
    print("📦 Initialisation du système...")
    rag = RAGSystem()
    print("✅ Système initialisé !\n")

    while True:
        print("="*80)
        print("MENU PRINCIPAL")
        print("="*80)
        print()
        print("=== SOURCES ===")
        print("1. 🔍 Ajouter sources (mode interactif)")
        print("2. 📝 Ajouter sources (direct)")
        print("3. ⚙️  Processer la file d'attente")
        print("4. 🔎 Rechercher dans la base")
        print()
        print("=== SYSTÈME ===")
        print("5. 📊 Statistiques système")
        print("6. 📊 Brave Search quota")
        print("7. ⏰ Configuration auto-refresh")
        print("8. 🗑️  Vider la file d'attente")
        print("9. 🗑️  Reset database (ADMIN)")
        print()
        print("10. ❌ Quitter")
        print()

        choice = input("Votre choix (1-10) : ").strip()

        if choice == "1":
            # Mode interactif
            print("\n" + "="*80)
            print("MODE INTERACTIF - Ajout de Sources")
            print("="*80 + "\n")
            print("💡 Exemples de prompts :")
            print("   - 'FastAPI tutorials'")
            print("   - 'Python async programming'")
            print("   - 'https://docs.python.org'")
            print("   - 'https://github.com/user/repo'")
            print()

            user_input = input("Entrez votre prompt ou URL : ").strip()

            if user_input:
                try:
                    result = rag.add_sources(user_input, interactive=True)
                    print(f"\n✅ Terminé !")
                    print(f"   URLs ajoutées : {result.get('urls_added', 0)}")
                    print(f"   URLs ignorées : {result.get('urls_skipped', 0)}")
                except Exception as e:
                    print(f"\n❌ Erreur : {e}")
            else:
                print("\n⚠️  Aucun input fourni")

        elif choice == "2":
            # Mode direct
            print("\n" + "="*80)
            print("MODE DIRECT - Ajout de Sources")
            print("="*80 + "\n")

            user_input = input("Entrez votre prompt ou URLs : ").strip()

            if user_input:
                try:
                    result = rag.add_sources(user_input, interactive=False)
                    print(f"\n✅ URLs ajoutées : {result.get('urls_added', 0)}")
                    print(f"   URLs ignorées : {result.get('urls_skipped', 0)}")
                except Exception as e:
                    print(f"\n❌ Erreur : {e}")
            else:
                print("\n⚠️  Aucun input fourni")

        elif choice == "3":
            # Processer la queue
            print("\n" + "="*80)
            print("PROCESSING DE LA FILE D'ATTENTE")
            print("="*80 + "\n")

            max_batches = input("Nombre de batches (vide = illimité) : ").strip()
            max_batches = int(max_batches) if max_batches else None

            print("\n⏳ Processing en cours...\n")

            try:
                result = await rag.process_queue(max_batches=max_batches)
                print(f"\n✅ Processing terminé !")
                print(f"   URLs traitées   : {result['total_processed']}")
                print(f"   Succès          : {result['total_succeeded']}")
                print(f"   Échecs          : {result['total_failed']}")
            except Exception as e:
                print(f"\n❌ Erreur : {e}")
                import traceback
                traceback.print_exc()

        elif choice == "4":
            # Rechercher
            print("\n" + "="*80)
            print("RECHERCHE SÉMANTIQUE")
            print("="*80 + "\n")

            query = input("Votre question : ").strip()

            if query:
                n_results = input("Nombre de résultats (défaut: 5) : ").strip()
                n_results = int(n_results) if n_results else 5

                print(f"\n🔍 Recherche en cours...\n")

                try:
                    results = rag.search(query, n_results=n_results)

                    if results['documents'] and len(results['documents'][0]) > 0:
                        print(f"✅ Trouvé {len(results['documents'][0])} résultats pertinents :\n")

                        # Get similarities if available
                        similarities = results.get('similarities', [[]] * len(results['documents']))[0]
                        distances = results.get('distances', [[]] * len(results['documents']))[0]

                        for i, (doc, meta) in enumerate(zip(results['documents'][0], results['metadatas'][0]), 1):
                            print("─" * 80)
                            print(f"RÉSULTAT #{i}")
                            print("─" * 80)

                            source = meta.get('source_url', 'N/A')
                            if len(source) > 70:
                                source = source[:70] + "..."

                            print(f"📄 Source    : {source}")
                            print(f"🏷️  Type      : {meta.get('source_type', 'N/A')}")

                            # Display similarity score if available
                            if similarities and i <= len(similarities):
                                similarity_score = similarities[i-1]
                                similarity_percent = similarity_score * 100

                                # Color-code based on similarity
                                if similarity_percent >= 80:
                                    indicator = "🟢 Excellente"
                                elif similarity_percent >= 60:
                                    indicator = "🟡 Bonne"
                                elif similarity_percent >= 40:
                                    indicator = "🟠 Moyenne"
                                else:
                                    indicator = "🔴 Faible"

                                print(f"⚡ Pertinence: {indicator} ({similarity_percent:.1f}%)")

                            # Handle metadata that may be stored as comma-separated strings
                            topics = meta.get('topics', '')
                            if isinstance(topics, str):
                                # Already a comma-separated string from ChromaDB
                                topics_display = topics.split(', ')[:3]
                                topics_str = ', '.join(topics_display) if topics_display else ''
                            elif isinstance(topics, list):
                                topics_str = ', '.join(topics[:3])
                            else:
                                topics_str = ''

                            keywords = meta.get('keywords', '')
                            if isinstance(keywords, str):
                                # Already a comma-separated string from ChromaDB
                                keywords_display = keywords.split(', ')[:5]
                                keywords_str = ', '.join(keywords_display) if keywords_display else ''
                            elif isinstance(keywords, list):
                                keywords_str = ', '.join(keywords[:5])
                            else:
                                keywords_str = ''

                            print(f"📌 Topics    : {topics_str}")
                            print(f"🔑 Keywords  : {keywords_str}")
                            print(f"📊 Difficulty: {meta.get('difficulty', 'N/A')}")
                            print()
                            print(f"📝 Résumé : {meta.get('summary', 'N/A')}")
                            print()
                            print(f"💬 Contenu (extrait) :")
                            content_preview = doc[:300] + "..." if len(doc) > 300 else doc
                            print(f"   {content_preview}")
                            print()

                    else:
                        print("⚠️  Aucun résultat pertinent trouvé")
                        print("   Causes possibles :")
                        print("   - La base de données ne contient pas d'informations sur ce sujet")
                        print("   - Les résultats étaient trop peu pertinents (score < seuil)")
                        print("   - Ajoutez des sources liées à votre recherche avec Option 1-4")

                except Exception as e:
                    print(f"\n❌ Erreur : {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print("\n⚠️  Aucune question fournie")

        elif choice == "5":
            # Statistiques
            print("\n" + "="*80)
            print("STATISTIQUES DU SYSTÈME")
            print("="*80 + "\n")

            try:
                stats = rag.get_stats()

                print("📊 BASE DE DONNÉES (SQLite) :")
                db_stats = stats['database']
                print(f"   Total URLs       : {db_stats['total']}")
                print(f"   Pending          : {db_stats['pending']}")
                print(f"   Scraped          : {db_stats['scraped']}")
                print(f"   Failed           : {db_stats['failed']}")
                print()

                print("🔢 VECTOR STORE (ChromaDB) :")
                vs_stats = stats['vector_store']
                print(f"   Total chunks     : {vs_stats['total_chunks']}")
                print()

                if db_stats.get('by_type'):
                    print("📁 PAR TYPE DE SOURCE :")
                    for source_type, count in db_stats['by_type'].items():
                        print(f"   {source_type:20s}: {count:4d}")

                # Info message if database is empty
                if db_stats['total'] == 0 and vs_stats['total_chunks'] == 0:
                    print("\nℹ️  La base de données est vide")
                    print("   Utilisez l'option 1 ou 2 pour ajouter des sources\n")

            except Exception as e:
                print(f"\n❌ Erreur lors de la récupération des statistiques")
                if "does not exist" in str(e).lower():
                    print("ℹ️  La base de données est vide ou vient d'être réinitialisée")
                    print("   Ajoutez des sources pour voir des statistiques\n")
                else:
                    print(f"   Détails : {e}\n")

        elif choice == "6":
            # Brave Search quota
            print("\n" + "="*80)
            print("BRAVE SEARCH API - RATE LIMIT")
            print("="*80 + "\n")

            try:
                from utils.rate_limit_tracker import RateLimitTracker
                from config import settings

                tracker = RateLimitTracker()
                status = tracker.get_rate_limit_status(daily_quota=settings.brave_daily_quota)

                # Status icon
                if status['usage_percent'] < 50:
                    status_icon = "✅"
                elif status['usage_percent'] < 80:
                    status_icon = "⚠️ "
                else:
                    status_icon = "🔴"

                print(f"{status_icon} QUOTA STATUS")
                print()
                print(f"   Daily quota      : {status['daily_quota']:4d} queries")
                print(f"   Used today       : {status['queries_used']:4d}")
                print(f"   Remaining        : {status['queries_remaining']:4d} ({100 - status['usage_percent']:.1f}%)")
                print(f"   Reset in         : {status['reset_in_hours']}h {status['reset_in_minutes']}min")
                print()

                print(f"📈 PERFORMANCE")
                print()
                print(f"   Success rate     : {status['queries_success']:4d} / {status['queries_used']:4d}")
                print(f"   Failed           : {status['queries_failed']:4d}")
                print(f"   Avg response     : {status['avg_response_time_ms']:4d} ms")
                print()

                # Recent queries
                print(f"📋 RECENT QUERIES (Last 5)")
                print()
                recent = tracker.get_recent_queries(limit=5)
                if recent:
                    for i, query_info in enumerate(recent, 1):
                        timestamp = query_info['timestamp']
                        query_text = query_info['query'][:50]
                        success_icon = "✅" if query_info['success'] else "❌"
                        print(f"   {i}. {success_icon} [{timestamp}] {query_text}")
                else:
                    print("   Aucune requête enregistrée")

                # Warning if quota high
                if status['usage_percent'] >= 80:
                    print()
                    print("⚠️  WARNING: 80%+ du quota utilisé !")
                    print("   Considérez limiter les recherches pour aujourd'hui.")

            except Exception as e:
                print(f"❌ Erreur : {e}")
                import traceback
                traceback.print_exc()

        elif choice == "7":
            # Auto-refresh configuration
            print("\n" + "="*80)
            print("AUTO-REFRESH CONFIGURATION")
            print("="*80 + "\n")

            try:
                from utils.state_manager import StateManager
                from scheduler.refresh_scheduler import RefreshScheduler

                state = StateManager()
                enabled = state.get_auto_refresh_status()
                schedule = state.get_refresh_schedule()
                last_toggle = state.get_last_toggle_time()

                # Status
                status_icon = "✅ ENABLED" if enabled else "❌ DISABLED"
                print(f"📊 STATUS")
                print()
                print(f"   Auto-refresh     : {status_icon}")
                print(f"   Schedule         : {schedule}")

                # Try to get next run time if enabled
                if enabled:
                    try:
                        scheduler = RefreshScheduler()
                        next_run = scheduler.get_next_run_time()
                        print(f"   Next refresh     : {next_run}")
                    except:
                        print(f"   Next refresh     : (scheduler not running)")

                if last_toggle:
                    print(f"   Last toggle      : {last_toggle}")

                print()

                # Options
                print("OPTIONS :")
                print()
                print("   [1] Toggle ON/OFF")
                print("   [2] Retour au menu")
                print()

                sub_choice = input("Votre choix : ").strip()

                if sub_choice == "1":
                    # Toggle
                    print()
                    confirmation = input(f"{'Désactiver' if enabled else 'Activer'} auto-refresh ? (o/n) : ").strip().lower()

                    if confirmation in ['o', 'oui', 'y', 'yes']:
                        new_state = state.toggle_auto_refresh()

                        if new_state:
                            print("\n✅ Auto-refresh ACTIVÉ !")
                            print("   Le scheduler vérifiera les sources selon le planning.")
                        else:
                            print("\n✅ Auto-refresh DÉSACTIVÉ !")
                            print("   Le scheduler ne fera plus de refresh automatique.")
                    else:
                        print("\n⚠️  Opération annulée")

            except Exception as e:
                print(f"❌ Erreur : {e}")
                import traceback
                traceback.print_exc()

        elif choice == "8":
            # Vider la file d'attente
            print("\n" + "="*80)
            print("VIDER LA FILE D'ATTENTE")
            print("="*80 + "\n")

            try:
                from database import URLDatabase

                url_db = URLDatabase()
                stats = url_db.get_stats()

                print("📊 ÉTAT ACTUEL DE LA FILE :")
                print()
                print(f"   Pending          : {stats['pending']} URLs")
                print(f"   Failed           : {stats['failed']} URLs")
                print(f"   Scraped (gardés) : {stats['scraped']} URLs")
                print()

                if stats['pending'] == 0 and stats['failed'] == 0:
                    print("✅ La file d'attente est déjà vide !")
                else:
                    print("OPTIONS :")
                    print()
                    print("   [1] Vider PENDING seulement")
                    print("   [2] Vider FAILED seulement")
                    print("   [3] Vider PENDING + FAILED")
                    print("   [4] Annuler")
                    print()

                    sub_choice = input("Votre choix : ").strip()

                    if sub_choice in ["1", "2", "3"]:
                        filter_map = {
                            "1": "pending",
                            "2": "failed",
                            "3": "all"
                        }
                        status_filter = filter_map[sub_choice]

                        print()
                        confirmation = input("⚠️  Confirmer la suppression ? (o/n) : ").strip().lower()

                        if confirmation in ['o', 'oui', 'y', 'yes']:
                            deleted_count = url_db.clear_queue(status_filter=status_filter)

                            print(f"\n✅ {deleted_count} URLs supprimées de la file d'attente !")
                        else:
                            print("\n⚠️  Opération annulée")
                    elif sub_choice == "4":
                        print("\n⚠️  Opération annulée")
                    else:
                        print("\n⚠️  Choix invalide")

                url_db.close()

            except Exception as e:
                print(f"❌ Erreur : {e}")
                import traceback
                traceback.print_exc()

        elif choice == "9":
            # Reset database (ADMIN)
            print("\n" + "="*80)
            print("🔴 RESET DATABASE (ADMIN - DESTRUCTIF)")
            print("="*80 + "\n")

            try:
                from database.reset_manager import ResetManager

                reset_mgr = ResetManager()
                sizes = reset_mgr.get_database_sizes()

                print("⚠️  WARNING: Cette action va SUPPRIMER TOUTES LES DONNÉES !")
                print()
                print("📊 TAILLES DES DATABASES :")
                print()
                print(f"   SQLite   : {sizes['sqlite_size_mb']:.2f} MB ({sizes['sqlite_url_count']} URLs)")
                print(f"   ChromaDB : {sizes['chroma_size_mb']:.2f} MB ({sizes['chroma_chunk_count']} chunks)")
                print(f"   TOTAL    : {sizes['total_size_mb']:.2f} MB")
                print()

                print("✅ Un backup automatique sera créé avant le reset.")
                print()

                # Step 1: First confirmation
                print("─" * 80)
                print("ÉTAPE 1/2 : PREMIÈRE CONFIRMATION")
                print("─" * 80)
                print()
                confirm1 = input("Tapez 'DELETE' pour continuer : ").strip()

                if confirm1 == "DELETE":
                    # Step 2: Date confirmation
                    print()
                    print("─" * 80)
                    print("ÉTAPE 2/2 : CONFIRMATION FINALE")
                    print("─" * 80)
                    print()
                    today = datetime.now().strftime('%Y-%m-%d')
                    print(f"Tapez la date d'aujourd'hui ({today}) pour confirmer le reset :")
                    confirm2 = input("Date : ").strip()

                    if confirm2 == today:
                        # Perform reset
                        print()
                        print("🔄 Création du backup...")

                        result = reset_mgr.reset_all(create_backup=True)

                        if result['success']:
                            print()
                            print("✅ RESET TERMINÉ AVEC SUCCÈS !")
                            print()
                            print(f"   Backup créé : {result['backup_path']}")
                            print(f"   SQLite reset : {'✅' if result['sqlite_reset'] else '❌'}")
                            print(f"   ChromaDB reset : {'✅' if result['chromadb_reset'] else '❌'}")
                            print()
                            print("📊 Toutes les données ont été supprimées.")
                            print("💾 Un backup est disponible pour restauration si besoin.")
                        else:
                            print()
                            print(f"❌ ÉCHEC DU RESET : {result.get('error', 'Unknown error')}")

                            if result['backup_created']:
                                print(f"✅ Backup créé : {result['backup_path']}")
                                print("⚠️  Les données n'ont PAS été modifiées (échec du reset).")
                    else:
                        print("\n⚠️  Date incorrecte - reset annulé")
                else:
                    print("\n⚠️  Confirmation incorrecte - reset annulé")

            except Exception as e:
                print(f"❌ Erreur : {e}")
                import traceback
                traceback.print_exc()

        elif choice == "10":
            # Quitter
            print("\n👋 Au revoir !\n")
            rag.close()
            break

        else:
            print("\n⚠️  Choix invalide (utilisez 1-10)\n")

        print()
        input("Appuyez sur Entrée pour continuer...")
        print()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Arrêt du programme...\n")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ ERREUR : {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
