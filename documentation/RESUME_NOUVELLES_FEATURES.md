# Résumé: 5 Nouvelles Features Menu RAG

## ✅ Ce qui a été fait

J'ai ajouté **5 nouvelles fonctionnalités** au menu interactif (`run_rag.py`) :

### 1. 📊 Brave Search Quota (Option 6)
Voir combien de requêtes Brave Search il te reste aujourd'hui.
```
Daily quota : 2000 queries
Used today  : 127
Remaining   : 1873 (93.6%)
```

### 2. ⏰ Auto-Refresh Toggle (Option 7)
Activer/désactiver le refresh automatique sans redémarrer.
```
Auto-refresh : ✅ ENABLED
Schedule     : Monday 3 AM

[1] Toggle ON/OFF
```

### 3. 🗑️ Vider la File d'Attente (Option 8)
Supprimer les URLs pending/failed sans toucher aux URLs scrapées.
```
Pending : 45 URLs
Failed  : 12 URLs

[1] Vider PENDING
[2] Vider FAILED
[3] Vider PENDING + FAILED
```

### 4. 🗑️ Reset Database (Option 9)
Réinitialiser tout le système (SQLite + ChromaDB) avec backup auto.
```
⚠️ Double confirmation requise :
1. Tape "DELETE"
2. Tape la date du jour

✅ Backup créé automatiquement
```

### 5. 📊 Tracking Brave Search
Chaque requête Brave Search est automatiquement loguée (table `api_usage_log`).

---

## 📁 Fichiers Créés

1. `utils/rate_limit_tracker.py` - Track quota Brave
2. `utils/state_manager.py` - Persistence state (JSON)
3. `database/reset_manager.py` - Reset + backup system

---

## 📝 Fichiers Modifiés

1. `orchestrator/web_search.py` - Log Brave queries
2. `scheduler/refresh_scheduler.py` - Toggle() method
3. `config/settings.py` - brave_daily_quota setting
4. `database/models.py` - clear_queue() method
5. `run_rag.py` - Menu étendu (1-10)

---

## 🚀 Utilisation

```bash
python run_rag.py
```

Nouveau menu :
```
1-4  : Sources (comme avant)
5    : Stats (comme avant)
6    : Brave Search quota ← NOUVEAU
7    : Auto-refresh config ← NOUVEAU
8    : Vider file d'attente ← NOUVEAU
9    : Reset database ← NOUVEAU
10   : Quitter
```

---

## 🎯 À retenir

- **Option 6** : Voir le quota Brave restant
- **Option 7** : Toggle auto-refresh ON/OFF
- **Option 8** : Vider pending/failed sans toucher scrapées
- **Option 9** : Reset TOUT (double confirmation + backup auto)

Tout est prêt et fonctionnel ! 🎉
