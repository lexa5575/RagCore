#!/usr/bin/env python3
"""
Улучшенный RAG сервер с поддержкой IDE интеграции
Использует конфигурационный файл и универсальный подход
"""

import yaml
import time
import logging
from typing import Optional, List, Dict, Any
from pathlib import Path

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import chromadb
from sentence_transformers import SentenceTransformer
import requests

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

class IDEQueryRequest(BaseModel):
    question: str = Field(..., description="Вопрос от IDE")
    file_path: Optional[str] = Field(None, description="Путь к текущему файлу")
    file_content: Optional[str] = Field(None, description="Содержимое файла")
    cursor_position: Optional[Dict[str, int]] = Field(None, description="Позиция курсора")
    framework: Optional[str] = Field(None, description="Автоопределяемый фреймворк")
    quick_mode: bool = Field(True, description="Быстрый режим для автодополнения")

class QueryResponse(BaseModel):
    answer: str
    sources: List[Dict[str, str]]
    total_docs: int
    response_time: float
    framework_detected: Optional[str] = None

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
        "message": "🚀 RAG Assistant API v2.0",
        "description": "Универсальный RAG ассистент с поддержкой IDE",
        "frameworks": frameworks,
        "total_docs": collection.count(),
        "endpoints": {
            "/ask": "POST - Обычный запрос",
            "/ide/ask": "POST - Запрос от IDE",
            "/stats": "GET - Статистика",
            "/frameworks": "GET - Список фреймворков"
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
    
    # Проверяем кэш
    cache_key = get_cache_key(data.question, data.framework)
    cached_response = get_cached_response(cache_key)
    if cached_response:
        cached_response['response_time'] = time.time() - start_time
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
    
    # Создаем контекст
    context_parts = []
    for doc, meta in zip(documents, metadatas):
        framework = meta.get("framework", "unknown").upper()
        source = meta.get("source", "unknown")
        heading = meta.get("heading", "")
        context_parts.append(f"[{framework}] {source} - {heading}\n{doc}")
    
    context = "\n\n".join(context_parts)
    
    # Адаптивный промпт
    framework_title = main_framework.title() if main_framework != "unknown" else "Web Development"
    
    prompt = f"""[{framework_title} Documentation Context]
{context}

[User Question]
{data.question}

[Additional Context]
{data.context or "Нет дополнительного контекста"}

[Instructions]
- Answer based on the provided documentation context
- If the question relates to {framework_title}, prioritize {framework_title}-specific information
- Provide practical, actionable advice with code examples when relevant
- Be concise but comprehensive

[Answer]"""
    
    # Получаем ответ от LLM
    answer = await query_llm(prompt, data.model)
    
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
        "framework_detected": main_framework
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
    
    # Создаем запрос
    query_request = QueryRequest(
        question=data.question,
        framework=detected_framework,
        max_results=3 if data.quick_mode else 5,
        context="\n".join(ide_context) if ide_context else None
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

# Запуск сервера
if __name__ == "__main__":
    import uvicorn
    
    server_config = CONFIG.get('server', {})
    host = server_config.get('host', '0.0.0.0')
    port = server_config.get('port', 8000)
    
    print(f"🚀 Запуск RAG сервера на {host}:{port}")
    print(f"📚 Документов в базе: {collection.count()}")
    
    uvicorn.run(app, host=host, port=port)
