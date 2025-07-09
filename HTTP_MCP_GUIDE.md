# HTTP-MCP Server для RAG Assistant

## Архитектура

```
Claude-CLI  ──HTTP──▶  MCP-сервер (порт 8200)  ──HTTP──▶  RAG-backend (FastAPI)
                              │
                              └─ SQLite (session_storage.db)
```

## Установка и запуск

### 1. Установка зависимостей

```bash
cd mcp-server
npm install
```

### 2. Запуск сервисов

#### Шаг 1: Запустите RAG сервер
```bash
cd /Users/aleksejcuprynin/PycharmProjects/chanki
source venv/bin/activate
python rag_server.py
```

#### Шаг 2: Запустите HTTP-MCP сервер
```bash
cd mcp-server
npm run start:http
```

Сервер запустится на `http://127.0.0.1:8200`

### 3. Регистрация в Claude

Вариант 1: Используйте файл `.mcp.json` в корне проекта

Вариант 2: Добавьте вручную:
```bash
claude mcp add --transport http rag-server http://localhost:8200/mcp
```

## Доступные инструменты

### 1. ask_rag
Основной инструмент для вопросов к RAG
```json
POST /tool/ask_rag
{
  "query": "Что такое компонент?",
  "framework": "vue",  // опционально
  "model": "deepseek", // опционально: qwen или deepseek
  "max_results": 5
}
```

### 2. get_recent_changes
Получение ключевых моментов из сессии
```json
POST /tool/get_recent_changes
{
  "limit": 10
}
```

### 3. run_tests
Запуск тестов (заглушка)
```json
POST /tool/run_tests
{}
```

### 4. build_project
Сборка проекта (заглушка)
```json
POST /tool/build_project
{}
```

### 5. apply_patch
Применение патча с созданием ключевого момента
```json
POST /tool/apply_patch
{
  "diff": "--- a/file.js\n+++ b/file.js\n...",
  "files": ["file.js"]
}
```

### 6. run_linters
Запуск линтеров (заглушка)
```json
POST /tool/run_linters
{}
```

### 7. open_file
Чтение файла
```json
POST /tool/open_file
{
  "path": "path/to/file.js"
}
```

### 8. list_frameworks
Список доступных фреймворков
```json
POST /tool/list_frameworks
{}
```

### 9. list_models
Список доступных LLM моделей
```json
POST /tool/list_models
{}
```

### 10. get_stats
Статистика RAG базы данных
```json
POST /tool/get_stats
{}
```

### 11. save_tool_call
Системный инструмент для логирования
```json
POST /tool/save_tool_call
{
  "tool_name": "ask_rag",
  "parameters": {...},
  "result": "..."
}
```

### 12. save_file_change
Системный инструмент для логирования изменений файлов
```json
POST /tool/save_file_change
{
  "file_path": "path/to/file",
  "old_content": "...",
  "new_content": "..."
}
```

## Дополнительные endpoints

### Health check
```
GET /health
```

### Статистика вызовов
```
GET /stats/calls
```

## Политика ключевых моментов

- Система хранит 10 последних ключевых моментов
- Автоматическое определение ключевых моментов из контента
- Типы моментов:
  - ERROR_SOLVED (важность: 8)
  - FEATURE_COMPLETED (важность: 7)
  - CONFIG_CHANGED (важность: 6)
  - BREAKTHROUGH (важность: 9)
  - FILE_CREATED (важность: 5)
  - DEPLOYMENT (важность: 8)
  - IMPORTANT_DECISION (важность: 7)
  - REFACTORING (важность: 6)

## Chunking больших ответов

Если ответ превышает 4000 токенов, он автоматически разбивается на чанки:
```json
{
  "segment": "1/3",
  "data": {...}
}
```

## Логирование

Все вызовы инструментов логируются в SQLite базу данных:
- Таблица: `mcp_calls`
- Поля: `tool_name`, `args_json`, `result_json`, `success`, `ts`

## Тестирование

Запустите тестовый скрипт:
```bash
python test_http_mcp.py
```

## Пример использования в Claude

```
User: Исправь ошибку 'module is not defined' в postcss.config.js

Claude: [использует ask_rag для получения рекомендаций]
Claude: [использует apply_patch для применения исправления]
Claude: [использует run_tests для проверки]
Claude: [создает key_moment "PostCSS bug fixed"]
```

## Конфигурация

В `config.yaml`:
```yaml
mcp:
  base_url: http://127.0.0.1:8200
  chunk_limit_tokens: 4000
  key_moments_limit: 10
  tools_enabled:
    - ask_rag
    - get_recent_changes
    - run_tests
    # ... и другие
```

## Устранение проблем

### MCP сервер не запускается
- Проверьте, что порт 8200 свободен
- Убедитесь, что RAG сервер запущен на порту 8000

### Ошибки при вызове инструментов
- Проверьте логи в консоли MCP сервера
- Посмотрите статистику: `GET /stats/calls`

### Нет ключевых моментов
- Убедитесь, что Session Manager включен в config.yaml
- Проверьте, что база данных session_storage.db создана
