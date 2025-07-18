from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class QueryRequest(BaseModel):
    """
    Запрос к RAG системе для получения ответа на вопрос.
    
    Основной способ взаимодействия с системой - отправить вопрос и получить
    ответ на основе документации фреймворков с использованием контекста сессии.
    """
    question: str = Field(
        ..., 
        description="Вопрос пользователя на любом языке. Система поддерживает технические вопросы по Laravel, Vue.js, Filament и другим фреймворкам.",
        example="Как создать модель в Laravel с миграцией?"
    )
    framework: Optional[str] = Field(
        None, 
        description="Фильтр по конкретному фреймворку. Доступные: 'laravel', 'vue', 'filament', 'alpine', 'inertia', 'tailwindcss'. Если не указан, система автоопределит.",
        example="laravel"
    )
    max_results: int = Field(
        5, 
        ge=1, 
        le=20, 
        description="Максимальное количество документов для поиска. Больше документов = более полный ответ, но медленнее.",
        example=5
    )
    context: Optional[str] = Field(
        None, 
        description="Дополнительный контекст для уточнения вопроса. Может включать код, описание проблемы, версии фреймворков.",
        example="Использую Laravel 10, нужно создать модель User с полями name, email, password"
    )
    model: Optional[str] = Field(
        None, 
        description="Модель LLM для генерации ответа. Если не указано, используется модель по умолчанию.",
        example="llama3.1:8b"
    )
    # Поля для интеграции с системой памяти
    project_name: Optional[str] = Field(
        None, 
        description="Имя проекта для создания/использования сессии. Помогает группировать вопросы по проектам.",
        example="my-laravel-app"
    )
    project_path: Optional[str] = Field(
        None, 
        description="Путь к проекту для автоопределения имени проекта и контекста.",
        example="/home/user/projects/my-app"
    )
    session_id: Optional[str] = Field(
        None, 
        description="ID существующей сессии для продолжения диалога. Если не указан, создается новая сессия.",
        example="uuid-session-id"
    )
    use_memory: bool = Field(
        True, 
        description="Использовать контекст предыдущих сообщений и ключевых моментов сессии для более точного ответа."
    )
    save_to_memory: bool = Field(
        True, 
        description="Сохранять текущее взаимодействие в память сессии для будущих запросов."
    )


class QueryResponse(BaseModel):
    """
    Ответ RAG системы на пользовательский запрос.
    
    Содержит сгенерированный ответ, использованные источники, 
    метаданные о поиске и сессии.
    """
    answer: str = Field(
        ..., 
        description="Сгенерированный ответ на вопрос пользователя на основе найденных документов и контекста сессии.",
        example="Для создания модели в Laravel используйте команду: php artisan make:model User -m"
    )
    sources: List[Dict[str, Any]] = Field(
        ..., 
        description="Список источников (документов), использованных для генерации ответа. Каждый источник содержит title, content, framework, relevance_score.",
        example=[{
            "title": "Eloquent Models",
            "content": "Eloquent models are used to interact with database tables...",
            "framework": "laravel",
            "relevance_score": 0.85
        }]
    )
    total_docs: int = Field(
        ..., 
        description="Общее количество документов, найденных для данного запроса.",
        example=5
    )
    response_time: float = Field(
        ..., 
        description="Время генерации ответа в секундах.",
        example=1.234
    )
    framework_detected: Optional[str] = Field(
        None, 
        description="Автоопределенный фреймворк на основе вопроса и контекста.",
        example="laravel"
    )
    # Поля для интеграции с системой памяти
    session_id: Optional[str] = Field(
        None, 
        description="ID сессии, в которой был обработан запрос. Используется для продолжения диалога.",
        example="uuid-session-id"
    )
    session_context_used: bool = Field(
        False, 
        description="Указывает, был ли использован контекст предыдущих сообщений сессии для генерации ответа."
    )
    key_moments_detected: List[Dict[str, Any]] = Field(
        [], 
        description="Автоматически обнаруженные ключевые моменты в диалоге (решение проблемы, завершение задачи и т.д.).",
        example=[{
            "type": "problem_solved",
            "title": "Создание модели User",
            "summary": "Пользователь успешно создал модель User с миграцией"
        }]
    )
