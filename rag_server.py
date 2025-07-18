#!/usr/bin/env python3

import json
import logging
import yaml
import os
from typing import Dict, Any
import chromadb
from sentence_transformers import SentenceTransformer
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from services.rag_service import RAGService
from api.rag_endpoints import create_rag_router

def load_config():
    """Загружает конфигурацию с поддержкой локальных настроек"""
    # Загружаем основную конфигурацию
    with open("config.yaml", 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # Если есть локальная конфигурация - мержим её
    if os.path.exists("config.local.yaml"):
        with open("config.local.yaml", 'r', encoding='utf-8') as f:
            local_config = yaml.safe_load(f)
            # Глубокое слияние конфигураций
            config = merge_configs(config, local_config)
            print("✅ Local LLM configuration loaded from config.local.yaml")
    else:
        print("ℹ️  Using default LLM configuration. Create config.local.yaml for personal settings.")
    
    return config

def merge_configs(base_config, local_config):
    """Глубокое слияние конфигураций"""
    import copy
    result = copy.deepcopy(base_config)
    
    def deep_merge(base, local):
        for key, value in local.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                deep_merge(base[key], value)
            else:
                base[key] = value
    
    deep_merge(result, local_config)
    return result

def init_system():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    
    config = load_config()
    
    os.environ['ANONYMIZED_TELEMETRY'] = 'False'
    db_config = config['database']
    client = chromadb.PersistentClient(path=db_config['path'])
    
    try:
        collection = client.get_collection(db_config['collection_name'])
        logger.info("✅ Connected to collection")
    except:
        collection = client.create_collection(db_config['collection_name'])
        logger.info("✅ Created new collection")
    
    class LazyEmbedder:
        def __init__(self, model_name):
            self.model_name = model_name
            self._model = None
        def encode(self, texts, **kwargs):
            if self._model is None:
                logger.info(f"Loading model: {self.model_name}")
                self._model = SentenceTransformer(self.model_name)
            return self._model.encode(texts, **kwargs)
    
    embedder = LazyEmbedder(config['embeddings']['model'])
    return config, collection, embedder, logger

config, collection, embedder, logger = init_system()

app = FastAPI(
    title="🚀 RAG Assistant API v2.0",
    description="RAG ассистент с модульной архитектурой",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

@app.exception_handler(json.JSONDecodeError)
async def json_decode_error_handler(request: Request, exc: json.JSONDecodeError):
    return JSONResponse(status_code=400, content={"detail": "Неверный JSON формат"})

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={"detail": f"Ошибка значения: {str(exc)}"})

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

rag_service = RAGService(config, collection, embedder, None)

@app.get("/")
async def root():
    return {
        "message": "🚀 RAG Assistant API v2.0",
        "status": "ready",
        "endpoints": {
            "/ask": "POST - Main RAG query",
            "/frameworks": "GET - List frameworks",
            "/health": "GET - Health check"
        },
        "docs": "/docs",
        "database": "ChromaDB - Framework docs"
    }

app.include_router(create_rag_router(rag_service, config), tags=["RAG Queries"])

@app.get("/health")
async def health_check():
    try:
        return {
            "status": "healthy",
            "components": {
                "database": "healthy" if collection else "unhealthy",
                "embedder": "healthy" if embedder else "unhealthy",
                "documents": collection.count() if collection else 0
            }
        }
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return {"status": "unhealthy", "error": str(e)}

@app.get("/api-info")
async def get_api_info():
    return {
        "api_name": "RAG Assistant API",
        "version": "2.0.0",
        "description": "RAG system for framework documentation",
        "base_url": "http://localhost:8000",
        "supported_frameworks": ["laravel", "vue", "filament", "alpine", "inertia", "tailwindcss"],
        "main_endpoints": {
            "ask": "POST /ask",
            "frameworks": "GET /frameworks",
            "sessions": "/sessions/*",
            "memory_bank": "/memory-bank/*"
        },
        "documentation": "/docs"
    }

@app.get("/models")
async def get_models():
    """Получить список доступных LLM моделей"""
    try:
        llm_config = config.get('llm', {})
        models_info = llm_config.get('models', {})
        default_model = llm_config.get('default_model', 'qwen')
        
        # Форматируем информацию о моделях для MCP
        formatted_models = {}
        for model_key, model_config in models_info.items():
            formatted_models[model_key] = {
                "name": model_config.get('model_name', model_key),
                "api_url": model_config.get('api_url', ''),
                "max_tokens": model_config.get('max_tokens', 800),
                "temperature": model_config.get('temperature', 0.2),
                "description": f"LLM model: {model_config.get('model_name', model_key)}"
            }
        
        return {
            "models": formatted_models,
            "default": default_model,
            "total_models": len(formatted_models)
        }
    except Exception as e:
        logger.error(f"Error getting models: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving models: {str(e)}")

@app.get("/function-schema")
async def get_function_schema():
    return {
        "functions": [
            {
                "name": "ask_rag_question",
                "description": "Ask RAG system a question about framework documentation",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string", "description": "User question"},
                        "framework": {"type": "string", "enum": ["laravel", "vue", "filament", "alpine", "inertia", "tailwindcss"]},
                        "max_results": {"type": "integer", "default": 5}
                    },
                    "required": ["question"]
                }
            },
            {
                "name": "get_supported_frameworks",
                "description": "Get list of supported frameworks",
                "parameters": {"type": "object", "properties": {}}
            }
        ]
    }

if __name__ == "__main__":
    import uvicorn
    
    logger.info("🚀 Starting RAG server...")
    logger.info(f"📊 Collection ready: {collection is not None}")
    logger.info(f"🧠 RAG Service: {'enabled' if rag_service else 'disabled'}")
    logger.info(f"🔧 Documents count: {collection.count() if collection else 0}")
    
    uvicorn.run(
        "rag_server:app",
        host="0.0.0.0",
        port=8000,
        reload=False,  # Отключаем file watching - используем только наш File Watcher V2
        log_level="info"
    )
