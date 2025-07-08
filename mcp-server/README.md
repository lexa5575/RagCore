# RAG MCP Server

MCP сервер для интеграции RAG Assistant с Cline в VS Code.

## Установка

1. Установите зависимости:
```bash
cd mcp-server
npm install
```

2. Убедитесь, что запущены:
   - LLM модель на `http://127.0.0.1:1234`
   - RAG сервер на `http://localhost:8000`

## Настройка в Cline

Добавьте в настройки Cline (обычно в `~/Library/Application Support/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json` на macOS):

```json
{
  "mcpServers": {
    "rag-assistant": {
      "command": "node",
      "args": ["/Users/aleksejcuprynin/PycharmProjects/chanki/mcp-server/index.js"],
      "env": {}
    }
  }
}
```

## Доступные инструменты

### 1. `ask_rag`
Задать вопрос RAG серверу и получить ответ на основе документации.

**Параметры:**
- `question` (обязательный) - Вопрос пользователя
- `framework` (опциональный) - Фреймворк для фильтрации: vue, laravel, alpine, filament, inertia, tailwindcss
- `model` (опциональный) - Модель LLM для ответа: qwen или deepseek
- `max_results` (опциональный) - Максимальное количество результатов (1-20, по умолчанию 5)

**Примеры использования в Cline:**
- "Используй ask_rag чтобы узнать как создать компонент в Vue"
- "Спроси у RAG как создать миграцию в Laravel"
- "Используй ask_rag с model=deepseek чтобы узнать что такое компонент"

### 2. `list_frameworks`
Получить список доступных фреймворков с описаниями.

**Пример использования:**
- "Покажи список доступных фреймворков"

### 3. `get_stats`
Получить статистику базы данных RAG.

**Пример использования:**
- "Покажи статистику RAG базы"

### 4. `list_models`
Получить список доступных LLM моделей.

**Пример использования:**
- "Покажи список доступных моделей"
- "Какие LLM модели доступны"

## Доступные ресурсы

- `rag://frameworks` - Информация о доступных фреймворках
- `rag://stats` - Статистика документов в базе
- `rag://models` - Информация о доступных LLM моделях

## Архитектура

```
Cline <-> MCP Server <-> RAG Server <-> LLM Model
                              |
                              v
                         ChromaDB
```

## Отладка

Логи MCP сервера выводятся в stderr и видны в консоли Cline.

Для тестирования можно запустить сервер вручную:
```bash
node index.js
```

## Требования

- Node.js 16+
- Запущенный RAG сервер на http://localhost:8000
- Запущенная LLM модель на http://127.0.0.1:1234
