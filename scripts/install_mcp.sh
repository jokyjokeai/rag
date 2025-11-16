#!/bin/bash
# Script d'installation du MCP server pour Claude Desktop

set -e

echo "🔧 Installation du MCP Server pour Claude Desktop"
echo "=================================================="
echo ""

# Detect OS
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    CONFIG_DIR="$HOME/.config/Claude"
    CONFIG_FILE="$CONFIG_DIR/claude_desktop_config.json"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    CONFIG_DIR="$HOME/Library/Application Support/Claude"
    CONFIG_FILE="$CONFIG_DIR/claude_desktop_config.json"
else
    echo "❌ OS non supporté : $OSTYPE"
    exit 1
fi

echo "📁 Chemin de configuration détecté : $CONFIG_FILE"
echo ""

# Get absolute path to project
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MCP_SERVER_PATH="$PROJECT_DIR/mcp_server/server.py"
VENV_PYTHON="$PROJECT_DIR/venv/bin/python"

echo "📂 Projet RAG : $PROJECT_DIR"
echo "🐍 Python venv : $VENV_PYTHON"
echo "📡 MCP Server  : $MCP_SERVER_PATH"
echo ""

# Check if server exists
if [ ! -f "$MCP_SERVER_PATH" ]; then
    echo "❌ Erreur : MCP server non trouvé à $MCP_SERVER_PATH"
    exit 1
fi

# Check if venv python exists
if [ ! -f "$VENV_PYTHON" ]; then
    echo "❌ Erreur : Python venv non trouvé à $VENV_PYTHON"
    echo "💡 Lancez d'abord : python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Create config directory if needed
mkdir -p "$CONFIG_DIR"

# Create or update config
if [ -f "$CONFIG_FILE" ]; then
    echo "📝 Fichier de config existant détecté"
    echo "💾 Backup créé : ${CONFIG_FILE}.backup"
    cp "$CONFIG_FILE" "${CONFIG_FILE}.backup"

    # Check if rag-knowledge-base already exists
    if grep -q '"rag-knowledge-base"' "$CONFIG_FILE"; then
        echo "⚠️  Configuration 'rag-knowledge-base' existe déjà"
        echo "❓ Voulez-vous la remplacer ? (y/N)"
        read -r response
        if [[ ! "$response" =~ ^[Yy]$ ]]; then
            echo "❌ Installation annulée"
            exit 0
        fi
    fi
fi

# Generate config
cat > "$CONFIG_FILE" << EOF
{
  "mcpServers": {
    "rag-knowledge-base": {
      "command": "$VENV_PYTHON",
      "args": [
        "$MCP_SERVER_PATH"
      ],
      "env": {
        "PYTHONPATH": "$PROJECT_DIR"
      }
    }
  }
}
EOF

echo ""
echo "✅ Configuration MCP installée avec succès !"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 PROCHAINES ÉTAPES"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "1. Redémarrez Claude Desktop complètement"
echo "   (Quitter l'application, pas juste fermer la fenêtre)"
echo ""
echo "2. Rouvrez Claude Desktop"
echo ""
echo "3. Vérifiez que le MCP est connecté :"
echo "   - Cliquez sur l'icône 🔌 en bas de Claude Desktop"
echo "   - Vous devriez voir 'rag-knowledge-base' avec un point vert"
echo ""
echo "4. Testez avec Claude :"
echo "   Demandez : 'Search the knowledge base for Python requests'"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📖 OUTILS DISPONIBLES DANS CLAUDE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🔍 search_rag          - Rechercher dans la base de connaissances"
echo "➕ add_source          - Ajouter des URLs ou faire une recherche"
echo "📊 get_status          - Voir les stats du système RAG"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🎉 Installation terminée !"
