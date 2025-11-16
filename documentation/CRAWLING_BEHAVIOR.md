# Comportement du crawling - Guide détaillé

## Vue d'ensemble

Le système RAG décide automatiquement **quand crawler** (découvrir toutes les pages d'un site) vs **quand scraper** (extraire le contenu d'une seule page).

---

## Décision automatique : Crawl vs Scrape

### Flux de décision

```
URL ajoutée à la queue
    ↓
Est-ce un site web ?
    ├─ NON (YouTube/GitHub) → Scrape/Traitement spécifique
    └─ OUI → Est-ce découvert d'un crawl précédent ?
        ├─ OUI → Scrape direct (évite crawl récursif)
        └─ NON → Correspond aux patterns de documentation ?
            ├─ OUI → CRAWL (découvre 1-1000 pages)
            └─ NON → SCRAPE (page unique)
```

---

## Patterns de détection du crawling

### 🕷️ Sites crawlés automatiquement

#### 1. Domaines de documentation
- `docs.example.com` - Sous-domaine "docs"
- `doc.example.com` - Sous-domaine "doc"
- `documentation.example.com` - Sous-domaine "documentation"

#### 2. Plateformes de documentation
- `*.readthedocs.io` - ReadTheDocs
- `*.gitbook.io` - GitBook
- `*.notion.site` - Notion sites publics
- `*.readme.io` - ReadMe.io

#### 3. Wikis et Confluence
- Domaine contient `wiki`
- Domaine contient `confluence`

#### 4. Guides et tutoriels (dans le path)
- `/tutorial/` - Tutoriels
- `/guide/` - Guides
- `/learn/` - Sections d'apprentissage

#### 5. Blogs (dans le path)
- `/blog/` - Blogs
- `/article/` - Articles
- `/post/` - Posts
- `/news/` - News

### Exemples concrets

| URL | Crawlé ? | Raison |
|-----|----------|--------|
| `https://docs.python.org` | ✅ Oui | Domaine contient "docs" |
| `https://fastapi.tiangolo.com/tutorial/` | ✅ Oui | Path contient "tutorial" |
| `https://wiki.archlinux.org` | ✅ Oui | Domaine contient "wiki" |
| `https://example.com/blog/article-1` | ✅ Oui | Path contient "blog" |
| `https://company.com/product` | ❌ Non | Aucun pattern |
| `https://signalwire.com/freeswitch` | ❌ Non | Aucun pattern |
| `https://blog.example.com/2024/article` | ❌ Non | "blog" dans domaine, pas dans path |

**Note importante** : Le pattern doit être dans le **path** pour `/blog`, `/tutorial`, etc., pas seulement dans le domaine.

---

## Processus de crawling

### Phase 1 : Découverte des pages

1. **Démarrage** : Le crawler visite l'URL de départ
2. **Extraction des liens** : Parse tous les liens `<a href="...">`
3. **Filtrage** :
   - Même domaine uniquement (par défaut)
   - Exclut les fichiers (images, PDF, ZIP, etc.)
   - Exclut les patterns non-pertinents (`/login`, `/search`, `/admin`)
4. **Queue** : Ajoute les nouveaux liens à visiter
5. **Récursion** : Répète jusqu'à atteindre `max_pages` (default: 1000)

### Phase 2 : Ajout à la queue

- Toutes les pages découvertes sont ajoutées à la base de données
- **Status** : `pending` (en attente de scraping)
- **Source** : `discovered_from='website_crawl:URL_ORIGINE'`
- **Priority** : 50 (priorité moyenne)
- **Dédoublonnage** : URLs déjà en base sont skip

### Phase 3 : Scraping ultérieur

- Les pages découvertes seront traitées dans le prochain batch
- Chaque page est scrapée individuellement (pas de re-crawl)
- Le contenu est chunké, embedé et stocké dans ChromaDB

---

## Limites et paramètres

### Paramètres configurables

| Paramètre | Valeur par défaut | Description |
|-----------|-------------------|-------------|
| `max_pages` | 1000 | Nombre maximum de pages à découvrir |
| `same_domain_only` | `True` | Rester sur le même domaine |
| `timeout` | 10000 ms | Timeout de chargement par page |
| `delay` | 0.5s | Délai entre chaque page |

### Fichiers exclus automatiquement

**Extensions ignorées** :
- Images : `.jpg`, `.jpeg`, `.png`, `.gif`, `.svg`, `.webp`
- Vidéos : `.mp4`, `.avi`, `.mov`
- Documents : `.pdf`, `.zip`, `.tar`, `.gz`, `.rar`
- Exécutables : `.exe`, `.dmg`, `.iso`

**Paths ignorés** :
- `/search`, `/login`, `/signup`
- `/cart`, `/checkout`, `/account`
- `/admin`, `/api/`

---

## Cas d'usage

### Cas 1 : Documentation officielle

**Input** :
```
https://docs.fastapi.tiangolo.com
```

**Résultat** :
- ✅ Détecté comme doc (domaine "docs")
- 🕷️ Crawl de toute la documentation
- 📄 Découvre ~200-500 pages
- ⏱️ Durée : 3-8 minutes
- 💾 Toutes les pages ajoutées à la queue

### Cas 2 : Article de blog unique

**Input** :
```
https://company.com/blog/my-article
```

**Résultat** :
- ✅ Détecté comme blog (path "/blog")
- 🕷️ Crawl du blog entier
- 📄 Découvre tous les articles
- ⚠️ **Attention** : Va crawler TOUS les articles, pas juste celui-ci

### Cas 3 : Site web générique

**Input** :
```
https://signalwire.com/freeswitch
```

**Résultat** :
- ❌ Pas de pattern détecté
- 📄 Scrape de cette page uniquement
- ⏱️ Durée : 1-3 secondes
- 💾 1 chunk ajouté à ChromaDB

### Cas 4 : GitHub Repository

**Input** :
```
https://github.com/user/repo
```

**Résultat** :
- 🔧 Traitement spécial GitHub
- 📄 Clone sparse (README + docs/)
- 📚 Pas de crawling web
- 💾 Fichiers markdown + code pertinent

---

## Stratégies pour les sites non-crawlés

Si un site important n'est **pas** détecté comme documentation :

### Option 1 : Ajouter les URLs manuellement

```python
# Ajouter les pages une par une
urls = [
    "https://site.com/page1",
    "https://site.com/page2",
    "https://site.com/page3"
]
for url in urls:
    rag.add_sources(url)
```

### Option 2 : Utiliser la recherche par prompt

```python
# Le système découvrira automatiquement des URLs pertinentes
rag.add_sources("tutoriels complets sur FreeSWITCH")
```

Le prompt déclenchera :
1. Analyse Ollama → génération de requêtes de recherche
2. Brave Search → découverte d'URLs
3. Filtrage → sélection des URLs pertinentes
4. Crawl automatique des docs trouvées

### Option 3 : Modifier les patterns (développeurs)

**Fichier** : `scrapers/web_crawler.py` (ligne 184-230)

Ajouter votre domaine/pattern :
```python
# Documentation sites - always crawl
doc_patterns = [
    'docs.', 'doc.', 'documentation',
    'wiki', 'confluence',
    'readthedocs', 'gitbook',
    'YOUR_SITE_PATTERN'  # Ajoutez ici
]
```

---

## FAQ

### Q : Pourquoi ne pas crawler tous les sites ?

**R** : Raisons techniques et pratiques :
1. **Performance** : Un site peut avoir des milliers de pages
2. **Pertinence** : Beaucoup de pages ne sont pas du contenu (login, contact, etc.)
3. **Ressources** : Limite le temps de traitement et l'espace disque
4. **Qualité** : Les docs structurées ont un meilleur signal/bruit

### Q : Comment savoir si un site sera crawlé ?

**R** : Vérifiez si l'URL contient :
- `docs.` ou `doc.` dans le domaine
- `wiki`, `confluence` dans le domaine
- `/tutorial`, `/guide`, `/blog` dans le path
- Ou une plateforme reconnue (readthedocs, gitbook, etc.)

### Q : Puis-je forcer le crawling d'un site ?

**R** : Actuellement, non. Le comportement est automatique. Solutions de contournement :
1. Ajouter manuellement les URLs importantes
2. Utiliser une recherche par prompt
3. Modifier les patterns dans le code (pour développeurs)

### Q : Combien de temps prend un crawl ?

**R** : Dépend du nombre de pages :
- 50 pages : ~30 secondes - 1 minute
- 200 pages : ~2-4 minutes
- 1000 pages : ~8-15 minutes

**Formule approximative** : `temps = nombre_pages × 0.5s`

### Q : Le crawl peut-il dépasser 1000 pages ?

**R** : Non, limite fixée à 1000 pages par crawl pour éviter :
- Temps de traitement excessif
- Surcharge réseau
- Problèmes de mémoire

Si un site a plus de 1000 pages, seules les 1000 premières découvertes seront indexées.

---

## Logs et feedback

### Logs de progression

Pendant un crawl, vous verrez :

```
🕷️  Crawling: https://docs.example.com (max: 1000 pages)

📄 [1/1000] https://docs.example.com/index.html...
   → 45 links found | Queue: 35 | Visited: 1

📄 [10/1000] https://docs.example.com/getting-started...
   → 23 links found | Queue: 143 | Visited: 10

🔄 Progress: 20/1000 pages | Queue: 62 | Elapsed: 15s | ETA: ~8min

📄 [50/1000] https://docs.example.com/advanced/...
   → 18 links found | Queue: 287 | Visited: 50

✅ Crawling complete: discovered 243 pages in 3m 24s

💾 Adding 243 discovered pages to database...
   [50/243] Added 44 new, skipped 6 duplicates
   [100/243] Added 88 new, skipped 12 duplicates

✅ Website crawled successfully!
```

### Message pour les sites non-crawlés

```
ℹ️  Single page scrape (not detected as documentation site)
   💡 Crawling triggers for: docs.*, wiki, tutorial, blog, readthedocs, etc.
Scraping web page: https://example.com/page
```

---

## Fichiers de code impliqués

| Fichier | Rôle |
|---------|------|
| `scrapers/web_crawler.py` | Logique de crawling et patterns de détection |
| `queue_processor/integrated_processor.py` | Décision crawl vs scrape |
| `database/models.py` | Stockage des URLs découvertes |
| `config/settings.py` | Configuration (futurs paramètres) |

---

## Améliorations futures envisagées

- [ ] Configuration : `WEBSITE_CRAWL_MODE = "documentation_only" | "all" | "none"`
- [ ] Choix utilisateur : "Voulez-vous crawler ce site ?" (mode interactif)
- [ ] Liste blanche/noire de domaines
- [ ] Détection intelligente via sitemap.xml
- [ ] Analyse de robots.txt pour les limites
- [ ] Crawl par profondeur (depth-first vs breadth-first)
- [ ] Crawler les sites dynamiques (SPA/React)

---

**Dernière mise à jour** : Version 1.0 (2025-11-16)
