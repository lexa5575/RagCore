import time
import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Request
from models.api_models import QueryRequest, QueryResponse

logger = logging.getLogger(__name__)


def is_meta_question(question: str) -> bool:
    question_lower = question.lower()
    meta_words = [
        'что делали', 'прогресс', 'статус', 'история', 'покажи', 'сводка', 'резюме',
        'что это за проект', 'какой проект', 'опиши проект', 'о проекте', 
        'что за', 'проект', 'контекст', 'что происходит'
    ]
    return any(word in question_lower for word in meta_words)

def create_rag_router(rag_service, config: Dict[str, Any]) -> APIRouter:
    router = APIRouter()
    
    @router.post("/ask", response_model=QueryResponse, summary="Задать вопрос RAG системе")
    async def ask_question(data: QueryRequest, request: Request):
        start_time = time.time()
        
        try:
            project_name = data.project_name
            if not project_name and data.project_path:
                project_name = rag_service.project_service.extract_project_name(data.project_path)
            
            current_session_id = None
            session_context_used = False
            
            if data.use_memory and rag_service.session_manager:
                current_session_id = rag_service.get_or_create_session(project_name, data.session_id)
            
            cache_key = rag_service.cache_service.get_cache_key(data.question, data.framework)
            if current_session_id:
                cache_key += f":{current_session_id}"
            
            cached_response = rag_service.cache_service.get_cached_response(cache_key)
            if cached_response:
                cached_response['response_time'] = time.time() - start_time
                cached_response['session_id'] = current_session_id
                return QueryResponse(**cached_response)
            
            is_meta = is_meta_question(data.question)
            
            detected_framework = data.framework
            if not detected_framework:
                detected_framework = rag_service.framework_detector.detect_framework_from_context(
                    data.project_path, data.context
                )
            
            if is_meta:
                if not rag_service.session_manager:
                    raise HTTPException(status_code=503, detail="Session Manager недоступен для мета-вопросов")
                
                logger.info("🧠 Обрабатываем мета-вопрос через Session Manager...")
                
                memory_context = rag_service.get_memory_bank_context(session_id=current_session_id)
                if not memory_context:
                    raise HTTPException(status_code=404, detail="Контекст проекта не найден")
                
                enhanced_context = memory_context
                session_context_used = True
                documents = []
                
                logger.info("✅ Контекст из Memory Bank получен")
                
            else:
                logger.info(f"🎯 RAG QUERY: Processing technical question with framework: {detected_framework or 'auto-detect'}")
                
                documents = rag_service.query_documents(
                    data.question, 
                    detected_framework, 
                    data.max_results
                )
                
                if not documents:
                    logger.warning("❌ NO DOCUMENTS: No relevant documents found in ChromaDB")
                    raise HTTPException(status_code=404, detail="Релевантные документы не найдены")
                
                logger.info(f"📝 CONTEXT BUILDING: Creating context from {len(documents)} ChromaDB documents")
                enhanced_context = "\n\n".join([doc['content'] for doc in documents])
                if data.context:
                    enhanced_context += f"\n\nДополнительный контекст:\n{data.context}"
                    logger.info("➕ CONTEXT: Added additional user context")
                
                context_length = len(enhanced_context)
                logger.info(f"📊 CONTEXT READY: Total context length: {context_length} characters")
                
                session_context_used = False
            
            logger.info("🤖 LLM PROCESSING: Generating response with local LLM model...")
            answer = rag_service.generate_llm_response(
                data.question, 
                enhanced_context, 
                detected_framework
            )
            logger.info(f"✅ LLM COMPLETE: Generated response ({len(answer)} characters)")
            
            logger.info("📋 SOURCES: Preparing source attribution...")
            sources = []
            if documents:
                for doc in documents:
                    source_file = doc['metadata'].get('source_file', 'Document')
                    framework = doc['metadata'].get('framework', 'unknown')
                    relevance = doc['relevance_score']
                    
                    logger.info(f"📄 SOURCE: {source_file} ({framework}) - relevance: {relevance:.3f}")
                    
                    sources.append({
                        "title": doc['metadata'].get('title', 'Document'),
                        "content": doc['content'][:200] + "..." if len(doc['content']) > 200 else doc['content'],
                        "framework": framework,
                        "relevance_score": relevance
                    })
            else:
                logger.info("💾 SOURCE: Using Memory Bank context")
                sources.append({
                    "title": "Memory Bank Context",
                    "content": "Контекст проекта из Memory Bank",
                    "framework": "memory_bank",
                    "relevance_score": 1.0
                })
            
            response_time = time.time() - start_time
            logger.info(f"🎉 REQUEST COMPLETE: Total response time: {response_time:.3f}s")
            
            response_data = {
                "answer": answer,
                "sources": sources,
                "total_docs": len(documents) if documents else 0,
                "response_time": response_time,
                "framework_detected": detected_framework,
                "session_id": current_session_id,
                "session_context_used": session_context_used,
                "key_moments_detected": []
            }
            
            rag_service.cache_service.set_cached_response(cache_key, response_data)
            
            if data.save_to_memory and current_session_id and is_meta:
                rag_service.save_interaction_to_session(
                    current_session_id, 
                    data.question, 
                    answer,
                    detected_framework,
                    actions=["ask_question"]
                )
            
            return QueryResponse(**response_data)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Ошибка в ask_question: {e}")
            raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")
    
    @router.get("/frameworks", summary="Получить список поддерживаемых фреймворков")
    async def get_frameworks():
        try:
            frameworks = {}
            
            # Получаем все документы из базы данных для подсчета
            all_results = rag_service.collection.get(include=['metadatas'])
            
            # Подсчитываем документы по фреймворкам
            framework_counts = {}
            if all_results and all_results['metadatas']:
                for metadata in all_results['metadatas']:
                    framework = metadata.get('framework', 'unknown')
                    framework_counts[framework] = framework_counts.get(framework, 0) + 1
            
            # Показываем только фреймворки с документами в базе данных
            for name, framework_config in config['frameworks'].items():
                if framework_config.get('enabled', True):
                    docs_count = framework_counts.get(name, 0)
                    
                    # КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: показываем только фреймворки с документами
                    if docs_count > 0:
                        frameworks[name] = {
                            "name": framework_config['name'],
                            "description": framework_config.get('description', ''),
                            "type": framework_config.get('type', 'markdown'),
                            "docs_count": docs_count
                        }
                        logger.info(f"📦 Framework {name}: {docs_count} документов")
                    else:
                        logger.info(f"🚫 Framework {name}: нет документов в базе данных - скрыт")
            
            logger.info(f"✅ Возвращаем {len(frameworks)} фреймворков с документами")
            return frameworks
        except Exception as e:
            logger.error(f"Ошибка получения фреймворков: {e}")
            raise HTTPException(status_code=500, detail="Ошибка получения списка фреймворков")
    
    @router.get("/stats", summary="Получить статистику RAG системы")
    async def get_stats():
        try:
            total_docs = rag_service.collection.count()
            
            # Оптимизация: получаем статистику одним запросом
            framework_stats = {}
            try:
                all_results = rag_service.collection.get(include=['metadatas'])
                
                # Подсчитываем документы по фреймворкам
                for framework_name in config['frameworks'].keys():
                    framework_stats[framework_name] = 0
                
                if all_results and all_results['metadatas']:
                    for metadata in all_results['metadatas']:
                        framework = metadata.get('framework', 'unknown')
                        if framework in framework_stats:
                            framework_stats[framework] += 1
                            
            except Exception as e:
                logger.warning(f"Ошибка получения статистики фреймворков: {e}")
                # Fallback к старому методу
                for framework_name in config['frameworks'].keys():
                    framework_stats[framework_name] = 0
            
            return {
                "total_documents": total_docs,
                "framework_statistics": framework_stats,
                "cache_statistics": rag_service.cache_service.cache_stats,
                "session_statistics": rag_service.session_manager.get_stats() if rag_service.session_manager else None
            }
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            raise HTTPException(status_code=500, detail="Ошибка получения статистики")
    
    @router.delete("/cache")
    async def clear_cache():
        try:
            rag_service.cache_service.clear_cache()
            return {"message": "Кэш очищен", "status": "success"}
        except Exception as e:
            logger.error(f"Ошибка очистки кэша: {e}")
            raise HTTPException(status_code=500, detail="Ошибка очистки кэша")
    
    return router
