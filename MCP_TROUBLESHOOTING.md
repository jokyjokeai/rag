# 🔧 MCP Server Troubleshooting Guide

## ❓ Problème: `/mcp` ne trouve pas le serveur

### 🎯 **Solution Appliquée** ✅

Un lien symbolique a été créé pour rendre le serveur MCP accessible **globalement**:

```bash
~/.mcp.json → /home/jokyjokeai/Desktop/RAG/rag-local-system/.mcp.json
```

**Maintenant tu peux lancer Claude Code depuis N'IMPORTE QUEL répertoire!**

---

## 🧪 **Test de Vérification**

### 1. Vérifier le lien symbolique

```bash
ls -la ~/.mcp.json
```

**Résultat attendu:**
```
lrwxrwxrwx ... /home/jokyjokeai/.mcp.json -> .../rag-local-system/.mcp.json
```

✅ Si tu vois la flèche `→`, c'est bon!

---

### 2. Tester Claude Code depuis n'importe où

**Depuis ton répertoire home:**
```bash
cd ~
claude
```

**Dans Claude Code, taper:**
```
/mcp list
```

**Résultat attendu:**
```
Available MCP servers:
  • rag-knowledge-base - RAG Knowledge Base
```

✅ Le serveur devrait apparaître!

---

### 3. Tester la connexion au serveur

```
/mcp use rag-knowledge-base
```

**Résultat attendu:**
```
Connected to MCP server: rag-knowledge-base
Tools available:
  • search_rag
  • add_source
  • get_status
```

✅ Tu devrais voir les 3 outils disponibles!

---

## 🐛 **Si ça ne marche toujours pas**

### Problème 1: "Server not found"

**Vérifications:**

1. **Le lien symbolique existe?**
```bash
ls -la ~/.mcp.json
```

2. **Le fichier cible existe?**
```bash
cat ~/.mcp.json
```

Tu devrais voir:
```json
{
  "mcpServers": {
    "rag-knowledge-base": {
      ...
    }
  }
}
```

3. **Le serveur Python fonctionne?**
```bash
cd /home/jokyjokeai/Desktop/RAG/rag-local-system
source venv/bin/activate
python mcp_server/server.py
```

Tu devrais voir: "Starting MCP server..."

**Appuie sur Ctrl+C pour arrêter**

---

### Problème 2: "Connection failed"

**Causes possibles:**

1. **L'environnement virtuel n'est pas activé**
   - Vérifier: `which python` dans le venv
   - Le chemin dans `.mcp.json` pointe vers `venv/bin/python`

2. **Dépendances manquantes**
```bash
cd /home/jokyjokeai/Desktop/RAG/rag-local-system
source venv/bin/activate
pip install mcp rank-bm25 sentence-transformers
```

3. **Base de données ChromaDB corrompue**
```bash
# Recréer la collection (depuis le venv)
python rebuild_vector_db.py
```

---

### Problème 3: "Python path not found"

**Vérifier le chemin dans `.mcp.json`:**

```bash
cat ~/.mcp.json | grep command
```

Tu devrais voir:
```
"command": "/home/jokyjokeai/Desktop/RAG/rag-local-system/venv/bin/python",
```

**Si le chemin est différent, le corriger:**
```bash
# Trouver le bon chemin
cd /home/jokyjokeai/Desktop/RAG/rag-local-system
source venv/bin/activate
which python
```

Puis éditer `~/.mcp.json` avec le bon chemin.

---

## 📍 **Emplacements des Fichiers de Config**

| Fichier | Emplacement | Usage |
|---------|-------------|-------|
| `.mcp.json` (lien) | `~/.mcp.json` | **Config globale Claude Code** ⭐ |
| `.mcp.json` (source) | `~/Desktop/RAG/rag-local-system/.mcp.json` | Config locale |
| `claude_desktop_config.json` | `~/.config/Claude/claude_desktop_config.json` | Config Claude Desktop |

---

## 🎨 **Différences Claude Desktop vs Claude Code**

### Claude Desktop (app graphique)
- **Config:** `~/.config/Claude/claude_desktop_config.json`
- **Format:** Pas de champ `"type": "stdio"`
- **Test:** Ouvrir Claude Desktop, vérifier les serveurs MCP

### Claude Code (CLI)
- **Config:** `.mcp.json` (répertoire courant ou home)
- **Format:** Avec `"type": "stdio"`
- **Test:** Commande `/mcp list`

**Les deux peuvent coexister!** ✅

---

## ✅ **Checklist Complète**

Avant d'ouvrir Claude Code:

- [ ] Lien symbolique créé: `~/.mcp.json`
- [ ] Environnement virtuel activé une fois: `source venv/bin/activate`
- [ ] Dépendances installées: `pip install -r requirements.txt`
- [ ] Serveur testé manuellement: `python mcp_server/server.py`
- [ ] Base de données prête: `python run_rag.py` (Option 5)

Test final:
- [ ] `cd ~` (partir du home)
- [ ] `claude`
- [ ] `/mcp list` → voit "rag-knowledge-base"
- [ ] `/mcp use rag-knowledge-base` → connecté
- [ ] Utiliser `search_rag` avec une requête

---

## 🚀 **Utilisation Rapide**

### Workflow recommandé:

```bash
# 1. Ouvrir Claude Code (n'importe où)
claude

# 2. Lister les serveurs MCP
/mcp list

# 3. Se connecter
/mcp use rag-knowledge-base

# 4. Chercher dans la base
search the RAG knowledge base for "FastAPI tutorials"

# 5. Voir les stats
get RAG system status
```

---

## 🔄 **Mise à Jour du Serveur**

Si tu modifies le code du serveur MCP:

```bash
cd /home/jokyjokeai/Desktop/RAG/rag-local-system

# 1. Arrêter Claude Code (Ctrl+D)
# 2. Modifier le code
# 3. Relancer Claude Code
claude

# Le serveur sera rechargé automatiquement
```

**Pas besoin de recréer le lien symbolique!**

---

## 📞 **Support**

Si problème persistant:

1. **Vérifier les logs:**
```bash
# Lancer le serveur en mode debug
cd /home/jokyjokeai/Desktop/RAG/rag-local-system
source venv/bin/activate
python mcp_server/server.py 2>&1 | tee mcp_debug.log
```

2. **Consulter la documentation:**
- Claude Code MCP: https://docs.claude.com/mcp
- Projet RAG: `README.md`

3. **Tester avec un serveur MCP simple:**
```json
{
  "mcpServers": {
    "test": {
      "type": "stdio",
      "command": "python",
      "args": ["-c", "print('Hello MCP')"]
    }
  }
}
```

---

**Dernière mise à jour:** 2025-11-16
**Version:** 2.0
