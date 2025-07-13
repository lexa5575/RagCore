#!/bin/bash

# Тест для проверки доступности MCP tools без перезагрузки
echo "🔍 Тест доступности MCP tools"
echo "==============================="

# Проверка статуса MCP сервера
echo "1. Проверка MCP сервера..."
if curl -s http://localhost:8200/health > /dev/null; then
    echo "✅ MCP Server доступен"
else
    echo "❌ MCP Server недоступен"
    exit 1
fi

# Проверка доступных tools
echo "2. Проверка доступных MCP tools..."
TOOLS=$(curl -s http://localhost:8200/mcp | jq -r '.tools[].name' 2>/dev/null)

if [ -n "$TOOLS" ]; then
    echo "✅ Доступные MCP tools:"
    echo "$TOOLS" | while read tool; do
        echo "   - $tool"
    done
else
    echo "❌ MCP tools недоступны"
    exit 1
fi

# Тест ask_rag
echo "3. Тест ask_rag функции..."
RESPONSE=$(curl -s -X POST http://localhost:8200/tool/ask_rag \
    -H "Content-Type: application/json" \
    -d '{"question": "Что такое Laravel?", "framework": "laravel"}')

if echo "$RESPONSE" | grep -q "Laravel"; then
    echo "✅ ask_rag работает корректно"
else
    echo "❌ ask_rag не работает"
    exit 1
fi

echo ""
echo "🎉 Все MCP tools готовы к использованию!"
echo "💡 Для нового проекта достаточно создать CLAUDE.md"
echo "💡 Перезагрузка Claude НЕ требуется"