# 🚀 RAG Server + Memory Bank Integration
## Intelligent Documentation Assistant with Project Memory

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Node.js 16+](https://img.shields.io/badge/node-16+-green.svg)](https://nodejs.org/)

> **A comprehensive RAG (Retrieval-Augmented Generation) system with intelligent project memory management for AI assistants like Claude and Cline.**

### 🌍 Languages / Языки
- [🇺🇸 English Documentation](#english-documentation)
- [🇷🇺 Русская документация](#русская-документация)

---

## ENGLISH DOCUMENTATION

### 🎯 What is this?

This project combines a powerful **RAG (Retrieval-Augmented Generation) server** with an intelligent **Memory Bank system** to create the ultimate development assistant. It provides:

- **📚 Smart Documentation Search** - Query documentation for Laravel, Vue.js, Filament, Alpine.js, and Tailwind CSS
- **🧠 Project Memory** - Automatically tracks project context, tasks, and development history
- **👁️ File Monitoring** - Real-time tracking of code changes and key development moments
- **🔗 Unified Interface** - Single MCP server integrating all components
- **🤖 Local LLM Support** - Uses meta-llama-3.1-8b-instruct for intelligent responses

### 🏗️ System Architecture

```
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
```

### 📦 Installation

#### Prerequisites
- **Python 3.8+** with pip
- **Node.js 16+** with npm
- **Local LLM Server** (LM Studio, Ollama, or similar)
- **Claude Desktop** or **VS Code with Cline extension**

#### Step 1: Clone and Setup Python Environment
```bash
git clone https://github.com/lexa5575/rag_server.git
cd rag_server

# Install Python dependencies
pip install -r requirements.txt
```

#### Step 2: Setup Node.js Dependencies
```bash
cd mcp-server
npm install
cd ..
```

#### Step 3: Configure Local LLM
1. **Install LM Studio** or **Ollama**
2. **Download meta-llama-3.1-8b-instruct model**
3. **Start local server** on `http://127.0.0.1:1234` (LM Studio) or `http://localhost:11434` (Ollama)

#### Step 4: Configure Framework Documentation
```bash
# The system supports these frameworks out of the box:
# - Laravel (laravel_docs/)
# - Vue.js (vue_docs/)  
# - Filament (filament_docs/)
# - Alpine.js (alpine_docs/)
# - Tailwind CSS (tailwindcss_docs/)

# Documentation paths are configured in config.yaml
```

#### Step 5: Add Documentation to documentation/ folder
```bash
# Simply copy or clone documentation into documentation/ folder
# Examples:
git clone https://github.com/vuejs/docs.git documentation/vue_docs
git clone https://github.com/laravel/docs.git documentation/laravel_docs
cp -r /path/to/react_docs documentation/react_docs

# The system will automatically detect framework types by folder names:
# vue_docs → Vue.js, laravel_docs → Laravel, react_docs → React, etc.
```

### 🚀 Quick Start

#### 1. Run Installation Script
```bash
./install.sh
```
*This will install all dependencies and check your system*

#### 2. Configure Your Local LLM (One-time setup)
The system automatically creates `config.local.yaml` during installation. **You must configure it once for your LLM setup:**

```bash
# Edit your local LLM configuration
nano config.local.yaml
```

**For LM Studio users (recommended):**
- Keep default settings in `config.local.yaml`
- Just change `model_name` to your loaded model name
- Ensure LM Studio server is running on port 1234

**For Ollama users:**
```yaml
llm:
  default_model: ollama
  models:
    ollama:
      api_url: http://localhost:11434/api/generate
      model_name: llama3.1:8b  # Your Ollama model
```

**For other LLM services:**
- Edit the appropriate section in `config.local.yaml`
- See examples for OpenAI API, DeepSeek, and custom models

**⚠️ Important:** This is a **one-time setup**. After configuring your LLM, you'll never need to touch this again!

#### 3. 📁 Add Documentation to `documentation/` Folder

**IMPORTANT: All documentation must be placed in the `documentation/` folder!**

```bash
# Create documentation folder if it doesn't exist
mkdir -p documentation

# Copy your documentation folders to documentation/ directory
# Examples:
cp -r /path/to/laravel_docs documentation/
cp -r /path/to/vue_docs documentation/
cp -r /path/to/react_docs documentation/
cp -r /path/to/django_docs documentation/

# Or clone directly into documentation/ folder:
git clone https://github.com/vuejs/docs.git documentation/vue_docs
git clone https://github.com/laravel/docs.git documentation/laravel_docs
git clone https://github.com/filamentphp/filament.git documentation/filament_docs
```

**📋 Folder naming examples:**
- `documentation/vue_docs/` → Vue.js framework
- `documentation/laravel_docs/` → Laravel framework  
- `documentation/react_docs/` → React framework
- `documentation/tailwindcss_docs/` → Tailwind CSS framework

#### 4. 🚀 Run Automatic Documentation Sync

**THE MAIN COMMAND:**
```bash
python3 update_docs.py
```

**Preview command (recommended first):**
```bash
python3 update_docs.py --scan
```

*The system will automatically:*
- *Scan `documentation/` folder for framework documentation*
- *Detect framework types by folder names (vue_docs → Vue.js, laravel_docs → Laravel)*
- *Convert HTML to Markdown if needed*
- *Update config.yaml with new frameworks*
- *Index everything into the RAG database*

#### 5. Start the RAG Server
```bash
python3 rag_server.py
```
*Server will start on http://localhost:8000*

#### 6. Start the Enhanced MCP Server
```bash
cd mcp-server
npm run start:enhanced
```

#### 7. Configure MCP in Your AI Assistant

**For Claude Desktop:**
Add to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "enhanced-rag-memory-bank": {
      "command": "node",
      "args": ["/path/to/rag_server/mcp-server/enhanced-mcp-server.js"],
      "env": {
        "RAG_SERVER_URL": "http://localhost:8000"
      }
    }
  }
}
```

**For VS Code Cline:**
Add to `.mcp.json` in your project:
```json
{
  "mcpServers": {
    "enhanced-rag-memory-bank": {
      "command": "node",
      "args": ["mcp-server/enhanced-mcp-server.js"],
      "env": {
        "RAG_SERVER_URL": "http://localhost:8000"
      }
    }
  }
}
```

#### 8. Test the System
In Claude or Cline, try these commands:
```
Use get_rag_stats to check the system status
Use ask_rag with question "How to create a component in Vue.js?" and framework "vue"
Use memory_bank_status to check project memory (auto-initializes if needed)
Use file_watcher_start to begin tracking changes
```

**🎯 Smart Auto-Initialization:** Memory Bank now automatically initializes when you first use any memory_bank_* function. No manual setup required!

### 🎯 Simple Documentation Manager

The project includes a **Simple Documentation Manager** (`update_docs.py`) that completely automates the documentation workflow with one command:

#### 🚀 Key Features:
- **📁 Folder-Based Discovery**: Automatically scans `documentation/` folder for framework documentation
- **🏷️ Smart Naming**: Determines framework types by folder names (vue_docs → Vue.js, laravel_docs → Laravel)
- **🔄 HTML Conversion**: Converts HTML documentation to Markdown when needed
- **📝 Config Updates**: Automatically updates config.yaml with new frameworks
- **📚 Full Indexing**: Indexes everything into the RAG database
- **⚡ One-Command Setup**: Single command handles everything automatically

#### 📋 Simple Command Reference:
```bash
# 🔄 Full automatic synchronization - THE MAIN COMMAND
python3 update_docs.py

# 👀 Preview what will be processed (without indexing)
python3 update_docs.py --scan

# 📝 Verbose output for debugging
python3 update_docs.py --verbose
```

#### 🎯 Perfect Workflow for New Frameworks:
1. **📁 Add documentation** to `documentation/` folder:
   ```bash
   # Examples:
   git clone https://github.com/vuejs/docs.git documentation/vue_docs
   cp -r /path/to/react_docs documentation/react_docs
   ```
2. **🔄 Run automatic sync**: `python3 update_docs.py`
3. **✅ Done!** Framework is automatically detected, converted, and indexed

#### 🏷️ Framework Detection by Folder Names:
The system automatically recognizes frameworks by folder names:
- **vue_docs** → Vue.js
- **laravel_docs** → Laravel  
- **react_docs** → React
- **tailwindcss_docs** → Tailwind CSS
- **alpine_docs** → Alpine.js
- **filament_docs** → Filament
- **angular_docs** → Angular
- **svelte_docs** → Svelte
- **And any other** → Uses folder name as framework name

#### 📊 What Happens During Sync:
1. **🔍 Scan Phase**: Scans `documentation/` folder for framework folders
2. **🏷️ Detection Phase**: Determines framework names from folder names
3. **🔄 Conversion Phase**: Converts HTML to Markdown if needed
4. **📝 Config Phase**: Updates `config.yaml` with new frameworks
5. **📚 Indexing Phase**: Indexes all documentation into RAG database
6. **📊 Report Phase**: Shows detailed results and statistics

#### 💡 Pro Tips:
- Always run `--scan` first to see what will be processed
- Use consistent folder naming: `framework_docs` or `framework-docs`
- The system handles both HTML and Markdown documentation automatically
- Place all documentation in the `documentation/` folder for automatic detection
- No manual configuration needed - everything is automatic!

### 🛠️ Available MCP Tools

#### RAG Tools
- **`ask_rag`** - Query framework documentation
  - `question`: Your question (string)
  - `framework`: Target framework (vue, laravel, filament, alpine, tailwindcss)
  - `model`: LLM model (qwen, deepseek) - optional
  - `max_results`: Number of results (1-20) - optional

- **`list_frameworks`** - Get available frameworks
- **`get_rag_stats`** - Database statistics
- **`list_models`** - Available LLM models

#### Memory Bank Tools
- **`memory_bank_init`** - Initialize project memory
- **`memory_bank_status`** - Check memory bank status
- **`memory_bank_read`** - Read memory bank file
  - `filename`: File to read (tasks.md, progress.md, etc.)
- **`memory_bank_write`** - Write to memory bank
  - `filename`: Target file
  - `content`: File content
- **`memory_bank_search`** - Search project history
  - `query`: Search terms
- **`memory_bank_archive`** - Archive completed task
  - `taskId`: Task identifier
  - `summary`: Task summary
  - `completedWork`: Work description
  - `keyDecisions`: Important decisions
  - `lessonsLearned`: Lessons learned

#### File Watcher Tools
- **`file_watcher_start`** - Start monitoring files
- **`file_watcher_stop`** - Stop monitoring
- **`file_watcher_stats`** - Get monitoring statistics

### 💡 Usage Examples

#### Laravel Development
```
# Get Laravel-specific help
ask_rag("How to create middleware in Laravel?", "laravel")

# Track your work
memory_bank_write("activeContext.md", "Working on authentication middleware")

# Start monitoring changes
file_watcher_start()

# Search project history
memory_bank_search("middleware")
```

#### Vue.js Development
```
# Learn about Vue components
ask_rag("How to use Composition API in Vue 3?", "vue")

# Update project progress
memory_bank_write("progress.md", "## Current Task\nImplementing reactive forms with Composition API")

# Archive completed feature
memory_bank_archive("vue-forms", {
  "summary": "Implemented reactive forms",
  "completedWork": "Created form components with validation",
  "keyDecisions": "Used Composition API for better reusability"
})
```

#### Filament Admin Panel
```
# Get Filament guidance
ask_rag("How to create a resource in Filament?", "filament")

# Track admin panel development
memory_bank_write("techContext.md", "Building admin panel with Filament v3")
```

### 🔧 Configuration

#### config.yaml Structure
```yaml
# LLM Configuration
llm:
  models:
    qwen:
      api_url: http://127.0.0.1:1234/v1/completions
      model_name: meta-llama-3.1-8b-instruct
      max_tokens: 800
      temperature: 0.2

# Framework Paths
frameworks:
  laravel:
    enabled: true
    path: /path/to/laravel_docs
    description: Laravel - PHP Framework for Web Artisans
  vue:
    enabled: true
    path: /path/to/vue_docs
    description: Vue.js - Progressive JavaScript Framework

# Database Settings
database:
  collection_name: universal_docs
  path: ./chroma_storage
```

#### Memory Bank File Structure
```
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
```

### 🚨 Troubleshooting

#### RAG Server Issues
```bash
# Check if server is running
curl http://localhost:8000/stats

# Restart server
python3 rag_server.py

# Check logs
tail -f logs/rag_system.log
```

#### MCP Server Issues
```bash
# Test MCP server
cd mcp-server
npm run test:memory-bank

# Restart enhanced server
npm run start:enhanced

# Check Node.js version
node --version  # Should be 16+
```

#### Memory Bank Issues
```bash
# Check memory bank status in Claude/Cline
memory_bank_status()

# Reinitialize if needed
memory_bank_init()

# Check file permissions
ls -la memory-bank/
```

#### Local LLM Issues
- **LM Studio**: Ensure server is running on port 1234
- **Ollama**: Check `ollama serve` is active
- **Model**: Verify meta-llama-3.1-8b-instruct is loaded
- **API**: Test with `curl http://127.0.0.1:1234/v1/models`

### 📊 System Monitoring

#### Check System Health
```
# In Claude/Cline
get_rag_stats()           # RAG database status
memory_bank_status()      # Memory bank status  
file_watcher_stats()      # File monitoring status
list_frameworks()         # Available frameworks
```

#### Performance Metrics
- **RAG Database**: ~10,000+ indexed documents
- **Response Time**: <2 seconds for most queries
- **Memory Usage**: ~500MB for full system
- **File Monitoring**: Real-time change detection

---

## РУССКАЯ ДОКУМЕНТАЦИЯ

### 🎯 Что это такое?

Этот проект объединяет мощный **RAG (Retrieval-Augmented Generation) сервер** с интеллектуальной системой **Memory Bank** для создания идеального помощника разработчика. Система предоставляет:

- **📚 Умный поиск по документации** - Запросы к документации Laravel, Vue.js, Filament, Alpine.js и Tailwind CSS
- **🧠 Память проекта** - Автоматическое отслеживание контекста проекта, задач и истории разработки
- **👁️ Мониторинг файлов** - Отслеживание изменений кода и ключевых моментов разработки в реальном времени
- **🔗 Единый интерфейс** - Один MCP сервер, объединяющий все компоненты
- **🤖 Поддержка локальной LLM** - Использует meta-llama-3.1-8b-instruct для интеллектуальных ответов

### 🏗️ Архитектура системы

```
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
```

### 📦 Установка

#### Требования
- **Python 3.8+** с pip
- **Node.js 16+** с npm
- **Локальный LLM сервер** (LM Studio, Ollama или аналогичный)
- **Claude Desktop** или **VS Code с расширением Cline**

#### Шаг 1: Клонирование и настройка Python окружения
```bash
git clone https://github.com/lexa5575/rag_server.git
cd rag_server

# Установка Python зависимостей
pip install -r requirements.txt
```

#### Шаг 2: Настройка Node.js зависимостей
```bash
cd mcp-server
npm install
cd ..
```

#### Шаг 3: Настройка локальной LLM
1. **Установите LM Studio** или **Ollama**
2. **Скачайте модель meta-llama-3.1-8b-instruct**
3. **Запустите локальный сервер** на `http://127.0.0.1:1234` (LM Studio) или `http://localhost:11434` (Ollama)

#### Шаг 4: Настройка документации фреймворков
```bash
# Система поддерживает эти фреймворки из коробки:
# - Laravel (laravel_docs/)
# - Vue.js (vue_docs/)  
# - Filament (filament_docs/)
# - Alpine.js (alpine_docs/)
# - Tailwind CSS (tailwindcss_docs/)

# Пути к документации настраиваются в config.yaml
```

#### Шаг 5: Добавление документации в папку documentation/
```bash
# Просто скопируйте или клонируйте документацию в папку documentation/
# Примеры:
git clone https://github.com/vuejs/docs.git documentation/vue_docs
git clone https://github.com/laravel/docs.git documentation/laravel_docs
cp -r /путь/к/react_docs documentation/react_docs

# Система автоматически определит типы фреймворков по именам папок:
# vue_docs → Vue.js, laravel_docs → Laravel, react_docs → React, и т.д.
```

### 🚀 Быстрый старт

#### 1. Запуск скрипта установки
```bash
./install.sh
```
*Это установит все зависимости и проверит вашу систему*

#### 2. Настройка локальной LLM (одноразовая настройка)
Система автоматически создаёт `config.local.yaml` во время установки. **Вы должны настроить его один раз для вашей LLM:**

```bash
# Отредактируйте локальную конфигурацию LLM
nano config.local.yaml
```

**Для пользователей LM Studio (рекомендуется):**
- Оставьте стандартные настройки в `config.local.yaml`
- Просто измените `model_name` на название вашей загруженной модели
- Убедитесь, что сервер LM Studio запущен на порту 1234

**Для пользователей Ollama:**
```yaml
llm:
  default_model: ollama
  models:
    ollama:
      api_url: http://localhost:11434/api/generate
      model_name: llama3.1:8b  # Ваша модель Ollama
```

**Для других LLM сервисов:**
- Отредактируйте соответствующую секцию в `config.local.yaml`
- Смотрите примеры для OpenAI API, DeepSeek и кастомных моделей

**⚠️ Важно:** Это **одноразовая настройка**. После настройки вашей LLM, вам больше никогда не придётся это трогать!

#### 3. 📁 Добавьте документацию в папку `documentation/`

**ВАЖНО: Вся документация должна быть размещена в папке `documentation/`!**

```bash
# Создайте папку documentation если её нет
mkdir -p documentation

# Скопируйте папки с документацией в папку documentation/
# Примеры:
cp -r /путь/к/laravel_docs documentation/
cp -r /путь/к/vue_docs documentation/
cp -r /путь/к/react_docs documentation/
cp -r /путь/к/django_docs documentation/

# Или клонируйте напрямую в папку documentation/:
git clone https://github.com/vuejs/docs.git documentation/vue_docs
git clone https://github.com/laravel/docs.git documentation/laravel_docs
git clone https://github.com/filamentphp/filament.git documentation/filament_docs
```

**📋 Примеры именования папок:**
- `documentation/vue_docs/` → фреймворк Vue.js
- `documentation/laravel_docs/` → фреймворк Laravel  
- `documentation/react_docs/` → фреймворк React
- `documentation/tailwindcss_docs/` → фреймворк Tailwind CSS

#### 4. 🚀 Запустите автоматическую синхронизацию документации

**ОСНОВНАЯ КОМАНДА:**
```bash
python3 update_docs.py
```

**Команда предварительного просмотра (рекомендуется сначала):**
```bash
python3 update_docs.py --scan
```

*Система автоматически:*
- *Просканирует папку `documentation/` на наличие документации фреймворков*
- *Определит типы фреймворков по именам папок (vue_docs → Vue.js, laravel_docs → Laravel)*
- *Конвертирует HTML в Markdown если нужно*
- *Обновит config.yaml с новыми фреймворками*
- *Проиндексирует всё в RAG базу данных*

#### 5. Запуск RAG сервера
```bash
python3 rag_server.py
```
*Сервер запустится на http://localhost:8000*

#### 6. Запуск расширенного MCP сервера
```bash
cd mcp-server
npm run start:enhanced
```

#### 7. Настройка MCP в вашем ИИ ассистенте

**Для Claude Desktop:**
Добавьте в `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "enhanced-rag-memory-bank": {
      "command": "node",
      "args": ["/путь/к/rag_server/mcp-server/enhanced-mcp-server.js"],
      "env": {
        "RAG_SERVER_URL": "http://localhost:8000"
      }
    }
  }
}
```

**Для VS Code Cline:**
Добавьте в `.mcp.json` в вашем проекте:
```json
{
  "mcpServers": {
    "enhanced-rag-memory-bank": {
      "command": "node",
      "args": ["mcp-server/enhanced-mcp-server.js"],
      "env": {
        "RAG_SERVER_URL": "http://localhost:8000"
      }
    }
  }
}
```

#### 8. Тестирование системы
В Claude или Cline попробуйте эти команды:
```
Используй get_rag_stats чтобы проверить статус системы
Используй ask_rag с вопросом "Как создать компонент в Vue.js?" и framework "vue"
Используй memory_bank_init чтобы инициализировать память проекта
Используй file_watcher_start чтобы начать отслеживание изменений
```

### 🎯 Простой менеджер документации

Проект включает **Простой менеджер документации** (`update_docs.py`), который полностью автоматизирует работу с документацией одной командой:

#### 🚀 Ключевые возможности:
- **📁 Обнаружение по папкам**: Автоматически сканирует папку `documentation/` на наличие документации фреймворков
- **🏷️ Умное именование**: Определяет типы фреймворков по именам папок (vue_docs → Vue.js, laravel_docs → Laravel)
- **🔄 Конвертация HTML**: Конвертирует HTML документацию в Markdown когда необходимо
- **📝 Обновление конфигурации**: Автоматически обновляет config.yaml с новыми фреймворками
- **📚 Полная индексация**: Индексирует всё в RAG базу данных
- **⚡ Настройка одной командой**: Одна команда обрабатывает всё автоматически

#### 📋 Простой справочник команд:
```bash
# 🔄 Полная автоматическая синхронизация - ОСНОВНАЯ КОМАНДА
python3 update_docs.py

# 👀 Предварительный просмотр что будет обработано (без индексации)
python3 update_docs.py --scan

# 📝 Подробный вывод для отладки
python3 update_docs.py --verbose
```

#### 🎯 Идеальный workflow для новых фреймворков:
1. **📁 Добавьте документацию** в папку `documentation/`:
   ```bash
   # Примеры:
   git clone https://github.com/vuejs/docs.git documentation/vue_docs
   cp -r /путь/к/react_docs documentation/react_docs
   ```
2. **🔄 Запустите автоматическую синхронизацию**: `python3 update_docs.py`
3. **✅ Готово!** Фреймворк автоматически определён, конвертирован и проиндексирован

#### 🏷️ Определение фреймворков по именам папок:
Система автоматически распознаёт фреймворки по именам папок:
- **vue_docs** → Vue.js
- **laravel_docs** → Laravel  
- **react_docs** → React
- **tailwindcss_docs** → Tailwind CSS
- **alpine_docs** → Alpine.js
- **filament_docs** → Filament
- **angular_docs** → Angular
- **svelte_docs** → Svelte
- **И любые другие** → Использует имя папки как имя фреймворка

#### 📊 Что происходит во время синхронизации:
1. **🔍 Фаза сканирования**: Сканирует папку `documentation/` на наличие папок фреймворков
2. **🏷️ Фаза определения**: Определяет имена фреймворков по именам папок
3. **🔄 Фаза конвертации**: Конвертирует HTML в Markdown если нужно
4. **📝 Фаза конфигурации**: Обновляет `config.yaml` с новыми фреймворками
5. **📚 Фаза индексации**: Индексирует всю документацию в RAG базу данных
6. **📊 Фаза отчёта**: Показывает подробные результаты и статистику

#### 💡 Профессиональные советы:
- Всегда запускайте `--scan` сначала, чтобы увидеть что будет обработано
- Используйте последовательное именование папок: `framework_docs` или `framework-docs`
- Система обрабатывает как HTML, так и Markdown документацию автоматически
- Размещайте всю документацию в папке `documentation/` для автоматического обнаружения
- Никакой ручной настройки не требуется - всё автоматически!

### 🛠️ Доступные MCP инструменты

#### RAG инструменты
- **`ask_rag`** - Запрос к документации фреймворков
  - `question`: Ваш вопрос (строка)
  - `framework`: Целевой фреймворк (vue, laravel, filament, alpine, tailwindcss)
  - `model`: LLM модель (qwen, deepseek) - опционально
  - `max_results`: Количество результатов (1-20) - опционально

- **`list_frameworks`** - Получить доступные фреймворки
- **`get_rag_stats`** - Статистика базы данных
- **`list_models`** - Доступные LLM модели

#### Memory Bank инструменты
- **`memory_bank_init`** - Инициализировать память проекта
- **`memory_bank_status`** - Проверить статус memory bank
- **`memory_bank_read`** - Прочитать файл memory bank
  - `filename`: Файл для чтения (tasks.md, progress.md, и т.д.)
- **`memory_bank_write`** - Записать в memory bank
  - `filename`: Целевой файл
  - `content`: Содержимое файла
- **`memory_bank_search`** - Поиск в истории проекта
  - `query`: Поисковые термины
- **`memory_bank_archive`** - Архивировать завершенную задачу
  - `taskId`: Идентификатор задачи
  - `summary`: Краткое описание задачи
  - `completedWork`: Описание работы
  - `keyDecisions`: Важные решения
  - `lessonsLearned`: Извлеченные уроки

#### File Watcher инструменты
- **`file_watcher_start`** - Начать мониторинг файлов
- **`file_watcher_stop`** - Остановить мониторинг
- **`file_watcher_stats`** - Получить статистику мониторинга

### 💡 Примеры использования

#### Разработка на Laravel
```
# Получить помощь по Laravel
ask_rag("Как создать middleware в Laravel?", "laravel")

# Отследить вашу работу
memory_bank_write("activeContext.md", "Работаю над middleware для аутентификации")

# Начать мониторинг изменений
file_watcher_start()

# Поиск в истории проекта
memory_bank_search("middleware")
```

#### Разработка на Vue.js
```
# Изучить компоненты Vue
ask_rag("Как использовать Composition API в Vue 3?", "vue")

# Обновить прогресс проекта
memory_bank_write("progress.md", "## Текущая задача\nРеализация реактивных форм с Composition API")

# Архивировать завершенную функцию
memory_bank_archive("vue-forms", {
  "summary": "Реализованы реактивные формы",
  "completedWork": "Созданы компоненты форм с валидацией",
  "keyDecisions": "Использовали Composition API для лучшей переиспользуемости"
})
```

#### Админ панель Filament
```
# Получить руководство по Filament
ask_rag("Как создать ресурс в Filament?", "filament")

# Отследить разработку админ панели
memory_bank_write("techContext.md", "Создание админ панели с Filament v3")
```

### 🔧 Конфигурация

#### Структура config.yaml
```yaml
# Конфигурация LLM
llm:
  models:
    qwen:
      api_url: http://127.0.0.1:1234/v1/completions
      model_name: meta-llama-3.1-8b-instruct
      max_tokens: 800
      temperature: 0.2

# Пути к фреймворкам
frameworks:
  laravel:
    enabled: true
    path: /путь/к/laravel_docs
    description: Laravel - PHP Framework for Web Artisans
  vue:
    enabled: true
    path: /путь/к/vue_docs
    description: Vue.js - Progressive JavaScript Framework

# Настройки базы данных
database:
  collection_name: universal_docs
  path: ./chroma_storage
```

#### Структура файлов Memory Bank
```
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
```

### 🚨 Устранение неполадок

#### Проблемы с RAG сервером
```bash
# Проверить, запущен ли сервер
curl http://localhost:8000/stats

# Перезапустить сервер
python3 rag_server.py

# Проверить логи
tail -f logs/rag_system.log
```

#### Проблемы с MCP сервером
```bash
# Тестировать MCP сервер
cd mcp-server
npm run test:memory-bank

# Перезапустить расширенный сервер
npm run start:enhanced

# Проверить версию Node.js
node --version  # Должна быть 16+
```

#### Проблемы с Memory Bank
```bash
# Проверить статус memory bank в Claude/Cline
memory_bank_status()

# Переинициализировать при необходимости
memory_bank_init()

# Проверить права доступа к файлам
ls -la memory-bank/
```

#### Проблемы с локальной LLM
- **LM Studio**: Убедитесь, что сервер запущен на порту 1234
- **Ollama**: Проверьте, что `ollama serve` активен
- **Модель**: Убедитесь, что meta-llama-3.1-8b-instruct загружена
- **API**: Протестируйте с `curl http://127.0.0.1:1234/v1/models`

### 📊 Мониторинг системы

#### Проверка состояния системы
```
# В Claude/Cline
get_rag_stats()           # Статус RAG базы данных
memory_bank_status()      # Статус memory bank  
file_watcher_stats()      # Статус мониторинга файлов
list_frameworks()         # Доступные фреймворки
```

#### Метрики производительности
- **RAG База данных**: ~10,000+ индексированных документов
- **Время ответа**: <2 секунд для большинства запросов
- **Использование памяти**: ~500MB для полной системы
- **Мониторинг файлов**: Обнаружение изменений в реальном времени

---

## 🤝 Contributing / Вклад в развитие

We welcome contributions! Please feel free to submit a Pull Request.
Мы приветствуем вклад в развитие! Не стесняйтесь отправлять Pull Request.

## 📄 License / Лицензия

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
Этот проект лицензирован под MIT License - см. файл [LICENSE](LICENSE) для подробностей.

---

**Created with ❤️ for enhanced AI-assisted development**
**Создано с ❤️ для улучшенной разработки с помощью ИИ**
