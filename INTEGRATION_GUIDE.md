# 🔗 Интеграция Session Manager с RAG Сервером

Полное руководство по использованию интегрированной системы RAG сервера с умной памятью.

## 🎯 Что было интегрировано

### ✅ Основные компоненты
- **Session Manager** - система управления сессиями
- **RAG Server** - FastAPI сервер с документацией
- **Автоматическая интеграция** - бесшовная работа памяти

### ✅ Новые возможности
- **Автоопределение проектов** из путей файлов
- **Автосохранение диалогов** в сессии
- **Обогащение контекста** историей проекта
- **Автообнаружение ключевых моментов**

## 📋 Новые API Endpoints

### Session Management
```bash
# Создать новую сессию
POST /sessions/create?project_name=my-project

# Получить последнюю сессию проекта
GET /sessions/latest?project_name=my-project

# Информация о сессии
GET /sessions/{session_id}

# Все сессии проекта
GET /sessions/project/{project_name}

# Архивировать сессию
POST /sessions/{session_id}/archive

# Статистика сессий
GET /sessions/stats

# Добавить ключевой момент
POST /sessions/{session_id}/key-moment

# Очистить старые сессии
POST /sessions/cleanup?days_threshold=30

# Типы ключевых моментов
GET /sessions/key-moment-types
```

### Обновленные основные endpoints
```bash
# Обычный запрос с памятью
POST /ask

# IDE запрос с памятью
POST /ide/ask
```

## 🚀 Примеры использования

### 1. Создание сессии и запрос с памятью

```python
import requests

# Создать сессию
response = requests.post("http://localhost:8000/sessions/create", 
                        params={"project_name": "my_laravel_project"})
session_id = response.json()["session_id"]

# Запрос с использованием памяти
response = requests.post("http://localhost:8000/ask", json={
    "question": "Как создать модель User в Laravel?",
    "framework": "laravel",
    "project_name": "my_laravel_project",
    "session_id": session_id,
    "use_memory": True,
    "save_to_memory": True
})

print(response.json()["answer"])
```

### 2. IDE интеграция с автоопределением проекта

```python
# IDE запрос с автоопределением проекта
response = requests.post("http://localhost:8000/ide/ask", json={
    "question": "Как добавить валидацию к этой модели?",
    "file_path": "/path/to/my_laravel_project/app/Models/User.php",
    "project_path": "/path/to/my_laravel_project",
    "file_content": "<?php class User extends Model { ... }",
    "use_memory": True,
    "save_to_memory": True
})

# Проект автоматически определится как "my_laravel_project"
# Сессия будет найдена или создана автоматически
```

### 3. Получение контекста сессии

```python
# Получить полную информацию о сессии
response = requests.get(f"http://localhost:8000/sessions/{session_id}")
session_info = response.json()

print(f"Проект: {session_info['project_name']}")
print(f"Сообщений: {session_info['stats']['total_messages']}")
print(f"Ключевых моментов: {session_info['stats']['total_key_moments']}")

# Просмотр ключевых моментов
for moment in session_info['key_moments']:
    print(f"- {moment['title']}: {moment['summary']}")
```

### 4. Добавление ключевого момента

```python
# Добавить ключевой момент вручную
response = requests.post(f"http://localhost:8000/sessions/{session_id}/key-moment", 
                        params={
                            "moment_type": "feature_completed",
                            "title": "Система авторизации",
                            "summary": "Реализована полная система авторизации пользователей",
                            "importance": 8,
                            "files": ["app/Models/User.php", "app/Controllers/AuthController.php"],
                            "context": "Завершение работы над авторизацией"
                        })
```

### 5. Работа с проектами

```python
# Получить все сессии проекта
response = requests.get("http://localhost:8000/sessions/project/my_laravel_project")
sessions = response.json()["sessions"]

# Получить последнюю сессию проекта
response = requests.get("http://localhost:8000/sessions/latest", 
                       params={"project_name": "my_laravel_project"})
latest_session = response.json()
```

## 🔧 Конфигурация

### config.yaml
```yaml
# Настройки системы памяти
session_memory:
  enabled: true
  db_path: "./session_storage.db"
  max_messages: 200
  compression_threshold: 50
  auto_detect_moments: true
  cleanup_days: 30
  auto_save_interactions: true
```

### Модели данных

#### QueryRequest (обновленная)
```python
{
    "question": "Как создать модель?",
    "framework": "laravel",
    "project_name": "my_project",        # Имя проекта
    "project_path": "/path/to/project",  # Путь к проекту (для автоопределения)
    "session_id": "uuid-string",        # ID существующей сессии
    "use_memory": true,                 # Использовать контекст сессии
    "save_to_memory": true              # Сохранять взаимодействие в память
}
```

#### QueryResponse (обновленная)
```python
{
    "answer": "Для создания модели в Laravel...",
    "sources": [...],
    "total_docs": 5,
    "response_time": 1.23,
    "framework_detected": "laravel",
    "session_id": "uuid-string",
    "session_context_used": true,
    "key_moments_detected": [
        {
            "type": "feature_completed",
            "title": "Создание модели",
            "summary": "Объяснено создание модели User"
        }
    ]
}
```

## 🧠 Как работает умная память

### 1. Автоопределение проекта
```python
# Из project_path
"/path/to/my_laravel_project" → "my_laravel_project"

# Из file_path
"/path/to/my_laravel_project/app/Models/User.php" → "my_laravel_project"
```

### 2. Автоматическое создание/поиск сессий
```python
# Логика работы
def get_or_create_session(project_name, session_id=None):
    if session_id:
        # Проверяем существующую сессию
        return session_id if exists(session_id) else None
    
    if project_name:
        # Ищем последнюю сессию проекта
        latest = get_latest_session(project_name)
        if latest:
            return latest
        
        # Создаем новую сессию
        return create_session(project_name)
    
    # Анонимная сессия
    return create_session("anonymous")
```

### 3. Обогащение контекста
```python
# Контекст включает:
- Информация о проекте
- Топ-3 ключевых момента
- Последний период сжатой истории  
- Последние 3 сообщения
- Базовый контекст запроса
```

### 4. Автосохранение диалогов
```python
# После каждого ответа:
1. Сохраняется вопрос пользователя
2. Сохраняется ответ ассистента
3. Автоматически обнаруживаются ключевые моменты
4. Обновляется история сессии
```

## 🔄 Рабочий процесс

### Типичный сценарий использования

1. **Пользователь задает вопрос** с указанием project_path
2. **Система автоопределяет проект** из пути
3. **Находит или создает сессию** для проекта
4. **Получает контекст сессии** (история, ключевые моменты)
5. **Обогащает промпт** контекстом памяти
6. **Получает ответ от LLM** с учетом контекста
7. **Сохраняет диалог** в сессию
8. **Автоматически обнаруживает** ключевые моменты

### Пример полного цикла
```python
# 1. Первый запрос
response1 = requests.post("/ask", json={
    "question": "Как создать модель User?",
    "project_path": "/path/to/my_project"
})
# → Создается новая сессия, базовый ответ

# 2. Второй запрос  
response2 = requests.post("/ask", json={
    "question": "Как добавить валидацию к User?",
    "project_path": "/path/to/my_project"
})
# → Используется та же сессия, контекст обогащен предыдущим диалогом

# 3. Третий запрос
response3 = requests.post("/ask", json={
    "question": "Как создать контроллер для User?",
    "project_path": "/path/to/my_project"
})
# → Еще больше контекста, связанный ответ
```

## 📊 Мониторинг и отладка

### Проверка статуса системы
```python
# Главная страница
response = requests.get("http://localhost:8000/")
print(response.json()["session_memory"])

# Статистика сессий
response = requests.get("http://localhost:8000/sessions/stats")
print(response.json())

# Статистика документов
response = requests.get("http://localhost:8000/stats")
print(response.json())
```

### Логирование
```python
# Настройка логов в config.yaml
logging:
  level: INFO
  file: ./logs/rag_system.log

# Важные события логируются:
# - Создание сессий
# - Обработка запросов с памятью
# - Автообнаружение ключевых моментов
# - Ошибки работы с сессиями
```

## 🚨 Устранение проблем

### Session Manager не инициализирован
```python
# Проверьте config.yaml
session_memory:
  enabled: true  # Должно быть true
  
# Перезапустите сервер
python rag_server.py
```

### Сессия не найдена
```python
# Проверьте существование сессии
response = requests.get(f"/sessions/{session_id}")
if response.status_code == 404:
    # Сессия не существует, создайте новую
    response = requests.post("/sessions/create", 
                           params={"project_name": project_name})
```

### Медленная работа
```python
# Очистите старые сессии
response = requests.post("/sessions/cleanup", 
                        params={"days_threshold": 15})

# Проверьте размер базы данных
import os
db_size = os.path.getsize("session_storage.db")
print(f"Размер базы: {db_size / 1024 / 1024:.2f} MB")
```

## 💡 Лучшие практики

### 1. Именование проектов
```python
# Хорошо
project_name = "my_laravel_ecommerce"

# Плохо  
project_name = "project1"
```

### 2. Использование project_path
```python
# Всегда передавайте project_path для автоопределения
{
    "question": "...",
    "project_path": "/full/path/to/project",
    "use_memory": true
}
```

### 3. Управление сессиями
```python
# Периодически очищайте старые сессии
requests.post("/sessions/cleanup", params={"days_threshold": 30})

# Архивируйте завершенные проекты
requests.post(f"/sessions/{session_id}/archive")
```

### 4. Ключевые моменты
```python
# Добавляйте важные моменты вручную
requests.post(f"/sessions/{session_id}/key-moment", params={
    "moment_type": "deployment",
    "title": "Продакшн деплой",
    "summary": "Проект успешно развернут в продакшн",
    "importance": 9
})
```

## 🔮 Расширенные возможности

### Интеграция с IDE
```python
# Пример плагина для VS Code
def on_file_open(file_path):
    project_path = get_project_root(file_path)
    
    # Получить контекст проекта
    response = requests.get("/sessions/latest", 
                           params={"project_name": extract_project_name(project_path)})
    
    # Показать ключевые моменты в сайдбаре
    show_key_moments(response.json()["context"]["key_moments"])
```

### Автоматизация CI/CD
```python
# В pipeline
def on_deploy_success():
    session_id = get_current_session()
    
    requests.post(f"/sessions/{session_id}/key-moment", params={
        "moment_type": "deployment",
        "title": f"Деплой {os.environ['GIT_COMMIT'][:7]}",
        "summary": "Успешный деплой в продакшн",
        "importance": 8
    })
```

Интегрированная система готова к использованию и обеспечивает мощную умную память для ваших проектов! 🚀