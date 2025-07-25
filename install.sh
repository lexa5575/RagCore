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

# Установка Node.js зависимостей и глобальная установка MCP сервера
echo ""
echo "📦 Installing Node.js dependencies..."
cd mcp-server
npm install

echo "🌍 Installing MCP server globally..."
npm link
echo "✅ MCP server is now globally available as 'rag-mcp-server'"
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

echo ""
echo "✅ Installation completed!"
echo ""
echo "🎯 Next steps:"
echo "1. Add documentation folders to documentation/ directory"
echo "   Examples:"
echo "   cp -r /path/to/python_docs documentation/"
echo "   git clone https://github.com/vuejs/docs.git documentation/vue_docs"
echo ""
echo "2. Run automatic documentation sync:"
echo "   python3 update_docs.py"
echo ""
echo "3. Start RAG server:"
echo "   python3 rag_server.py"
echo ""
echo "4. Start MCP server:"
echo "   npm run start:enhanced"
echo ""
echo "🔗 Connect from any project:"
echo "   Create .mcp.json in your project with:"
echo '   {"servers":[{"name":"rag-server","type":"stdio","command":"rag-mcp-server"}]}'
echo ""
echo "💡 Useful commands:"
echo "   python3 update_docs.py --scan    # Preview what will be processed"
echo "   python3 update_docs.py           # Full automatic synchronization"
echo "   python3 rag_server.py            # Start RAG server"
echo "   rag-mcp-server                   # Start MCP server (globally available)"
echo ""
echo "📚 Documentation: README.md"
