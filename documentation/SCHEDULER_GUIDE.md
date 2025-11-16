# 🔄 Guide du Refresh Scheduler

## ✅ Qu'est-ce que c'est ?

Le **Refresh Scheduler** maintient automatiquement votre base de connaissances à jour en :
1. Vérifiant périodiquement les sources
2. Détectant les changements de contenu
3. Mettant à jour uniquement ce qui a changé

## 📅 Planning par défaut

**Tous les lundis à 3h du matin** (configurable dans `.env`)

```bash
REFRESH_SCHEDULE=0 3 * * 1
# Format cron: minute heure jour mois jour_semaine
# 0 3 * * 1 = Lundi 3h00
```

## 🎯 Fréquences de refresh par type

| Type de source | Fréquence | Raison |
|----------------|-----------|---------|
| **Documentation/Sites web** | Hebdomadaire | Peut être mise à jour |
| **Repos GitHub** | Hebdomadaire | Nouveaux commits possibles |
| **Chaînes YouTube** | Hebdomadaire | Nouvelles vidéos possibles |
| **Vidéos YouTube** | Jamais | Contenu statique |

## 🔄 Comment ça fonctionne ?

### Processus de refresh

```
1. Sélection des URLs
   - status = 'scraped' (déjà traitées)
   - refresh_frequency != 'never'
   - next_refresh_at <= NOW

2. Pour chaque URL :
   a) Re-scrape le contenu
   b) Calcule hash MD5 du nouveau contenu
   c) Compare avec ancien hash

   Si différent :
      - Supprime anciens chunks (ChromaDB)
      - Process nouveau contenu
      - Stocke nouveaux chunks

   Si identique :
      - Skip (pas de changement)

   d) Update next_refresh_at (+7 jours)

3. Logs et statistiques
```

## 🚀 Utilisation

### Option 1 : Service dédié (recommandé)

Lance le scheduler comme service séparé :

```bash
# Terminal dédié au scheduler
cd rag-local-system
source venv/bin/activate
python run_scheduler.py
```

**Avantages** :
- Tourne en arrière-plan
- Indépendant du reste
- Logs dédiés

### Option 2 : Intégré au système

Lance le système complet avec scheduler :

```bash
python main_with_scheduler.py
```

**Avantages** :
- Tout-en-un
- Plus simple

### Option 3 : Refresh manuel

```python
from scheduler import RefreshScheduler
import asyncio

async def manual_refresh():
    scheduler = RefreshScheduler()
    await scheduler.run_refresh_now()
    scheduler.close()

asyncio.run(manual_refresh())
```

## ⚙️ Configuration

### Dans `.env`

```bash
# Activer/désactiver le scheduler
ENABLE_AUTO_REFRESH=true

# Schedule (format cron)
REFRESH_SCHEDULE=0 3 * * 1  # Lundi 3h

# Exemples d'autres schedules :
# 0 2 * * *     # Tous les jours à 2h
# 0 0 * * 0     # Dimanche minuit
# 0 */6 * * *   # Toutes les 6 heures
# 0 0 1 * *     # 1er de chaque mois minuit
```

## 📊 Monitoring

### Logs

Le scheduler log tout dans `data/logs/rag_system.log` :

```
2025-11-15 03:00:00 | INFO | Starting scheduled refresh job
2025-11-15 03:00:01 | INFO | Found 45 URLs to refresh
2025-11-15 03:00:05 | INFO | Content changed for https://... - updating...
2025-11-15 03:00:10 | INFO | Content unchanged for https://...
2025-11-15 03:05:23 | INFO | Refresh job complete: {'processed': 45, 'updated': 12, 'unchanged': 30, 'failed': 3}
```

### Stats après refresh

```python
from scheduler import RefreshScheduler
import asyncio

async def check_stats():
    scheduler = RefreshScheduler()

    # Lancer refresh manuel
    await scheduler.run_refresh_now()

    # Voir les stats
    stats = scheduler.url_db.get_stats()
    print(stats)

    scheduler.close()

asyncio.run(check_stats())
```

## 🔍 Détection des changements

Le système utilise **hash MD5** du contenu pour détecter les changements :

```python
# Hash du contenu
new_hash = md5(scraped_content).hexdigest()

# Comparaison avec ancien hash (stocké dans métadonnées ChromaDB)
if new_hash != old_hash:
    # Contenu a changé → Update
    delete_old_chunks()
    process_new_content()
else:
    # Aucun changement → Skip
    pass
```

## 🎯 Use Cases

### Use Case 1 : Documentation officielle

```
FastAPI docs → Refresh hebdomadaire
- Lundi 3h : Check la doc
- Si nouvelle version : Update automatique
- Votre RAG reste à jour ✅
```

### Use Case 2 : Chaîne YouTube tech

```
@ArjanCodes → Refresh hebdomadaire
- Lundi 3h : Check nouvelles vidéos
- Nouvelles vidéos détectées : Scrape transcriptions
- Base RAG enrichie automatiquement ✅
```

### Use Case 3 : Repo GitHub actif

```
langchain/langchain → Refresh hebdomadaire
- Lundi 3h : Check nouveaux commits
- Code modifié : Re-scrape et update
- Base RAG synchronisée avec latest ✅
```

## 🛑 Arrêter le scheduler

### Si lancé avec run_scheduler.py

```bash
# Dans le terminal du scheduler
Ctrl + C
```

### Si lancé avec main_with_scheduler.py

```bash
Ctrl + C
```

### Programmatiquement

```python
scheduler = RefreshScheduler()
scheduler.start()

# ... plus tard ...

scheduler.stop()
scheduler.close()
```

## 💡 Tips

**Optimiser la performance** :
- Ajustez `REFRESH_SCHEDULE` selon vos besoins
- Sources stables → refresh mensuel
- Sources dynamiques → refresh hebdomadaire

**Économiser les ressources** :
- Désactiver pour sources statiques (vidéos YouTube)
- Limiter le nombre de sources à refresh par job (actuellement 100 max)

**Debugging** :
- Check logs dans `data/logs/rag_system.log`
- Niveau détail : `LOG_LEVEL=DEBUG` dans `.env`
- Test manuel : `scheduler.run_refresh_now()`

## 📈 Performance

**Temps estimé par refresh** :
- Documentation : ~5-10s par site
- GitHub repo : ~10-20s par repo
- Chaîne YouTube : ~5s + 3s par nouvelle vidéo

**Pour 100 sources** :
- Durée totale : ~20-30 minutes
- Seulement les changements sont processés
- Sources inchangées : <1s chacune

---

**Le scheduler maintient votre RAG à jour automatiquement ! 🔄✅**
