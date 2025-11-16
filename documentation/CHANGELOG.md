# Changelog - Système RAG Local

## [2025-11-16] - Corrections et Améliorations

### ✅ Corrigé
- **Reset Database**: Gestion robuste des erreurs (fichier inexistant, tables manquantes)
- **API Tracking**: Explication du "0 queries" (normal si aucune recherche Brave)

### ✨ Nouveau
- **Scores de Pertinence**: Affichage visuel de la similarité (🟢🟡🟠🔴) dans recherche sémantique
- **Seuil de Similarité**: Filtrage automatique résultats non pertinents (threshold: 0.3)
- **Mode Interactif C/A/S**: Crawling YouTube avec options [C]rawl 50 / [A]ll 500 / [S]kip / [Q]uit

### 🔧 Modifié
- `database/reset_manager.py` - Gestion d'erreurs SQLite (lignes 174-222)
- `main.py` - Seuil similarité + C/A/S YouTube (lignes 96-195, 220-280)
- `run_rag.py` - Affichage scores pertinence (lignes 129-189)

### 📝 Ajouté
- `AMELIORATIONS_SYSTEME.md` - Documentation complète des améliorations
- `RESUME_FINAL.md` - Guide utilisateur et workflows
- `test_ameliorations.py` - Suite de tests automatiques (4/4 passés ✅)

---

## [2025-11-15] - YouTube et Menu (session précédente)

### ✨ Nouveau
- **Priorisation YouTube**: 70% queries YouTube (30% channels, 20% masterclass, 10% playlists, 10% videos)
- **Scoring URLs**: Chaînes = 5 pts, Playlists = 4 pts, Vidéos = 3 pts
- **Crawl All**: Paramètre `crawl_all=True` pour crawler jusqu'à 500 vidéos/chaîne
- **Menu Options 6-9**:
  - Option 6: Brave Search quota tracker
  - Option 7: Auto-refresh toggle
  - Option 8: Clear queue (pending/failed)
  - Option 9: Database reset avec backup

### 🔧 Modifié
- `orchestrator/query_analyzer.py` - Ratio 70% YouTube
- `orchestrator/web_search.py` - Scoring chaînes/playlists
- `config/settings.py` - Configuration YouTube
- `scrapers/youtube_channel_crawler.py` - Paramètre crawl_all
- `run_rag.py` - Menu étendu (1-10)

### 📝 Ajouté
- `utils/rate_limit_tracker.py` - Tracking quota Brave API
- `utils/state_manager.py` - Persistence state runtime
- `database/reset_manager.py` - Reset + backup system

---

## Tests

Tous les tests passent ✅:
```bash
cd /home/jokyjokeai/Desktop/RAG/rag-local-system
source venv/bin/activate
python test_ameliorations.py
# ✅ 4/4 tests réussis
```

---

## Documentation

- `README.md` - Guide principal
- `AMELIORATIONS_SYSTEME.md` - Détails techniques des améliorations
- `RESUME_FINAL.md` - Guide utilisateur complet
- `RESUME_NOUVELLES_FEATURES.md` - Features menu (session précédente)
