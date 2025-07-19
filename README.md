🚀 RAG Server + Memory Bank Integration
Intelligent Documentation Assistant with Project Memory


A comprehensive RAG (Retrieval-Augmented Generation) system with intelligent project memory management for AI assistants like Claude and Cline.

🌍 Languages / Языки

🇺🇸 English Documentation
🇷🇺 Русская документация


ENGLISH DOCUMENTATION
🎯 What is this?
This project combines a powerful RAG (Retrieval-Augmented Generation) server with an intelligent Memory Bank system to create a versatile development assistant. It provides:

📚 Smart Documentation Search - Query documentation for any technology or framework you are working with
🧠 Project Memory - Automatically tracks project context, tasks, and development history
👁️ File Monitoring - Real-time tracking of code changes and key development moments
🔗 Unified Interface - Single MCP server integrating all components
🤖 Local LLM Support - Uses meta-llama-3.1-8b-instruct for intelligent responses

🏗️ System Architecture
┌─────────────────────────────────────────────────────────────┐
│                    Claude / Cline                          │
│                 (AI Assistant)                             │
└─────────────────────┬───────────────────────────────────────┘
                      │ MCP Protocol
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              Enhanced MCP Server                            │
│           (Unified Interface)                               │
└─────────┬─────────────────┬─────────────────┬───────────────┘
          │                 │                 │
          ▼                 ▼                 ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│   RAG Server    │ │  Memory Bank    │ │  File Watcher   │
│ (Documentation) │ │ (Project State) │ │ (Change Track)  │
└─────────┬───────┘ └─────────┬───────┘ └─────────┬───────┘
          │                   │                   │
          ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│    ChromaDB     │ │    MD Files     │ │     Events      │
│  (Vector Store) │ │ (Project Docs)  │ │  (File Changes) │
└─────────────────┘ └─────────────────┘ └─────────────────┘

📦 Installation
Prerequisites

Python 3.8+ with pip
Node.js 16+ with npm
Local LLM Server (LM Studio, Ollama, or similar)
Claude Desktop or VS Code with Cline extension

Step 1: Clone and Setup Python Environment
git clone https://github.com/lexa5575/rag_server.git
cd rag_server

# Create virtual environment (REQUIRED!)
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # macOS/Linux
# OR for Windows:
# venv\Scripts\activate

# Install Python dependencies
pip3 install -r requirements.txt

Step 2: Setup Node.js Dependencies
cd mcp-server
npm install
cd ..

Step 3: Configure Local LLM

Install LM Studio or Ollama
Download meta-llama-3.1-8b-instruct model
Start local server on http://127.0.0.1:1234 (LM Studio) or http://localhost:11434 (Ollama)

Step 4: Add Documentation to documentation/ Folder
Add any documentation you want to search through to the documentation/ folder. The system will automatically detect the technology based on the folder name you choose. For example:

documentation/python_docs/ for Python documentation
documentation/java_docs/ for Java documentation
documentation/custom_project_docs/ for your own project's documentation

You can clone repositories or copy local files into this folder.
🚀 Quick Start
1. Create Virtual Environment (REQUIRED!)
```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate  # macOS/Linux
# OR for Windows:
# venv\Scripts\activate
```

2. Run Installation Script
```bash
./install.sh
```
*This will install all dependencies and check your system*

3. Configure Your Local LLM (One-time setup)
Edit config.yaml to set up your local LLM.
3. Add Documentation to documentation/ Folder
Follow the instructions in Step 4 above.
4. Run Automatic Documentation Sync
python3 update_docs.py

5. Start the RAG Server
python3 rag_server.py

6. Start the Enhanced MCP Server
cd mcp-server
npm run start:enhanced

7. Configure MCP in Your AI Assistant
Follow the instructions for Claude Desktop or VS Code Cline.
8. Test the System
In Claude or Cline, try these commands:
get_rag_stats
ask_rag "How to create a class in Python?" "python"
memory_bank_status
file_watcher_start

🎯 Simple Documentation Manager
The project includes a Simple Documentation Manager (update_docs.py) that automates the documentation workflow with one command.
🚀 Key Features:

📁 Folder-Based Discovery: Automatically scans documentation/ folder for technology documentation
🏷️ Smart Naming: Determines technology types by folder names (e.g., python_docs → Python)
🔄 HTML Conversion: Converts HTML documentation to Markdown if needed
📝 Config Updates: Automatically updates config.yaml with new technologies
📚 Full Indexing: Indexes everything into the RAG database
⚡ One-Command Setup: Single command handles everything automatically

📋 Simple Command Reference:
python3 update_docs.py  # Full automatic synchronization
python3 update_docs.py --scan  # Preview what will be processed
python3 update_docs.py --verbose  # Verbose output for debugging

🎯 Perfect Workflow for New Technologies:

📁 Add documentation to documentation/ folder:# Examples:
git clone https://github.com/python/cpython.git documentation/python_docs
cp -r /path/to/java_docs documentation/java_docs


🔄 Run automatic sync: python3 update_docs.py
✅ Done! Technology is automatically detected, converted, and indexed

🏷️ Technology Detection by Folder Names:
The system automatically recognizes technologies by folder names:

python_docs → Python
java_docs → Java
custom_project_docs → Custom Project
And any other → Uses folder name as technology name

🛠️ Available MCP Tools
RAG Tools

ask_rag - Query documentation for any technology

question: Your question (string)
framework: Target technology (e.g., "python", "java", "my_project")
model: LLM model (qwen, deepseek) - optional
max_results: Number of results (1-20) - optional


list_frameworks - Get available technologies

get_rag_stats - Database statistics

list_models - Available LLM models


Memory Bank Tools

memory_bank_init - Initialize project memory
memory_bank_status - Check memory bank status
memory_bank_read - Read memory bank file
filename: File to read (tasks.md, progress.md, etc.)


memory_bank_write - Write to memory bank
filename: Target file
content: File content


memory_bank_search - Search project history
query: Search terms


memory_bank_archive - Archive completed task
taskId: Task identifier
summary: Task summary
completedWork: Work description
keyDecisions: Important decisions
lessonsLearned: Lessons learned



File Watcher Tools

file_watcher_start - Start monitoring files
file_watcher_stop - Stop monitoring
file_watcher_stats - Get monitoring statistics

💡 Usage Examples
Below are some examples of how to use the system with different technologies. Note that the system is not limited to these technologies; you can use it with any documentation you add to the documentation/ folder.
Python Development
# Get Python-specific help
ask_rag("How to create a class in Python?", "python")

# Track your work
memory_bank_write("activeContext.md", "Building Python scripts with OOP")

# Start monitoring changes
file_watcher_start()

# Search project history
memory_bank_search("classes")

Java API Development
# Learn about Java API
ask_rag("How to use Java streams?", "java")

# Update project progress
memory_bank_write("progress.md", "## Current Task\nImplementing Java streams for data processing")

# Archive completed feature
memory_bank_archive("java-streams", {
  "summary": "Implemented stream processing",
  "completedWork": "Created stream operations for data filtering",
  "keyDecisions": "Used Java 8 streams for better performance"
})

Custom Project Development
# Get help for your custom project
ask_rag("How to implement feature X in my project?", "my_project")

# Track project development
memory_bank_write("techContext.md", "Building custom feature with specific requirements")

🔧 Configuration
config.yaml Structure
frameworks:
  # Add your technologies here
  python:
    enabled: true
    path: /path/to/python_docs
    description: Python Programming Language
  java:
    enabled: true
    path: /path/to/java_docs
    description: Java Programming Language
  # Example for a custom project
  my_project:
    enabled: true
    path: /path/to/my_project_docs
    description: My Custom Project Documentation

Memory Bank File Structure
memory-bank/
├── tasks.md              # Current tasks
├── activeContext.md      # Current context
├── progress.md           # Development progress
├── projectbrief.md       # Project foundation
├── productContext.md     # Product context
├── systemPatterns.md     # System patterns
├── techContext.md        # Technical context
├── style-guide.md        # Style guidelines
├── creative/             # Design decisions
├── reflection/           # Task reflections
└── archive/              # Completed tasks

🚨 Troubleshooting
RAG Server Issues
# Check if server is running
curl http://localhost:8000/stats

# Restart server
python3 rag_server.py

# Check logs
tail -f logs/rag_system.log

MCP Server Issues
# Test MCP server
cd mcp-server
npm run test:memory-bank

# Restart enhanced server
npm run start:enhanced

# Check Node.js version
node --version  # Should be 16+

Memory Bank Issues
# Check memory bank status in Claude/Cline
memory_bank_status()

# Reinitialize if needed
memory_bank_init()

# Check file permissions
ls -la memory-bank/

Local LLM Issues

LM Studio: Ensure server is running on port 1234
Ollama: Check ollama serve is active
Model: Verify meta-llama-3.1-8b-instruct is loaded
API: Test with curl http://127.0.0.1:1234/v1/models

📊 System Monitoring
Check System Health
# In Claude/Cline
get_rag_stats()           # RAG database status
memory_bank_status()      # Memory bank status  
file_watcher_stats()      # File monitoring status
list_frameworks()         # Available technologies

Performance Metrics

RAG Database: ~10,000+ indexed documents
Response Time: <2 seconds for most queries
Memory Usage: ~500MB for full system
File Monitoring: Real-time change detection


РУССКАЯ ДОКУМЕНТАЦИЯ
🎯 Что это такое?
Этот проект объединяет мощный RAG (Retrieval-Augmented Generation) сервер с интеллектуальной системой Memory Bank для создания универсального помощника разработчика. Система предоставляет:

📚 Умный поиск по документации - Запросы к документации любых технологий и фреймворков, с которыми вы работаете
🧠 Память проекта - Автоматическое отслеживание контекста проекта, задач и истории разработки
assoc 👁️ Мониторинг файлов - Отслеживание изменений кода и ключевых моментов разработки в реальном времени
🔗 Единый интерфейс - Один MCP сервер, объединяющий все компоненты
🤖 Поддержка локальной LLM - Использует meta-llama-3.1-8b-instruct для интеллектуальных ответов

🏗️ Архитектура системы
┌─────────────────────────────────────────────────────────────┐
│                    Claude / Cline                          │
│                 (ИИ Ассистент)                             │
└─────────────────────┬───────────────────────────────────────┘
                      │ MCP Протокол
                      ▼
┌─────────────────────────────────────────────────────────────┐
│           Расширенный MCP Сервер                           │
│           (Единый интерфейс)                               │
└─────────┬─────────────────┬─────────────────┬───────────────┘
          │                 │                 │
          ▼                 ▼                 ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│   RAG Сервер    │ │  Memory Bank    │ │ File Watcher    │
│ (Документация)  │ │(Состояние проекта)│ │(Отслеживание)   │
└─────────┬───────┘ └─────────┬───────┘ └─────────┬───────┘
          │                   │                   │
          ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│    ChromaDB     │ │   MD Файлы      │ │    События      │
│(Векторное хран.)│ │ (Документы проекта)│ │(Изменения файлов)│
└─────────────────┘ └─────────────────┘ └─────────────────┘

📦 Установка
Требования

Python 3.8+ с pip
Node.js 16+ с npm
Локальный LLM сервер (LM Studio, Ollama или аналогичный)
Claude Desktop или VS Code с расширением Cline

Шаг 1: Клонирование и настройка Python окружения
git clone https://github.com/lexa5575/rag_server.git
cd rag_server

# Создание виртуального окружения (ОБЯЗАТЕЛЬНО!)
python3 -m venv venv

# Активация виртуального окружения
source venv/bin/activate  # macOS/Linux
# ИЛИ для Windows:
# venv\Scripts\activate

# Установка Python зависимостей
pip3 install -r requirements.txt

Шаг 2: Настройка Node.js зависимостей
cd mcp-server
npm install
cd ..

Шаг 3: Настройка локальной LLM

Установите LM Studio или Ollama
Скачайте модель meta-llama-3.1-8b-instruct
Запустите локальный сервер на http://127.0.0.1:1234 (LM Studio) или http://localhost:11434 (Ollama)

Шаг 4: Добавление документации в папку documentation/
Добавьте любую документацию, которую вы хотите использовать, в папку documentation/. Система автоматически определит технологию по имени папки. Например:

documentation/python_docs/ для документации Python
documentation/java_docs/ для документации Java
documentation/custom_project_docs/ для документации вашего собственного проекта

Вы можете клонировать репозитории или скопировать локальные файлы в эту папку.
🚀 Быстрый старт
1. Создание виртуального окружения (ОБЯЗАТЕЛЬНО!)
```bash
# Создаем виртуальное окружение
python3 -m venv venv

# Активируем его
source venv/bin/activate  # macOS/Linux
# или для Windows:
# venv\Scripts\activate
```

2. Запуск скрипта установки
```bash
./install.sh
```
*Это установит все зависимости и проверит вашу систему*

3. Настройка локальной LLM (одноразовая настройка)
Отредактируйте config.yaml, чтобы настроить вашу локальную LLM.
3. Добавьте документацию в папку documentation/
Следуйте инструкциям в Шаге 4 выше.
4. Запустите автоматическую синхронизацию документации
python3 update_docs.py

5. Запуск RAG сервера
python3 rag_server.py

6. Запуск расширенного MCP сервера
cd mcp-server
npm run start:enhanced

7. Настройка MCP в вашем ИИ ассистенте
Следуйте инструкциям для Claude Desktop или VS Code Cline.
8. Тестирование системы
В Claude или Cline попробуйте эти команды:
get_rag_stats
ask_rag "Как создать класс в Python?" "python"
memory_bank_status
file_watcher_start

🎯 Простой менеджер документации
Проект включает Простой менеджер документации (update_docs.py), который автоматизирует работу с документацией одной командой.
🚀 Ключевые возможности:

📁 Обнаружение по папкам: Автоматически сканирует папку documentation/ на наличие документации технологий
🏷️ Умное именование: Определяет типы технологий по именам папок (например, python_docs → Python)
🔄 Конвертация HTML: Конвертирует HTML документацию в Markdown когда необходимо
📝 Обновление конфигурации: Автоматически обновляет config.yaml с новыми технологиями
📚 Полная индексация: Индексирует всё в RAG базу данных
⚡ Настройка одной командой: Одна команда обрабатывает всё автоматически

📋 Простой справочник команд:
python3 update_docs.py  # Полная автоматическая синхронизация
python3 update_docs.py --scan  # Предварительный просмотр что будет обработано
python3 update_docs.py --verbose  # Подробный вывод для отладки

🎯 Идеальный workflow для новых технологий:

📁 Добавьте документацию в папку documentation/:# Примеры:
git clone https://github.com/python/cpython.git documentation/python_docs
cp -r /путь/к/java_docs documentation/java_docs


🔄 Запустите автоматическую синхронизацию: python3 update_docs.py
✅ Готово! Технология автоматически определена, конвертирована и проиндексирована

🏷️ Определение технологий по именам папок:
Система автоматически распознаёт технологии по именам папок:

python_docs → Python
java_docs → Java
custom_project_docs → Custom Project
И любые другие → Использует имя папки как имя технологии

🛠️ Доступные MCP инструменты
RAG инструменты

ask_rag - Запрос к документации любой технологии

question: Ваш вопрос (строка)
framework: Целевая технология (например, "python", "java", "my_project")
model: LLM модель (qwen, deepseek) - опционально
max_results: Количество результатов (1-20) - опционально


list_frameworks - Получить доступные технологии

get_rag_stats - Статистика базы данных

list_models - Доступные LLM модели


Memory Bank инструменты

memory_bank_init - Инициализировать память проекта
memory_bank_status - Проверить статус memory bank
memory_bank_read - Прочитать файл memory bank
filename: Файл для чтения (tasks.md, progress.md, и т.д.)


memory_bank_write - Записать в memory bank
filename: Целевой файл
content: Содержимое файла


memory_bank_search - Поиск в истории проекта
query: Поисковые термины


memory_bank_archive - Архивировать завершенную задачу
taskId: Идентификатор задачи
summary: Краткое описание задачи
completedWork: Описание работы
keyDecisions: Важные решения
lessonsLearned: Извлеченные уроки



File Watcher инструменты

file_watcher_start - Начать мониторинг файлов
file_watcher_stop - Остановить мониторинг
file_watcher_stats - Получить статистику мониторинга

💡 Примеры использования
Ниже приведены примеры использования системы с разными технологиями. Обратите внимание, что система не ограничена этими технологиями; вы можете использовать её с любой документацией, которую добавите в папку documentation/.
Разработка на Python
# Получить помощь по Python
ask_rag("Как создать класс в Python?", "python")

# Отследить вашу работу
memory_bank_write("activeContext.md", "Создание Python скриптов с ООП")

# Начать мониторинг изменений
file_watcher_start()

# Поиск в истории проекта
memory_bank_search("классы")

Разработка API на Java
# Узнать о Java API
ask_rag("Как использовать потоки в Java?", "java")

# Обновить прогресс проекта
memory_bank_write("progress.md", "## Текущая задача\nРеализация потоков Java для обработки данных")

# Архивировать завершенную функцию
memory_bank_archive("java-streams", {
  "summary": "Реализовано потоковое обработка",
  "completedWork": "Созданы операции потоков для фильтрации данных",
  "keyDecisions": "Использованы потоки Java 8 для лучшей производительности"
})

Разработка собственного проекта
# Получить помощь для вашего собственного проекта
ask_rag("Как реализовать функцию X в моем проекте?", "my_project")

# Отследить разработку проекта
memory_bank_write("techContext.md", "Создание пользовательской функции с особыми требованиями")

🔧 Конфигурация
Структура config.yaml
frameworks:
  # Добавьте ваши технологии здесь
  python:
    enabled: true
    path: /путь/к/python_docs
    description: Python Programming Language
  java:
    enabled: true
    path: /путь/к/java_docs
    description: Java Programming Language
  # Пример для вашего собственного проекта
  my_project:
    enabled: true
    path: /путь/к/my_project_docs
    description: My Custom Project Documentation

Структура файлов Memory Bank
memory-bank/
├── tasks.md              # Текущие задачи
├── activeContext.md      # Текущий контекст
├── progress.md           # Прогресс разработки
├── projectbrief.md       # Основа проекта
├── productContext.md     # Контекст продукта
├── systemPatterns.md     # Системные паттерны
├── techContext.md        # Технический контекст
├── style-guide.md        # Руководство по стилю
├── creative/             # Дизайнерские решения
├── reflection/           # Рефлексии по задачам
└── archive/              # Завершенные задачи

🚨 Устранение неполадок
Проблемы с RAG сервером
# Проверить, запущен ли сервер
curl http://localhost:8000/stats

# Перезапустить сервер
python3 rag_server.py

# Проверить логи
tail -f logs/rag_system.log

Проблемы с MCP сервером
# Тестировать MCP сервер
cd mcp-server
npm run test:memory-bank

# Перезапустить расширенный сервер
npm run start:enhanced

# Проверить версию Node.js
node --version  # Должна быть 16+

Проблемы с Memory Bank
# Проверить статус memory bank в Claude/Cline
memory_bank_status()

# Переинициализировать при необходимости
memory_bank_init()

# Проверить права доступа к файлам
ls -la memory-bank/

Проблемы с локальной LLM

LM Studio: Убедитесь, что сервер запущен на порту 1234
Ollama: Проверьте, что ollama serve активен
Модель: Убедитесь, что meta-llama-3.1-8b-instruct загружена
API: Протестируйте с curl http://127.0.0.1:1234/v1/models

📊 Мониторинг системы
Проверка состояния системы
# В Claude/Cline
get_rag_stats()           # Статус RAG базы данных
memory_bank_status()      # Статус memory bank  
file_watcher_stats()      # Статус мониторинга файлов
list_frameworks()         # Доступные технологии

Метрики производительности

RAG База данных: ~10,000+ индексированных документов
Время ответа: <2 секунд для большинства запросов
Использование памяти: ~500MB для полной системы
Мониторинг файлов: Обнаружение изменений в реальном времени


🤝 Contributing / Вклад в развитие
We welcome contributions! Please feel free to submit a Pull Request.Мы приветствуем вклад в развитие! Не стесняйтесь отправлять Pull Request.
📄 License / Лицензия
This project is licensed under the MIT License - see the LICENSE file for details.Этот проект лицензирован под MIT License - см. файл LICENSE для подробностей.

Created with ❤️ for enhanced AI-assisted developmentСоздано с ❤️ для улучшенной разработки с помощью ИИ
