#!/bin/bash

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🔍 Проверка статуса RAG системы${NC}"
echo "=================================================="

# Проверка RAG Backend
echo -e "${YELLOW}📊 Проверка RAG Backend (порт 8000)...${NC}"
if curl -s http://localhost:8000/health > /dev/null; then
    echo -e "${GREEN}✅ RAG Backend работает${NC}"
    RAG_STATUS="OK"
else
    echo -e "${RED}❌ RAG Backend не отвечает${NC}"
    RAG_STATUS="ERROR"
fi

# Проверка MCP Server
echo -e "${YELLOW}🔗 Проверка MCP Server (порт 8200)...${NC}"
if curl -s http://localhost:8200/health > /dev/null; then
    echo -e "${GREEN}✅ MCP Server работает${NC}"
    MCP_STATUS="OK"
else
    echo -e "${RED}❌ MCP Server не отвечает${NC}"
    MCP_STATUS="ERROR"
fi

# Проверка MCP Tools
echo -e "${YELLOW}🛠️  Проверка MCP Tools...${NC}"
if curl -s http://localhost:8200/mcp > /dev/null; then
    echo -e "${GREEN}✅ MCP Tools доступны${NC}"
    TOOLS_STATUS="OK"
else
    echo -e "${RED}❌ MCP Tools недоступны${NC}"
    TOOLS_STATUS="ERROR"
fi

# Проверка конфигурации Claude Desktop
echo -e "${YELLOW}⚙️  Проверка конфигурации Claude Desktop...${NC}"
if [ -f ~/.config/claude-desktop/claude_desktop_config.json ]; then
    echo -e "${GREEN}✅ Конфигурация Claude Desktop найдена${NC}"
    CONFIG_STATUS="OK"
else
    echo -e "${RED}❌ Конфигурация Claude Desktop не найдена${NC}"
    CONFIG_STATUS="ERROR"
fi

# Итоговый статус
echo ""
echo "=================================================="
echo -e "${YELLOW}📋 Итоговый статус:${NC}"

if [ "$RAG_STATUS" = "OK" ] && [ "$MCP_STATUS" = "OK" ] && [ "$TOOLS_STATUS" = "OK" ] && [ "$CONFIG_STATUS" = "OK" ]; then
    echo -e "${GREEN}🎉 Все компоненты работают корректно!${NC}"
    echo -e "${GREEN}✨ RAG система готова к использованию с Claude Desktop${NC}"
    exit 0
else
    echo -e "${RED}⚠️  Некоторые компоненты не работают${NC}"
    echo -e "${YELLOW}💡 Попробуйте перезапустить систему: ./start-rag-system.sh${NC}"
    exit 1
fi