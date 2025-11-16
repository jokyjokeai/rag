## 🚀 Quick Start Guide

### Installation rapide

```bash
# 1. Installation des dépendances
pip install -r requirements.txt

# 2. Installation Playwright pour le scraping web
playwright install

# 3. Configuration
cp .env.example .env

# 4. Installation Ollama (si pas déjà fait)
# Télécharger depuis https://ollama.ai
ollama pull llama3.2
```

### Configuration minimale

Éditez `.env` :

```bash
# Optionnel mais recommandé
BRAVE_API_KEY=votre_cle_ici

# Le reste peut rester par défaut
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.2
```

### Premier test

```bash
# Assurez-vous qu'Ollama est en cours d'exécution
ollama serve

# Dans un autre terminal, lancez le test
python test_orchestrator.py
```

### Utilisation basique

```python
from orchestrator import Orchestrator

# Initialisation
orch = Orchestrator()

# Méthode 1: Ajouter des URLs directement
orch.process_input("https://fastapi.tiangolo.com")

# Méthode 2: Recherche via prompt (nécessite Brave API + Ollama)
orch.process_input("apprendre FastAPI")

# Voir les statistiques
stats = orch.get_stats()
print(stats)

# Fermeture
orch.close()
```

### Obtenir les clés API (optionnel)

**Brave Search API** (2000 requêtes/mois gratuit):
1. Aller sur https://brave.com/search/api/
2. S'inscrire pour un compte développeur
3. Copier la clé API dans `.env`

**YouTube Data API** (gratuit):
1. Google Cloud Console → Créer projet
2. Activer YouTube Data API v3
3. Créer clé API
4. Copier dans `.env`

**GitHub Token** (gratuit):
1. GitHub Settings → Developer settings → Personal access tokens
2. Générer nouveau token (repo read access)
3. Copier dans `.env`

### Vérification de l'installation

```bash
# Vérifier que tout fonctionne
python -c "from orchestrator import Orchestrator; print('✅ Installation OK')"
```

### Structure des données

Après avoir ajouté des URLs, vous trouverez :

```
data/
├── discovered_urls.db    # SQLite avec toutes les URLs
├── chroma_db/           # Vector database (après processing)
└── logs/                # Logs système
    └── rag_system.log
```

### Prochaines étapes

Une fois que l'orchestrator fonctionne :

1. ✅ Les URLs sont stockées dans SQLite
2. 🚧 Implémenter les scrapers pour extraire le contenu
3. 🚧 Processing pipeline pour chunking et embeddings
4. 🚧 MCP server pour intégration Claude Code

### Dépannage

**"ModuleNotFoundError"**
→ `pip install -r requirements.txt`

**"Ollama connection error"**
→ `ollama serve` dans un terminal séparé

**"Brave API key not configured"**
→ OK pour le mode URL direct, nécessaire pour mode prompt

**"Database locked"**
→ Fermez les autres instances de l'orchestrator
