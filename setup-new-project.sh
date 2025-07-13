#!/bin/bash

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функция для вывода заголовка
print_header() {
    echo ""
    echo -e "${BLUE}================================================${NC}"
    echo -e "${BLUE}🚀 Настройка RAG для нового проекта${NC}"
    echo -e "${BLUE}================================================${NC}"
    echo ""
}

# Функция для проверки аргументов
check_arguments() {
    if [ $# -eq 0 ]; then
        echo -e "${RED}❌ Ошибка: Укажите путь к новому проекту${NC}"
        echo -e "${YELLOW}Использование: $0 /path/to/new/project${NC}"
        echo ""
        echo -e "${YELLOW}Примеры:${NC}"
        echo -e "  $0 /Users/aleksejcuprynin/PhpstormProjects/NewProject"
        echo -e "  $0 ~/Projects/MyApp"
        echo ""
        exit 1
    fi
}

# Функция для проверки существования папки
check_project_directory() {
    local project_path="$1"
    
    if [ ! -d "$project_path" ]; then
        echo -e "${RED}❌ Ошибка: Папка не существует: $project_path${NC}"
        echo -e "${YELLOW}💡 Создать папку? (y/n)${NC}"
        read -n 1 -s create_dir
        echo ""
        
        if [[ $create_dir == "y" || $create_dir == "Y" ]]; then
            mkdir -p "$project_path"
            echo -e "${GREEN}✅ Папка создана: $project_path${NC}"
        else
            echo -e "${RED}❌ Операция отменена${NC}"
            exit 1
        fi
    fi
}

# Функция для проверки статуса RAG системы
check_rag_system() {
    echo -e "${YELLOW}🔍 Проверка RAG системы...${NC}"
    
    if curl -s http://localhost:8000/health > /dev/null; then
        echo -e "${GREEN}✅ RAG Backend работает${NC}"
    else
        echo -e "${RED}❌ RAG Backend не работает${NC}"
        echo -e "${YELLOW}💡 Запустите RAG систему:${NC}"
        echo -e "   cd /Users/aleksejcuprynin/PycharmProjects/chanki && ./start-rag-system.sh"
        echo ""
        echo -e "${YELLOW}❓ Продолжить без запуска RAG? (y/n)${NC}"
        read -n 1 -s continue_anyway
        echo ""
        
        if [[ $continue_anyway != "y" && $continue_anyway != "Y" ]]; then
            echo -e "${RED}❌ Операция отменена${NC}"
            exit 1
        fi
    fi
}

# Функция для копирования CLAUDE.md
copy_claude_md() {
    local project_path="$1"
    local claude_md_path="$project_path/CLAUDE.md"
    
    echo -e "${YELLOW}📄 Создание CLAUDE.md...${NC}"
    
    if [ -f "$claude_md_path" ]; then
        echo -e "${YELLOW}⚠️  CLAUDE.md уже существует${NC}"
        echo -e "${YELLOW}❓ Заменить файл? (y/n)${NC}"
        read -n 1 -s replace_file
        echo ""
        
        if [[ $replace_file != "y" && $replace_file != "Y" ]]; then
            echo -e "${YELLOW}⏭️  Пропуск создания CLAUDE.md${NC}"
            return 0
        fi
    fi
    
    # Копируем шаблон
    cp "/Users/aleksejcuprynin/PycharmProjects/chanki/CLAUDE_MD_TEMPLATE.md" "$claude_md_path"
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ CLAUDE.md создан в проекте${NC}"
    else
        echo -e "${RED}❌ Ошибка создания CLAUDE.md${NC}"
        return 1
    fi
}

# Функция для создания quick-start команд
create_quick_commands() {
    local project_path="$1"
    
    echo -e "${YELLOW}⚡ Создание быстрых команд...${NC}"
    
    # Создаем скрипт для быстрого запуска RAG
    cat > "$project_path/start-rag.sh" << 'EOF'
#!/bin/bash
echo "🚀 Запуск RAG системы..."
cd /Users/aleksejcuprynin/PycharmProjects/chanki && ./start-rag-system.sh
EOF
    
    # Создаем скрипт для проверки статуса
    cat > "$project_path/check-rag.sh" << 'EOF'
#!/bin/bash
echo "🔍 Проверка RAG системы..."
/Users/aleksejcuprynin/PycharmProjects/chanki/check-rag-system.sh
EOF
    
    # Делаем скрипты исполняемыми
    chmod +x "$project_path/start-rag.sh"
    chmod +x "$project_path/check-rag.sh"
    
    echo -e "${GREEN}✅ Быстрые команды созданы${NC}"
}

# Функция для финальной информации
print_final_info() {
    local project_path="$1"
    
    echo ""
    echo -e "${GREEN}🎉 Настройка завершена!${NC}"
    echo -e "${BLUE}================================================${NC}"
    echo -e "${YELLOW}📋 Что было создано:${NC}"
    echo -e "  • CLAUDE.md - инструкции для Claude"
    echo -e "  • start-rag.sh - быстрый запуск RAG системы"
    echo -e "  • check-rag.sh - проверка статуса RAG"
    echo ""
    echo -e "${YELLOW}🚀 Как использовать:${NC}"
    echo -e "  1. Перейдите в проект: ${BLUE}cd $project_path${NC}"
    echo -e "  2. Запустите RAG: ${BLUE}./start-rag.sh${NC}"
    echo -e "  3. Откройте Claude Code в этой папке"
    echo -e "  4. Задавайте вопросы - Claude автоматически получит информацию из RAG!"
    echo ""
    echo -e "${GREEN}✨ RAG система готова к использованию!${NC}"
}

# Основная функция
main() {
    print_header
    check_arguments "$@"
    
    local project_path="$1"
    project_path=$(realpath "$project_path")
    
    echo -e "${YELLOW}🎯 Настройка проекта: ${BLUE}$project_path${NC}"
    
    check_project_directory "$project_path"
    check_rag_system
    copy_claude_md "$project_path"
    create_quick_commands "$project_path"
    print_final_info "$project_path"
}

# Запуск основной функции
main "$@"