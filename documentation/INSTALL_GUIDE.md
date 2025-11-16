# 🚀 Guide d'Installation - RAG Local System

## ✅ Prérequis

### Obligatoire
- **Python 3.11+**
- **Git** (pour cloner les repos GitHub)
- **Ollama** (pour LLM local)

### Optionnel
- **Brave Search API** (pour recherche web via prompts texte)
- **YouTube Data API** (pour métadonnées vidéos enrichies)

## 📦 Installation Complète

### 1. Créer l'environnement virtuel

```bash
cd /home/jokyjokeai/Desktop/RAG/rag-local-system

# Créer venv
python3 -m venv venv

# Activer venv
source venv/bin/activate
```

Vous devriez voir `(venv)` dans votre terminal.

### 2. Installer les dépendances Python

```bash
pip install -r requirements.txt
```

Cela installe :
- `ollama` - Client Ollama
- `sentence-transformers` - Embeddings locaux
- `chromadb` - Vector database
- `youtube-transcript-api` - Transcriptions YouTube
- `playwright` - Web scraping
- `beautifulsoup4` - HTML parsing
- `langchain` - Text splitting
- `mcp` - Model Context Protocol
- Et autres...

### 3. Installer Playwright browsers

```bash
playwright install
```

Cela télécharge les navigateurs nécessaires pour le scraping web.

### 4. Installer Ollama

Si pas déjà installé :

```bash
# Télécharger depuis https://ollama.ai
# Ou sur Linux :
curl -fsSL https://ollama.com/install.sh | sh

# Démarrer Ollama
ollama serve

# Dans un autre terminal, télécharger le modèle
ollama pull llama3.2
```

### 5. Vérifier que Git est installé

```bash
git --version
```

Si pas installé :
```bash
# Ubuntu/Debian
sudo apt install git

# macOS
brew install git
```

### 6. Configuration

```bash
# Copier le fichier de configuration
cp .env.example .env

# Éditer (optionnel)
nano .env
```

**Configuration minimale** (tout fonctionne sans clés API) :
```bash
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.2
```

**Configuration complète** (optionnel) :
```bash
# Pour recherche web via prompts texte
BRAVE_API_KEY=votre_cle_brave

# Pour métadonnées vidéos YouTube enrichies
YOUTUBE_API_KEY=votre_cle_youtube
```

## ✅ Vérification de l'installation

```bash
# Activer venv si pas déjà fait
source venv/bin/activate

# Tester
python -c "from main import RAGSystem; print('✅ Installation OK')"
```

## 🧪 Premier test

```bash
# Assurez-vous qu'Ollama tourne
ollama serve

# Dans un autre terminal
cd /home/jokyjokeai/Desktop/RAG/rag-local-system
source venv/bin/activate

# Tester l'orchestrator
python test_orchestrator.py
```

## 🚀 Utilisation

### Mode Simple (URLs directes - AUCUNE API nécessaire)

```python
from main import RAGSystem
import asyncio

async def demo():
    rag = RAGSystem()

    # Ajouter des URLs
    rag.add_sources("""
    https://fastapi.tiangolo.com
    https://github.com/tiangolo/fastapi
    https://www.youtube.com/watch?v=0sOvCWFmrtA
    """)

    # Traiter (scraping + chunking + embeddings)
    await rag.process_queue()

    # Rechercher
    results = rag.search("How to create routes?")
    print(results)

    rag.close()

asyncio.run(demo())
```

### Mode Avancé (avec recherche web - nécessite Brave API)

```python
rag = RAGSystem()

# Prompt texte → recherche web → URLs découvertes
rag.add_sources("Python FastAPI async framework")
```

## 🔑 Obtenir les clés API (optionnel)

### Brave Search API (gratuit)
1. Aller sur https://brave.com/search/api/
2. S'inscrire (gratuit, 2000 requêtes/mois)
3. Copier la clé dans `.env` : `BRAVE_API_KEY=...`

### YouTube Data API (gratuit)
1. Google Cloud Console → Créer projet
2. Activer YouTube Data API v3
3. Créer clé API
4. Copier dans `.env` : `YOUTUBE_API_KEY=...`

## 🛠️ Dépendances Système

**Ubuntu/Debian :**
```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv git
```

**macOS :**
```bash
brew install python git
```

## 📊 Ce qui fonctionne SANS aucune API

✅ **Scraping GitHub** - Utilise `git clone` (pas d'API)
✅ **Scraping YouTube** - Transcriptions gratuites via `youtube-transcript-api`
✅ **Scraping Web** - Sites publics avec Playwright
✅ **Processing** - Chunking, embeddings, enrichissement (100% local)
✅ **Search** - Recherche sémantique dans ChromaDB
✅ **MCP Server** - Intégration Claude Code

❌ **Recherche web via prompts** - Nécessite Brave API (mais vous pouvez donner des URLs directement)

## 🐛 Dépannage

**Erreur "ollama connection refused"**
```bash
# Démarrer Ollama dans un terminal séparé
ollama serve
```

**Erreur "git command not found"**
```bash
sudo apt install git  # Ubuntu
brew install git      # macOS
```

**Erreur "ModuleNotFoundError"**
```bash
# Vérifier que venv est activé
source venv/bin/activate
# Réinstaller
pip install -r requirements.txt
```

**Erreur Playwright**
```bash
playwright install
```

## 📝 Notes Importantes

1. **Venv doit être activé** pour chaque session :
   ```bash
   source venv/bin/activate
   ```

2. **Ollama doit tourner** en arrière-plan :
   ```bash
   ollama serve
   ```

3. **Git doit être installé** pour scraper GitHub

4. **APIs sont optionnelles** - Le système fonctionne sans !

---

**Vous êtes prêt ! 🎉**

Commencez par `python test_orchestrator.py` pour vérifier que tout fonctionne.
