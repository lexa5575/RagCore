#!/bin/bash

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🛑 Остановка RAG системы...${NC}"

# Чтение PID из файла
if [ -f /tmp/rag-system-pids.txt ]; then
    PIDS=$(cat /tmp/rag-system-pids.txt)
    echo -e "${YELLOW}📋 Найдены PID: $PIDS${NC}"
    
    for PID in $PIDS; do
        if kill -0 $PID 2>/dev/null; then
            echo -e "${YELLOW}🔪 Остановка процесса $PID...${NC}"
            kill $PID
            sleep 2
            if kill -0 $PID 2>/dev/null; then
                echo -e "${RED}⚠️  Принудительная остановка процесса $PID...${NC}"
                kill -9 $PID
            fi
        else
            echo -e "${GREEN}✅ Процесс $PID уже остановлен${NC}"
        fi
    done
    
    rm -f /tmp/rag-system-pids.txt
else
    echo -e "${YELLOW}📋 Файл PID не найден, останавливаем по портам...${NC}"
    
    # Поиск и остановка процессов по портам
    RAG_PID=$(lsof -t -i:8000 2>/dev/null)
    MCP_PID=$(lsof -t -i:8200 2>/dev/null)
    
    if [ ! -z "$RAG_PID" ]; then
        echo -e "${YELLOW}🔪 Остановка RAG Backend (PID: $RAG_PID)...${NC}"
        kill $RAG_PID
    fi
    
    if [ ! -z "$MCP_PID" ]; then
        echo -e "${YELLOW}🔪 Остановка MCP Server (PID: $MCP_PID)...${NC}"
        kill $MCP_PID
    fi
fi

echo -e "${GREEN}✅ RAG система остановлена!${NC}"