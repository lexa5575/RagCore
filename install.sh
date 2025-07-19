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
pip3 install -r requirements.txt

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

# Создание конфигурации LLM
echo ""
echo "⚙️  Setting up LLM configuration..."
if [ ! -f config.yaml ]; then
    if [ -f config.example.yaml ]; then
        cp config.example.yaml config.yaml
        echo "✅ Created config.yaml from example"
    else
        echo "✅ config.yaml will be created by update_docs.py"
    fi
    echo "⚠️  IMPORTANT: Configure config.yaml for your LLM model!"
    echo "   Open config.yaml and change:"
    echo "   - model_name: to your model name"
    echo "   - api_url: to your LLM server address"
    echo "   - default_model: to your preferred model"
else
    echo "✅ config.yaml already exists"
fi

# Проверка существующих папок с документацией
echo ""
echo "🔍 Checking for existing documentation..."
python3 update_docs.py --scan

echo ""
echo "✅ Installation completed!"
echo ""
echo "🎯 Next steps:"
echo "1. Add documentation folders to documentation/ directory"
echo "2. Run: python3 update_docs.py"
echo "3. Start RAG server: python3 rag_server.py"
echo "4. Start MCP server: cd mcp-server && npm run start:enhanced"
echo ""
echo "💡 Useful commands:"
echo "   python3 update_docs.py --scan    # Preview changes"
echo "   python3 update_docs.py           # Full synchronization"
echo "   python3 rag_server.py            # Start RAG server"
echo ""
echo "📚 Documentation: README.md"
