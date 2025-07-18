#!/bin/bash
# Smart Documentation Manager - Installation Script
# Скрипт установки умного менеджера документации

set -e  # Остановка при ошибке

echo "🚀 Installing RAG Server + Memory Bank Integration..."
echo ""

# Проверка Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.8+ and try again."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "✅ Python $PYTHON_VERSION found"

# Проверка Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.js not found. Please install Node.js 16+ and try again."
    exit 1
fi

NODE_VERSION=$(node --version)
echo "✅ Node.js $NODE_VERSION found"

# Установка Python зависимостей
echo ""
echo "📦 Installing Python dependencies..."

# Проверяем, есть ли виртуальное окружение
if [ ! -d "venv" ]; then
    echo "🔧 Creating Python virtual environment..."
    python3 -m venv venv
fi

# Активируем виртуальное окружение
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Устанавливаем зависимости
pip install -r requirements.txt

# Установка Node.js зависимостей
echo ""
echo "📦 Installing Node.js dependencies..."
cd mcp-server
npm install
cd ..

# Создание папок если нужно
echo ""
echo "📁 Creating necessary directories..."
mkdir -p chroma_storage
mkdir -p logs

# Создание локальной конфигурации LLM
echo ""
echo "⚙️  Setting up local LLM configuration..."
if [ ! -f config.local.yaml ]; then
    cp config.local.example.yaml config.local.yaml
    echo "✅ Created config.local.yaml from example"
    echo "⚠️  IMPORTANT: Configure config.local.yaml for your LLM model!"
    echo "   Open config.local.yaml and change:"
    echo "   - model_name: to your model name"
    echo "   - api_url: to your LLM server address"
    echo "   - default_model: to your preferred model"
else
    echo "✅ config.local.yaml already exists"
fi

# Проверка существующих папок с документацией
echo ""
echo "🔍 Checking for existing documentation..."
python3 smart_docs_manager.py --preview

echo ""
echo "✅ Installation completed!"
echo ""
echo "🎯 Next steps:"
echo "1. Add documentation folders to project root"
echo "2. Run: python3 smart_docs_manager.py --sync-all"
echo "3. Start RAG server: python3 rag_server.py"
echo "4. Start MCP server: cd mcp-server && npm run start:enhanced"
echo ""
echo "💡 Useful commands:"
echo "   python3 smart_docs_manager.py --preview    # Preview changes"
echo "   python3 smart_docs_manager.py --status     # System status"
echo "   python3 smart_docs_manager.py --sync-all   # Full synchronization"
echo ""
echo "📚 Documentation: README.md"
