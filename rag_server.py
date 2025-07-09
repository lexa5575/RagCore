#!/usr/bin/env python3
"""
Улучшенный RAG сервер с поддержкой IDE интеграции
Использует конфигурационный файл и универсальный подход
"""

import yaml
import time
import logging
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import chromadb
from sentence_transformers import SentenceTransformer
import requests
from session_manager import SessionManager, KeyMomentType, auto_detect_key_moments, MOMENT_IMPORTANCE

# Загрузка конфигурации
def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        raise Exception(f"Конфигурационный файл {config_path} не найден")

# Глобальная конфигурация
CONFIG = load_config()

# Настройка логирования
logging.basicConfig(
    level=getattr(logging, CONFIG.get('logging', {}).get('level', 'INFO')),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация компонентов
def init_database():
    """Инициализация ChromaDB"""
    db_config = CONFIG['database']
    client = chromadb.PersistentClient(path=db_config['path'])
    
    try:
        collection = client.get_collection(db_config['collection_name'])
        logger.info(f"Подключились к коллекции. Документов: {collection.count()}")
        return collection
    except Exception as e:
        logger.warning(f"Коллекция не найдена: {e}")
        logger.info("Создаем новую коллекцию...")
        try:
            collection = client.create_collection(db_config['collection_name'])
            logger.info("✅ Создана новая коллекция")
            return collection
        except Exception as create_error:
            logger.error(f"Ошибка создания коллекции: {create_error}")
            raise HTTPException(status_code=500, detail="Не удалось создать базу данных")

def init_embedder():
    """Инициализация модели эмбеддингов"""
    model_name = CONFIG['embeddings']['model']
    logger.info(f"Инициализируем модель эмбеддингов: {model_name}")
    return SentenceTransformer(model_name)

# Глобальные объекты
collection = init_database()
embedder = init_embedder()

# Инициализация Session Manager
session_config = CONFIG.get('session_memory', {})
session_manager = None
if session_config.get('enabled', True):
    session_manager = SessionManager(
        db_path=session_config.get('db_path', './session_storage.db'),
        max_messages=session_config.get('max_messages', 200)
    )
    logger.info("Session Manager initialized")
else:
    logger.info("Session Manager disabled")

# FastAPI приложение
app = FastAPI(
    title="RAG Assistant API",
    description="Универсальный RAG ассистент с поддержкой множественных фреймворков",
    version="2.0.0"
)

# CORS настройки
server_config = CONFIG.get('server', {})
cors_origins = server_config.get('cors_origins', ["*"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Модели данных
class QueryRequest(BaseModel):
    question: str = Field(..., description="Вопрос пользователя")
    framework: Optional[str] = Field(None, description="Фильтр по фреймворку")
    max_results: int = Field(5, ge=1, le=20, description="Максимум результатов")
    context: Optional[str] = Field(None, description="Дополнительный контекст")
    model: Optional[str] = Field(None, description="Модель LLM (qwen или deepseek)")
    # Новые поля для интеграции с системой памяти
    project_name: Optional[str] = Field(None, description="Имя проекта для сессии")
    project_path: Optional[str] = Field(None, description="Путь к проекту (для автоопределения)")
    session_id: Optional[str] = Field(None, description="ID существующей сессии")
    use_memory: bool = Field(True, description="Использовать контекст сессии")
    save_to_memory: bool = Field(True, description="Сохранять взаимодействие в память")

class IDEQueryRequest(BaseModel):
    question: str = Field(..., description="Вопрос от IDE")
    file_path: Optional[str] = Field(None, description="Путь к текущему файлу")
    file_content: Optional[str] = Field(None, description="Содержимое файла")
    cursor_position: Optional[Dict[str, int]] = Field(None, description="Позиция курсора")
    framework: Optional[str] = Field(None, description="Автоопределяемый фреймворк")
    quick_mode: bool = Field(True, description="Быстрый режим для автодополнения")
    # Новые поля для интеграции с системой памяти
    project_name: Optional[str] = Field(None, description="Имя проекта для сессии")
    project_path: Optional[str] = Field(None, description="Путь к проекту (для автоопределения)")
    session_id: Optional[str] = Field(None, description="ID существующей сессии")
    use_memory: bool = Field(True, description="Использовать контекст сессии")
    save_to_memory: bool = Field(True, description="Сохранять взаимодействие в память")

class QueryResponse(BaseModel):
    answer: str
    sources: List[Dict[str, str]]
    total_docs: int
    response_time: float
    framework_detected: Optional[str] = None
    # Новые поля для интеграции с системой памяти
    session_id: Optional[str] = None
    session_context_used: bool = False
    key_moments_detected: List[Dict[str, Any]] = []

# Кэш для быстрых ответов
cache = {}
cache_config = CONFIG.get('cache', {})

# Утилиты
def detect_framework_from_context(file_path: str = None, file_content: str = None) -> Optional[str]:
    """Автоопределение фреймворка по контексту файла"""
    if file_path:
        path_lower = file_path.lower()
        if any(x in path_lower for x in ['.vue', 'vue.js', 'vue.config']):
            return 'vue'
        elif any(x in path_lower for x in ['artisan', 'composer.json', 'laravel']):
            return 'laravel'
    
    if file_content:
        content_lower = file_content.lower()
        if any(x in content_lower for x in ['<template>', 'vue', 'composition api']):
            return 'vue'
        elif any(x in content_lower for x in ['eloquent', 'blade', 'artisan', 'laravel']):
            return 'laravel'
    
    return None

def get_cache_key(question: str, framework: str = None) -> str:
    """Генерация ключа кэша"""
    return f"{question}:{framework or 'all'}"

def extract_project_name(project_path: str) -> str:
    """Извлечь имя проекта из пути"""
    if not project_path:
        return "default"
    
    # Нормализуем путь и убираем trailing slash
    path = project_path.rstrip('/\\')
    
    # Извлекаем последнюю папку как имя проекта
    if '/' in path:
        project_name = path.split('/')[-1]
    elif '\\' in path:
        project_name = path.split('\\')[-1]
    else:
        project_name = path
    
    # Очищаем имя проекта от недопустимых символов
    import re
    project_name = re.sub(r'[^\w\-_.]', '_', project_name)
    
    return project_name or "default"

def get_or_create_session(project_name: str, session_id: str = None) -> str:
    """Получение существующей сессии или создание новой"""
    if not session_manager:
        logger.warning("Session Manager не инициализирован")
        return None
    
    try:
        if session_id:
            # Проверяем, что сессия существует
            session = session_manager.get_session(session_id)
            if session:
                logger.info(f"Используем существующую сессию: {session_id}")
                return session_id
        
        if project_name:
            # Пытаемся найти последнюю сессию проекта
            existing_session = session_manager.get_latest_session(project_name)
            if existing_session:
                logger.info(f"Найдена последняя сессия проекта {project_name}: {existing_session}")
                return existing_session
            
            # Создаем новую сессию
            new_session = session_manager.create_session(project_name)
            logger.info(f"Создана новая сессия для проекта {project_name}: {new_session}")
            return new_session
        
        # Создаем анонимную сессию
        anonymous_session = session_manager.create_session("anonymous")
        logger.info(f"Создана анонимная сессия: {anonymous_session}")
        return anonymous_session
    
    except Exception as e:
        logger.error(f"Ошибка при работе с сессией: {e}")
        return None

def build_context_with_memory(question: str, framework: str = None, 
                             session_id: str = None, base_context: str = None) -> Tuple[str, bool]:
    """Создание контекста с учетом памяти сессии"""
    if not session_id:
        return base_context or "", False
    
    # Получаем контекст сессии
    session_context = session_manager.get_session_context(session_id)
    if not session_context:
        return base_context or "", False
    
    # Строим расширенный контекст
    context_parts = []
    
    # Добавляем информацию о проекте
    context_parts.append(f"[Project Context: {session_context['project_name']}]")
    
    # Добавляем ключевые моменты
    if session_context['key_moments']:
        context_parts.append("[Key Moments from Session]")
        for moment in session_context['key_moments'][:5]:  # Топ 5 ключевых моментов
            context_parts.append(f"- {moment['title']}: {moment['summary']}")
    
    # Добавляем сжатую историю
    if session_context['compressed_history']:
        context_parts.append("[Previous Work Summary]")
        for period in session_context['compressed_history'][-2:]:  # Последние 2 периода
            context_parts.append(f"- {period['period']}: {period['summary']}")
    
    # Добавляем последние сообщения
    if session_context['recent_messages']:
        context_parts.append("[Recent Context]")
        recent_messages = session_context['recent_messages'][-5:]  # Последние 5 сообщений
        for msg in recent_messages:
            role = "User" if msg['role'] == 'user' else "Assistant"
            context_parts.append(f"{role}: {msg['content'][:150]}...")
    
    # Добавляем базовый контекст
    if base_context:
        context_parts.append(f"[Additional Context]\n{base_context}")
    
    return "\n\n".join(context_parts), True

def build_enhanced_prompt(base_prompt: str, session_context: dict = None) -> str:
    """Обогатить промпт контекстом сессии"""
    if not session_context:
        return base_prompt
    
    enhancement_parts = []
    
    # Добавляем информацию о проекте
    if session_context.get('project_name'):
        enhancement_parts.append(f"[Project: {session_context['project_name']}]")
    
    # Добавляем ключевые моменты из сессии
    if session_context.get('key_moments'):
        enhancement_parts.append("[Key Moments from Session]")
        for moment in session_context['key_moments'][:3]:  # Топ 3 момента
            enhancement_parts.append(f"- {moment['title']}: {moment['summary']}")
    
    # Добавляем краткую историю
    if session_context.get('compressed_history'):
        enhancement_parts.append("[Previous Work Summary]")
        for period in session_context['compressed_history'][-1:]:  # Последний период
            enhancement_parts.append(f"- {period['summary']}")
    
    # Добавляем недавний контекст
    if session_context.get('recent_messages'):
        enhancement_parts.append("[Recent Context]")
        recent_messages = session_context['recent_messages'][-3:]  # Последние 3 сообщения
        for msg in recent_messages:
            role = "User" if msg['role'] == 'user' else "Assistant"
            enhancement_parts.append(f"{role}: {msg['content'][:100]}...")
    
    if enhancement_parts:
        enhanced_prompt = "\n\n".join(enhancement_parts) + "\n\n" + base_prompt
    else:
        enhanced_prompt = base_prompt
    
    return enhanced_prompt

def save_interaction_to_session(session_id: str, question: str, answer: str, 
                               framework: str = None, files: List[str] = None,
                               actions: List[str] = None):
    """Сохранить взаимодействие в сессию с автообнаружением ключевых моментов"""
    if not session_manager or not session_id:
        return
    
    try:
        # Сохраняем сообщение пользователя
        session_manager.add_message(
            session_id,
            "user",
            question,
            actions=actions or ["ask_question"],
            files=files or [],
            metadata={"framework": framework}
        )
        
        # Сохраняем ответ ассистента
        session_manager.add_message(
            session_id,
            "assistant", 
            answer,
            actions=actions or ["provide_answer"],
            files=files or [],
            metadata={"framework": framework}
        )
        
        # Автоматическое обнаружение ключевых моментов
        session_config = CONFIG.get('session_memory', {})
        if session_config.get('auto_detect_moments', True):
            detected_moments = auto_detect_key_moments(answer, actions or ["provide_answer"], files or [])
            
            for moment_type, title, summary in detected_moments:
                session_manager.add_key_moment(
                    session_id,
                    moment_type,
                    title,
                    summary,
                    files=files or [],
                    context=question
                )
                logger.info(f"Автоматически обнаружен ключевой момент: {title}")
        
        logger.info(f"Взаимодействие сохранено в сессию {session_id}")
        
    except Exception as e:
        logger.error(f"Ошибка при сохранении взаимодействия: {e}")

def get_cached_response(cache_key: str) -> Optional[Dict]:
    """Получение ответа из кэша"""
    if not cache_config.get('enabled', True):
        return None
    
    if cache_key in cache:
        cached_data = cache[cache_key]
        # Проверяем TTL
        if time.time() - cached_data['timestamp'] < cache_config.get('ttl', 3600):
            return cached_data['data']
        else:
            del cache[cache_key]
    
    return None

def set_cached_response(cache_key: str, response: Dict):
    """Сохранение ответа в кэш"""
    if not cache_config.get('enabled', True):
        return
    
    # Ограничиваем размер кэша
    max_size = cache_config.get('max_size', 1000)
    if len(cache) >= max_size:
        # Удаляем самые старые записи
        oldest_key = min(cache.keys(), key=lambda k: cache[k]['timestamp'])
        del cache[oldest_key]
    
    cache[cache_key] = {
        'data': response,
        'timestamp': time.time()
    }

async def query_llm(prompt: str, model_name: str = None, quick_mode: bool = False) -> str:
    """Запрос к LLM"""
    llm_config = CONFIG['llm']
    
    # Выбор модели
    model_key = model_name or llm_config.get('default_model', 'qwen')
    if model_key not in llm_config['models']:
        model_key = llm_config['default_model']
    
    model_config = llm_config['models'][model_key]
    
    # Формирование запроса в зависимости от типа модели
    if model_key == 'qwen':  # LM Studio API
        payload = {
            "model": model_config['model_name'],
            "prompt": prompt,
            "max_tokens": 200 if quick_mode else model_config['max_tokens'],
            "temperature": model_config['temperature']
        }
        
        try:
            response = requests.post(
                model_config['api_url'], 
                json=payload,
                timeout=CONFIG.get('ide', {}).get('quick_response_timeout', 2.0) if quick_mode else 60
            )
            
            if response.status_code != 200:
                raise Exception(f"LLM API error: {response.status_code}")
            
            return response.json()["choices"][0]["text"].strip()
        
        except requests.exceptions.Timeout:
            if quick_mode:
                return "Быстрый ответ недоступен. Попробуйте без quick_mode."
            raise
        except Exception as e:
            logger.error(f"Ошибка запроса к LLM: {e}")
            raise HTTPException(status_code=500, detail=f"LLM сервис {model_key} недоступен")
    
    elif model_key == 'deepseek':  # Ollama API
        payload = {
            "model": model_config['model_name'],
            "prompt": prompt,
            "max_tokens": 200 if quick_mode else model_config['max_tokens'],
            "temperature": model_config['temperature'],
            "stream": False
        }
        
        try:
            response = requests.post(
                model_config['api_url'], 
                json=payload,
                timeout=CONFIG.get('ide', {}).get('quick_response_timeout', 2.0) if quick_mode else 60
            )
            
            if response.status_code != 200:
                raise Exception(f"Ollama API error: {response.status_code}")
            
            return response.json()["response"].strip()
        
        except requests.exceptions.Timeout:
            if quick_mode:
                return "Быстрый ответ недоступен. Попробуйте без quick_mode."
            raise
        except Exception as e:
            logger.error(f"Ошибка запроса к Ollama: {e}")
            raise HTTPException(status_code=500, detail=f"Ollama сервис {model_key} недоступен")
    
    else:
        raise HTTPException(status_code=400, detail=f"Неизвестная модель: {model_key}")

# API endpoints
@app.get("/")
async def root():
    """Главная страница API"""
    frameworks = {name: config['name'] for name, config in CONFIG['frameworks'].items() 
                 if config.get('enabled', True)}
    
    return {
        "message": "🚀 RAG Assistant API v2.0 with Smart Memory",
        "description": "Универсальный RAG ассистент с поддержкой IDE и системой памяти",
        "frameworks": frameworks,
        "total_docs": collection.count(),
        "features": [
            "🧠 Smart Session Memory with sliding window",
            "🔑 Key Moments detection and tracking",
            "📊 Compressed history for long sessions",
            "🔄 Automatic framework detection",
            "⚡ Caching and performance optimization"
        ],
        "endpoints": {
            "/ask": "POST - Обычный запрос с поддержкой памяти",
            "/ide/ask": "POST - Запрос от IDE с контекстом сессии",
            "/stats": "GET - Статистика документов",
            "/frameworks": "GET - Список фреймворков",
            "/sessions/create": "POST - Создать новую сессию",
            "/sessions/latest": "GET - Последняя сессия проекта",
            "/sessions/{session_id}": "GET - Информация о сессии",
            "/sessions/project/{project_name}": "GET - Сессии проекта",
            "/sessions/{session_id}/key-moment": "POST - Добавить ключевой момент",
            "/sessions/{session_id}/archive": "POST - Архивировать сессию",
            "/sessions/cleanup": "POST - Очистить старые сессии",
            "/sessions/stats": "GET - Статистика сессий",
            "/sessions/key-moment-types": "GET - Типы ключевых моментов"
        },
        "session_memory": {
            "enabled": session_manager is not None,
            "config": CONFIG.get('session_memory', {}) if session_manager else None
        }
    }

@app.get("/frameworks")
async def get_frameworks():
    """Список поддерживаемых фреймворков"""
    frameworks = {}
    for name, config in CONFIG['frameworks'].items():
        if config.get('enabled', True):
            frameworks[name] = {
                "name": config['name'],
                "description": config.get('description', ''),
                "type": config.get('type', 'markdown')
            }
    return frameworks

@app.get("/models")
async def get_models():
    """Список доступных моделей"""
    models = {}
    for name, config in CONFIG['llm']['models'].items():
        models[name] = {
            "name": config['model_name'],
            "max_tokens": config['max_tokens'],
            "temperature": config['temperature']
        }
    
    return {
        "models": models,
        "default": CONFIG['llm'].get('default_model', 'qwen')
    }

@app.get("/stats")
async def get_stats():
    """Статистика базы данных"""
    total_docs = collection.count()
    
    # Получаем ВСЕ документы для точной статистики
    if total_docs > 0:
        all_results = collection.get(limit=total_docs)
        
        # Подсчитываем по фреймворкам
        framework_counts = {}
        for metadata in all_results["metadatas"]:
            framework = metadata.get("framework", "unknown").upper()
            framework_counts[framework] = framework_counts.get(framework, 0) + 1
    else:
        framework_counts = {}
    
    return {
        "total_documents": total_docs,
        "frameworks": framework_counts,
        "cache_size": len(cache) if cache_config.get('enabled') else 0
    }

@app.post("/ask", response_model=QueryResponse)
async def ask_question(data: QueryRequest):
    """Основной endpoint для вопросов"""
    start_time = time.time()
    
    # 1. Определить проект и сессию
    project_name = data.project_name
    if not project_name and data.project_path:
        project_name = extract_project_name(data.project_path)
    
    current_session_id = None
    session_context_used = False
    session_context = None
    
    if data.use_memory and session_manager:
        current_session_id = get_or_create_session(project_name, data.session_id)
        
        # 2. Получить контекст сессии
        if current_session_id:
            try:
                session_context = session_manager.get_session_context(current_session_id)
                session_context_used = True
                logger.info(f"Получен контекст сессии {current_session_id}")
            except Exception as e:
                logger.error(f"Ошибка получения контекста сессии: {e}")
    
    # Проверяем кэш (учитываем сессию в ключе)
    cache_key = get_cache_key(data.question, data.framework)
    if current_session_id:
        cache_key += f":{current_session_id}"
    
    cached_response = get_cached_response(cache_key)
    if cached_response:
        cached_response['response_time'] = time.time() - start_time
        cached_response['session_id'] = current_session_id
        return QueryResponse(**cached_response)
    
    # Создаем эмбеддинг для поиска
    query_embedding = embedder.encode(data.question).tolist()
    
    # Фильтр по фреймворку
    where_filter = None
    if data.framework:
        where_filter = {"framework": data.framework.lower()}
    
    # Поиск релевантных документов
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=data.max_results,
        where=where_filter
    )
    
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    
    if not documents:
        raise HTTPException(status_code=404, detail="Релевантные документы не найдены")
    
    # Определяем основной фреймворк в результатах
    frameworks = [meta.get("framework", "unknown") for meta in metadatas]
    main_framework = max(set(frameworks), key=frameworks.count) if frameworks else "unknown"
    
    # Создаем контекст документации
    doc_context_parts = []
    for doc, meta in zip(documents, metadatas):
        framework = meta.get("framework", "unknown").upper()
        source = meta.get("source", "unknown")
        heading = meta.get("heading", "")
        doc_context_parts.append(f"[{framework}] {source} - {heading}\n{doc}")
    
    doc_context = "\n\n".join(doc_context_parts)
    
    # Адаптивный промпт
    framework_title = main_framework.title() if main_framework != "unknown" else "Web Development"
    
    # Создаем базовый промпт
    base_prompt_parts = [
        f"[{framework_title} Documentation Context]",
        doc_context,
        "[User Question]",
        data.question,
        "[Additional Context]",
        data.context or "Нет дополнительного контекста",
        "[Instructions]",
        "- Answer based on the provided documentation context",
        f"- If the question relates to {framework_title}, prioritize {framework_title}-specific information",
        "- Use session memory context to provide continuity and avoid repeating information",
        "- Provide practical, actionable advice with code examples when relevant",
        "- Be concise but comprehensive",
        "",
        "[Answer]"
    ]
    
    base_prompt = "\n\n".join(base_prompt_parts)
    
    # 3. Обогатить промпт контекстом сессии
    enhanced_prompt = build_enhanced_prompt(base_prompt, session_context)
    
    # Получаем ответ от LLM
    answer = await query_llm(enhanced_prompt, data.model)
    
    # 4. Сохранить диалог в сессию
    key_moments_detected = []
    if current_session_id and data.save_to_memory:
        try:
            # Извлекаем файлы из контекста если есть
            files_involved = []
            if data.context:
                # Простая эвристика для обнаружения файлов в контексте
                import re
                file_matches = re.findall(r'(\w+\.[a-zA-Z]{1,5})', data.context)
                files_involved.extend(file_matches)
            
            # Сохраняем взаимодействие
            save_interaction_to_session(
                current_session_id,
                data.question,
                answer,
                framework=main_framework,
                files=files_involved,
                actions=["ask_question", "provide_answer"]
            )
            
            # Получаем обнаруженные ключевые моменты
            detected_moments = auto_detect_key_moments(answer, ["provide_answer"], files_involved)
            for moment_type, title, summary in detected_moments:
                key_moments_detected.append({
                    "type": moment_type.value,
                    "title": title,
                    "summary": summary
                })
        except Exception as e:
            logger.error(f"Ошибка при сохранении в сессию: {e}")
    
    # Формируем ответ
    response_data = {
        "answer": answer,
        "sources": [
            {
                "framework": meta.get("framework", "unknown").upper(),
                "source": meta.get("source", "unknown"),
                "heading": meta.get("heading", "")
            }
            for meta in metadatas
        ],
        "total_docs": len(documents),
        "response_time": time.time() - start_time,
        "framework_detected": main_framework,
        "session_id": current_session_id,
        "session_context_used": session_context_used,
        "key_moments_detected": key_moments_detected
    }
    
    # Сохраняем в кэш
    set_cached_response(cache_key, response_data)
    
    return QueryResponse(**response_data)

@app.post("/ide/ask", response_model=QueryResponse)
async def ide_ask_question(data: IDEQueryRequest):
    """Специальный endpoint для IDE интеграции"""
    start_time = time.time()
    
    # Автоопределение фреймворка
    detected_framework = data.framework or detect_framework_from_context(
        data.file_path, data.file_content
    )
    
    # Формируем контекст для IDE
    ide_context = []
    if data.file_path:
        ide_context.append(f"Текущий файл: {data.file_path}")
    if data.cursor_position:
        ide_context.append(f"Позиция курсора: строка {data.cursor_position.get('line', 0)}")
    
    # Автоматическое определение имени проекта из пути файла
    project_name = data.project_name
    if not project_name and data.project_path:
        project_name = extract_project_name(data.project_path)
    elif not project_name and data.file_path:
        # Извлекаем имя проекта из пути файла
        project_name = extract_project_name(data.file_path)
    
    # Создаем запрос
    query_request = QueryRequest(
        question=data.question,
        framework=detected_framework,
        max_results=3 if data.quick_mode else 5,
        context="\n".join(ide_context) if ide_context else None,
        project_name=project_name,
        project_path=data.project_path,
        session_id=data.session_id,
        use_memory=data.use_memory,
        save_to_memory=data.save_to_memory
    )
    
    # Используем основную логику
    response = await ask_question(query_request)
    
    # response уже является объектом QueryResponse
    # Просто обновляем framework_detected если нужно
    if detected_framework:
        response.framework_detected = detected_framework
    
    return response

@app.delete("/cache")
async def clear_cache():
    """Очистка кэша"""
    cache.clear()
    return {"message": "Кэш очищен", "timestamp": time.time()}

# Новые endpoints для управления сессиями
@app.post("/sessions/create")
async def create_session(project_name: str):
    """Создание новой сессии"""
    if not session_manager:
        raise HTTPException(status_code=503, detail="Session Manager не инициализирован")
    
    try:
        session_id = session_manager.create_session(project_name)
        logger.info(f"Создана новая сессия {session_id} для проекта {project_name}")
        return {"session_id": session_id, "project_name": project_name}
    except Exception as e:
        logger.error(f"Ошибка создания сессии: {e}")
        raise HTTPException(status_code=500, detail="Ошибка создания сессии")

@app.get("/sessions/latest")
async def get_latest_session(project_name: str):
    """Получение последней сессии проекта"""
    if not session_manager:
        raise HTTPException(status_code=503, detail="Session Manager не инициализирован")
    
    try:
        session_id = session_manager.get_latest_session(project_name)
        if not session_id:
            raise HTTPException(status_code=404, detail="Сессия не найдена")
        
        session_context = session_manager.get_session_context(session_id)
        return {"session_id": session_id, "project_name": project_name, "context": session_context}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения последней сессии: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения сессии")

@app.get("/sessions/{session_id}")
async def get_session_info(session_id: str):
    """Получение информации о сессии"""
    if not session_manager:
        raise HTTPException(status_code=503, detail="Session Manager не инициализирован")
    
    try:
        session_context = session_manager.get_session_context(session_id)
        if not session_context:
            raise HTTPException(status_code=404, detail="Сессия не найдена")
        return session_context
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения информации о сессии: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения информации о сессии")

@app.get("/sessions/project/{project_name}")
async def get_project_sessions(project_name: str):
    """Получение всех сессий проекта"""
    if not session_manager:
        raise HTTPException(status_code=503, detail="Session Manager не инициализирован")
    
    try:
        sessions = session_manager.get_project_sessions(project_name)
        return {"project_name": project_name, "sessions": sessions}
    except Exception as e:
        logger.error(f"Ошибка получения сессий проекта: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения сессий проекта")

@app.post("/sessions/{session_id}/key-moment")
async def add_key_moment(session_id: str, request: Request):
    """Добавление ключевого момента в сессию"""
    if not session_manager:
        raise HTTPException(status_code=503, detail="Session Manager не инициализирован")
    
    try:
        data = await request.json()
        moment_type = data.get("moment_type")
        title = data.get("title")
        summary = data.get("summary")
        importance = data.get("importance")
        files = data.get("files", [])
        context = data.get("context", "")
        
        if not moment_type or not title or not summary:
            raise HTTPException(status_code=400, detail="Обязательные поля: moment_type, title, summary")
        
        moment_type_enum = KeyMomentType(moment_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Неизвестный тип момента: {moment_type}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка обработки данных: {e}")
    
    try:
        success = session_manager.add_key_moment(
            session_id, moment_type_enum, title, summary, 
            importance, files or [], context
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Сессия не найдена")
        
        logger.info(f"Добавлен ключевой момент в сессию {session_id}: {title}")
        return {"message": "Ключевой момент добавлен", "session_id": session_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка добавления ключевого момента: {e}")
        raise HTTPException(status_code=500, detail="Ошибка добавления ключевого момента")

@app.post("/sessions/{session_id}/archive")
async def archive_session(session_id: str):
    """Архивирование сессии"""
    if not session_manager:
        raise HTTPException(status_code=503, detail="Session Manager не инициализирован")
    
    try:
        success = session_manager.archive_session(session_id)
        if not success:
            raise HTTPException(status_code=404, detail="Сессия не найдена")
        
        logger.info(f"Сессия {session_id} заархивирована")
        return {"message": "Сессия заархивирована", "session_id": session_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка архивирования сессии: {e}")
        raise HTTPException(status_code=500, detail="Ошибка архивирования сессии")

@app.post("/sessions/cleanup")
async def cleanup_sessions(days_threshold: int = 30):
    """Очистка старых сессий"""
    if not session_manager:
        raise HTTPException(status_code=503, detail="Session Manager не инициализирован")
    
    try:
        archived_count, deleted_count = session_manager.cleanup_old_sessions(days_threshold)
        logger.info(f"Очистка сессий завершена: {archived_count} архивированных, {deleted_count} удаленных")
        return {
            "message": "Очистка завершена",
            "archived_sessions": archived_count,
            "deleted_sessions": deleted_count
        }
    except Exception as e:
        logger.error(f"Ошибка очистки сессий: {e}")
        raise HTTPException(status_code=500, detail="Ошибка очистки сессий")

@app.get("/sessions/stats")
async def get_session_stats():
    """Статистика системы сессий"""
    if not session_manager:
        raise HTTPException(status_code=503, detail="Session Manager не инициализирован")
    
    try:
        stats = session_manager.get_stats()
        return stats
    except Exception as e:
        logger.error(f"Ошибка получения статистики сессий: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения статистики сессий")

@app.get("/sessions/key-moment-types")
async def get_key_moment_types():
    """Получение доступных типов ключевых моментов"""
    return {
        "types": [
            {
                "type": moment_type.value,
                "importance": importance,
                "description": moment_type.value.replace("_", " ").title()
            }
            for moment_type, importance in MOMENT_IMPORTANCE.items()
        ]
    }

# Запуск сервера
if __name__ == "__main__":
    import uvicorn
    
    server_config = CONFIG.get('server', {})
    host = server_config.get('host', '0.0.0.0')
    port = server_config.get('port', 8000)
    
    print(f"🚀 Запуск RAG сервера на {host}:{port}")
    print(f"📚 Документов в базе: {collection.count()}")
    
    uvicorn.run(app, host=host, port=port)
