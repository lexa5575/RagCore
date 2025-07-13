#!/bin/bash

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Запуск RAG системы для HeaterTeam${NC}"
echo "=================================================="

# Переход в рабочую директорию
cd /Users/aleksejcuprynin/PycharmProjects/chanki

# Проверка наличия Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python3 не найден!${NC}"
    exit 1
fi

# Проверка наличия Node.js
if ! command -v node &> /dev/null; then
    echo -e "${RED}❌ Node.js не найден!${NC}"
    exit 1
fi

echo -e "${YELLOW}📊 Запуск RAG Backend (FastAPI)...${NC}"
python3 rag_server.py &
RAG_PID=$!

# Ожидание запуска RAG backend
echo -e "${YELLOW}⏳ Ожидание запуска RAG backend...${NC}"
sleep 8

# Проверка работы RAG backend
if curl -s http://localhost:8000/health > /dev/null; then
    echo -e "${GREEN}✅ RAG Backend запущен успешно!${NC}"
else
    echo -e "${RED}❌ RAG Backend не отвечает!${NC}"
    kill $RAG_PID 2>/dev/null
    exit 1
fi

echo -e "${YELLOW}🔗 Запуск MCP Server...${NC}"
cd mcp-server
node http-mcp-server.js &
MCP_PID=$!

# Ожидание запуска MCP server
echo -e "${YELLOW}⏳ Ожидание запуска MCP server...${NC}"
sleep 5

# Проверка работы MCP server
if curl -s http://localhost:8200/health > /dev/null; then
    echo -e "${GREEN}✅ MCP Server запущен успешно!${NC}"
else
    echo -e "${RED}❌ MCP Server не отвечает!${NC}"
    kill $RAG_PID $MCP_PID 2>/dev/null
    exit 1
fi

echo ""
echo -e "${GREEN}🎉 Система запущена успешно!${NC}"
echo "=================================================="
echo -e "RAG Backend PID: ${GREEN}$RAG_PID${NC}"
echo -e "MCP Server PID: ${GREEN}$MCP_PID${NC}"
echo ""
echo -e "${YELLOW}📋 Доступные сервисы:${NC}"
echo "• RAG Backend: http://localhost:8000"
echo "• MCP Server: http://localhost:8200"
echo "• MCP Tools: http://localhost:8200/mcp"
echo ""
echo -e "${YELLOW}🛑 Для остановки используйте:${NC}"
echo "kill $RAG_PID $MCP_PID"
echo ""
echo -e "${GREEN}✨ Теперь Claude Desktop автоматически подключится к RAG!${NC}"

# Сохранение PID для скрипта остановки
echo "$RAG_PID $MCP_PID" > /tmp/rag-system-pids.txt

# Ожидание завершения процессов
wait