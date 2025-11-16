# MCP Integration avec Claude Desktop/Code

## 📖 Table des matières

1. [Qu'est-ce que MCP ?](#quest-ce-que-mcp-)
2. [Comment ça fonctionne](#comment-ça-fonctionne)
3. [Installation](#installation)
4. [Utilisation avec Claude](#utilisation-avec-claude)
5. [Outils disponibles](#outils-disponibles)
6. [FAQ](#faq)

---

## Qu'est-ce que MCP ?

**MCP (Model Context Protocol)** est un protocole développé par Anthropic qui permet à Claude Desktop/Code de communiquer avec des serveurs externes pour accéder à des données et des outils.

Dans notre cas, le MCP server donne accès à ta **base de connaissances RAG** directement depuis Claude Desktop !

---

## Comment ça fonctionne

### Architecture

```
┌─────────────────────┐         ┌──────────────────┐         ┌─────────────────┐
│  Claude Desktop     │ ◄─────► │   MCP Server     │ ◄─────► │  RAG System     │
│  (Claude Code)      │  stdio  │   (server.py)    │         │  (ChromaDB etc) │
└─────────────────────┘         └──────────────────┘         └─────────────────┘
```

### Cycle de vie

1. **Tu ouvres Claude Desktop** → Le MCP server démarre automatiquement
2. **Claude Desktop est ouvert** → MCP tourne en arrière-plan
3. **Tu fermes Claude Desktop** → MCP s'arrête automatiquement

**Tu n'as rien à gérer manuellement !** 🎉

### Séparation CLI vs MCP

| CLI Interactif (`run_rag.py`) | MCP Server |
|--------------------------------|------------|
| Pour **gérer** tes données | Pour **interroger** tes données |
| Ajouter URLs, process queue | Recherche automatique par Claude |
| Voir stats, recherches manuelles | Communique avec Claude Desktop |
| Tu le lances manuellement | Claude Desktop le lance automatiquement |

**Les deux peuvent tourner en même temps !** Ils accèdent à la même database.

---

## Installation

### Méthode automatique (recommandée)

```bash
# Depuis la racine du projet
./scripts/install_mcp.sh
```

Le script va :
- ✅ Détecter ton OS (Linux/macOS)
- ✅ Trouver le fichier de config Claude Desktop
- ✅ Créer un backup de ta config existante
- ✅ Ajouter la configuration MCP
- ✅ Te donner les prochaines étapes

### Méthode manuelle

#### 1. Localiser le fichier de config

**Linux** :
```bash
~/.config/Claude/claude_desktop_config.json
```

**macOS** :
```bash
~/Library/Application Support/Claude/claude_desktop_config.json
```

**Windows** :
```
%APPDATA%\Claude\claude_desktop_config.json
```

#### 2. Éditer la configuration

Remplace `/chemin/vers/ton/projet` par le chemin absolu de ton projet :

```json
{
  "mcpServers": {
    "rag-knowledge-base": {
      "command": "/chemin/vers/ton/projet/venv/bin/python",
      "args": [
        "/chemin/vers/ton/projet/mcp_server/server.py"
      ],
      "env": {
        "PYTHONPATH": "/chemin/vers/ton/projet"
      }
    }
  }
}
```

**Exemple concret** :
```json
{
  "mcpServers": {
    "rag-knowledge-base": {
      "command": "/home/jokyjokeai/Desktop/RAG/rag-local-system/venv/bin/python",
      "args": [
        "/home/jokyjokeai/Desktop/RAG/rag-local-system/mcp_server/server.py"
      ],
      "env": {
        "PYTHONPATH": "/home/jokyjokeai/Desktop/RAG/rag-local-system"
      }
    }
  }
}
```

#### 3. Redémarrer Claude Desktop

**Important** : Quitter complètement l'application (pas juste fermer la fenêtre).

#### 4. Vérifier la connexion

Dans Claude Desktop, clique sur l'icône 🔌 en bas. Tu devrais voir :
- `rag-knowledge-base` avec un **point vert** ✅

---

## Utilisation avec Claude

### Recherche simple

```
Toi : "Search the knowledge base for Python asyncio tutorials"

Claude : *Utilise automatiquement le MCP server*
         *Retourne 20 chunks pertinents de ta base*
```

### Ajouter des sources

```
Toi : "Add this URL to the knowledge base: https://github.com/python/cpython"

Claude : *Utilise le tool add_source*
         *Ajoute l'URL à la queue*
```

### Voir les stats

```
Toi : "What's the status of my RAG system?"

Claude : *Utilise get_status*
         *Affiche : 240 chunks, 54 URLs, etc.*
```

---

## Outils disponibles

### 🔍 `search_rag`

Recherche dans la base de connaissances.

**Paramètres** :
- `query` (requis) : Question ou recherche
- `n_results` (optionnel, défaut: 20) : Nombre de chunks à retourner
  - Recommandé : 10-20 pour contexte complet, 5 pour réponse rapide
- `source_type` (optionnel) : Filtrer par type
  - `all` (défaut), `documentation`, `youtube`, `github`
- `difficulty` (optionnel) : Filtrer par niveau
  - `all` (défaut), `beginner`, `intermediate`, `advanced`

**Exemple** :
```
Claude utilise : search_rag(
  query="Python async programming best practices",
  n_results=15,
  source_type="documentation"
)
```

### ➕ `add_source`

Ajoute des URLs ou lance une recherche Brave.

**Paramètres** :
- `input` (requis) : URL(s) ou prompt de recherche
- `process_immediately` (optionnel, défaut: false) : Traiter immédiatement

**Exemple URLs** :
```
Claude utilise : add_source(
  input="https://github.com/pallets/flask\nhttps://flask.palletsprojects.com",
  process_immediately=false
)
```

**Exemple recherche** :
```
Claude utilise : add_source(
  input="Python FastAPI tutorials and documentation",
  process_immediately=false
)
```

### 📊 `get_status`

Affiche les statistiques du système RAG.

**Exemple de sortie** :
```
📊 RAG System Status

Database:
- Total URLs: 54
- ✅ Scraped: 3
- ⏳ Pending: 51
- ❌ Failed: 0

Vector Database:
- Total chunks: 240
- Collection: knowledge_base

By Source Type:
- github: 239 chunks
- youtube_video: 1 chunks
```

---

## FAQ

### Q : Le MCP server tourne-t-il tout le temps ?

**R :** Non, seulement quand Claude Desktop est ouvert. Il démarre et s'arrête automatiquement.

### Q : Puis-je utiliser le CLI en même temps que le MCP ?

**R :** Oui ! Ils sont complètement indépendants et accèdent à la même base de données. Tu peux :
- Terminal 1 : `python run_rag.py` (gérer les données)
- Claude Desktop : Interroger via MCP (rechercher)

### Q : Comment savoir si le MCP fonctionne ?

**R :** Clique sur l'icône 🔌 en bas de Claude Desktop. Si tu vois `rag-knowledge-base` avec un point vert, c'est bon !

### Q : Que se passe-t-il si j'ajoute des URLs depuis le CLI ?

**R :** Claude Desktop les verra immédiatement après le processing ! Les deux accèdent à la même database ChromaDB.

### Q : Pourquoi 20 chunks par défaut ?

**R :** C'est le bon équilibre pour donner assez de contexte à Claude sans surcharger. Il peut ajuster selon le besoin.

### Q : Le MCP consomme-t-il des ressources ?

**R :** Très peu. Il reste en attente et ne s'active que quand Claude l'utilise.

### Q : Comment désactiver le MCP ?

**R :** Deux options :
1. Supprimer la config de `claude_desktop_config.json`
2. Ou simplement ne pas l'utiliser (il reste dormant)

### Q : Puis-je avoir plusieurs MCP servers ?

**R :** Oui ! Claude Desktop supporte plusieurs serveurs MCP en même temps. Chacun avec son nom unique.

---

## Troubleshooting

### Le MCP n'apparaît pas dans Claude Desktop

1. Vérifie que le chemin dans `claude_desktop_config.json` est **absolu** (pas relatif)
2. Vérifie que le venv Python existe et contient les dépendances
3. Redémarre Claude Desktop **complètement** (quitter l'app)
4. Vérifie les logs de Claude Desktop (varie selon l'OS)

### Erreur "module not found"

Le `PYTHONPATH` dans la config doit pointer vers la racine du projet :
```json
"env": {
  "PYTHONPATH": "/chemin/absolu/vers/rag-local-system"
}
```

### Le MCP est lent

1. Vérifie que ChromaDB n'est pas trop gros (< 10GB)
2. Réduis `n_results` si nécessaire
3. Vérifie que le CPU n'est pas saturé

---

## 🎉 C'est tout !

Une fois installé, Claude Desktop peut interroger ta base de connaissances automatiquement. Tu n'as plus qu'à utiliser le CLI pour gérer tes données (ajouter URLs, process queue, etc.).

**Profite de ton assistant IA personnel avec ta propre base de connaissances !** 🚀
