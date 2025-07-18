#!/usr/bin/env python3
"""
Улучшенный RAG сервис с интеграцией всех оптимизаций
Включает гибридный поиск, кэширование embeddings и улучшенное определение фреймворков
"""

import time
import logging
import re
from typing import Dict, List, Optional, Tuple, Any
import requests
import json
import numpy as np

from .rag_service import RAGService, CacheService, ProjectService, FrameworkDetector as BaseFrameworkDetector
from .embedding_cache import EmbeddingCache
from .hybrid_retriever import HybridRetriever
from .framework_detector import FrameworkDetector as EnhancedFrameworkDetector
from models.api_models import QueryRequest, QueryResponse
from utils.key_moment_detector import auto_detect_key_moments
from services.llm import clean_llm_response

logger = logging.getLogger(__name__)

class EnhancedRAGService(RAGService):
    """
    Улучшенный RAG сервис с дополнительными возможностями:
    - Гибридный поиск (семантический + лексический)
    - Кэширование embeddings для ускорения
    - Улучшенное автоопределение фреймворков
    - Оптимизированная генерация ответов
    """
    
    def __init__(self, config: Dict[str, Any], collection, embedder, session_manager):
        super().__init__(config, collection, embedder, session_manager)
        
        # Инициализируем новые компоненты
        self.embedding_cache = EmbeddingCache(
            cache_dir="./embedding_cache",
            max_size=config.get('cache', {}).get('embedding_cache_size', 10000)
        )
        
        self.hybrid_retriever = HybridRetriever(
            embedder=embedder,
            collection=collection,
            config=config
        )
        
        self.enhanced_framework_detector = EnhancedFrameworkDetector()
        
        # Статистика производительности
        self.performance_stats = {
            'total_queries': 0,
            'cache_hits': 0,
            'hybrid_searches': 0,
            'framework_detections': 0,
            'avg_response_time': 0.0
        }
        
        logger.info("✅ Enhanced RAG Service инициализирован с улучшениями")
    
    def _create_embedding_with_cache(self, text: str) -> np.ndarray:
        """Создает embedding с использованием кэша"""
        # Проверяем кэш
        cached_embedding = self.embedding_cache.get_embedding(text)
        if cached_embedding is not None:
            return cached_embedding
        
        # Создаем новый embedding
        embedding = self.embedder.encode([text])[0]
        
        # Сохраняем в кэш
        self.embedding_cache.set_embedding(text, embedding)
        
        return embedding
    
    def query_documents_enhanced(self, question: str, framework: str = None, 
                                max_results: int = 5, use_hybrid: bool = True) -> List[Dict]:
        """
        Улучшенный поиск документов с гибридным подходом
        """
        try:
            start_time = time.time()
            
            logger.info(f"🔍 ENHANCED QUERY: '{question}' (framework: {framework}, hybrid: {use_hybrid})")
            
            if use_hybrid:
                # Используем гибридный поиск
                documents = self.hybrid_retriever.search(
                    query=question,
                    framework=framework,
                    max_results=max_results,
                    alpha=0.7  # 70% семантический, 30% лексический
                )
                self.performance_stats['hybrid_searches'] += 1
                logger.info(f"🎯 HYBRID SEARCH: Found {len(documents)} documents")
            else:
                # Используем стандартный семантический поиск с кэшированием
                query_embedding = self._create_embedding_with_cache(question)
                
                where_filter = {}
                if framework:
                    where_filter = {"framework": framework}
                
                results = self.collection.query(
                    query_embeddings=[query_embedding.tolist()],
                    n_results=max_results,
                    where=where_filter if where_filter else None
                )
                
                documents = []
                if results['documents'][0]:
                    for i, (doc, metadata, distance) in enumerate(zip(
                        results['documents'][0], 
                        results['metadatas'][0], 
                        results['distances'][0]
                    )):
                        documents.append({
                            'content': doc,
                            'metadata': metadata,
                            'relevance_score': 1 - distance,
                            'rank': i + 1,
                            'source': 'semantic'
                        })
                
                logger.info(f"📊 SEMANTIC SEARCH: Found {len(documents)} documents")
            
            search_time = time.time() - start_time
            logger.info(f"⏱️ SEARCH TIME: {search_time:.3f}s")
            
            return documents
            
        except Exception as e:
            logger.error(f"❌ ENHANCED QUERY ERROR: {e}")
            return []
    
    def detect_framework_enhanced(self, question: str, context: str = None, 
                                 project_path: str = None) -> Tuple[Optional[str], float]:
        """
        Улучшенное определение фреймворка с оценкой уверенности
        """
        try:
            # Используем комплексное определение
            detected_framework = self.enhanced_framework_detector.detect_framework_comprehensive(
                question=question,
                file_path=project_path,
                file_content=None,
                context=context
            )
            
            # Получаем уверенность
            confidence = 0.0
            if detected_framework:
                confidence = self.enhanced_framework_detector.get_framework_confidence(
                    question, detected_framework
                )
                self.performance_stats['framework_detections'] += 1
                logger.info(f"🎯 FRAMEWORK: {detected_framework} (confidence: {confidence:.2f})")
            
            return detected_framework, confidence
            
        except Exception as e:
            logger.error(f"❌ FRAMEWORK DETECTION ERROR: {e}")
            return None, 0.0
    
    def _optimize_llm_parameters(self, question: str, context: str, 
                                num_documents: int) -> Dict[str, Any]:
        """
        Оптимизирует параметры LLM на основе типа запроса
        """
        # Базовые параметры
        params = {
            'max_tokens': 800,
            'temperature': 0.2,
            'top_p': 0.8,
            'frequency_penalty': 0.1,
            'presence_penalty': 0.1
        }
        
        question_lower = question.lower()
        
        # Адаптация под тип вопроса
        if any(word in question_lower for word in ['example', 'пример', 'как', 'how']):
            # Практические вопросы - больше токенов, меньше температура
            params['max_tokens'] = 1000
            params['temperature'] = 0.1
        elif any(word in question_lower for word in ['что такое', 'what is', 'define']):
            # Определения - средние параметры
            params['max_tokens'] = 600
            params['temperature'] = 0.15
        elif any(word in question_lower for word in ['best practice', 'лучшие практики', 'optimize']):
            # Best practices - больше креативности
            params['max_tokens'] = 1200
            params['temperature'] = 0.25
        
        # Адаптация под количество документов
        if num_documents >= 4:
            params['max_tokens'] += 200  # Больше контекста = больше токенов
        elif num_documents <= 2:
            params['max_tokens'] -= 100  # Меньше контекста = меньше токенов
        
        # Адаптация под длину контекста
        context_length = len(context)
        if context_length > 3000:
            params['max_tokens'] += 150
        elif context_length < 1000:
            params['max_tokens'] -= 50
        
        # Ограничения
        params['max_tokens'] = max(400, min(params['max_tokens'], 1500))
        
        return params
    
    def generate_llm_response_enhanced(self, question: str, context: str, 
                                     framework: str = None) -> str:
        """
        Улучшенная генерация ответов с оптимизированными параметрами
        """
        try:
            llm_config = self.config.get('llm', {})
            model_config = llm_config.get('models', {}).get('qwen', {})
            
            # Форматируем контекст
            formatted_context = self._format_context_for_llm(context)
            
            # Подсчитываем количество документов
            num_documents = len([part for part in context.split('\n\n') if part.strip()])
            
            # Оптимизируем параметры LLM
            optimized_params = self._optimize_llm_parameters(question, context, num_documents)
            
            # Обновляем конфигурацию модели
            model_config.update(optimized_params)
            
            logger.info(f"🤖 LLM PARAMS: max_tokens={optimized_params['max_tokens']}, "
                       f"temperature={optimized_params['temperature']}")
            
            # Создаем улучшенный промпт
            prompt = self._create_enhanced_prompt(question, formatted_context, framework)
            
            # Генерируем ответ с retry системой
            return self._generate_with_retry_enhanced(prompt, model_config)
            
        except Exception as e:
            logger.error(f"❌ ENHANCED LLM ERROR: {e}")
            return "Ошибка при генерации улучшенного ответа"
    
    def _create_enhanced_prompt(self, question: str, context: str, framework: str = None) -> str:
        """
        Создает улучшенный промпт с учетом фреймворка
        """
        framework_instructions = {
            'laravel': "Ты эксперт по Laravel. Давай практические примеры с PHP кодом.",
            'vue': "Ты эксперт по Vue.js. Показывай примеры компонентов и Composition API.",
            'filament': "Ты эксперт по Filament. Фокусируйся на ресурсах, формах и таблицах.",
            'alpine': "Ты эксперт по Alpine.js. Показывай примеры с x-data и директивами.",
            'inertia': "Ты эксперт по Inertia.js. Объясняй SPA подход и интеграцию.",
            'tailwindcss': "Ты эксперт по Tailwind CSS. Показывай utility классы и примеры."
        }
        
        system_instruction = framework_instructions.get(framework, 
            "Ты технический эксперт. Давай точные и практические ответы.")
        
        prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>

{system_instruction}

ВАЖНЫЕ ИНСТРУКЦИИ:
1. Отвечай на основе предоставленной документации
2. Включай практические примеры кода когда это уместно
3. Структурируй ответ четко и логично
4. Если информации недостаточно, честно об этом скажи
5. Завершай ответы полностью - не обрывай на середине

<|eot_id|><|start_header_id|>user<|end_header_id|>

ДОКУМЕНТАЦИЯ:
{context}

ВОПРОС: {question}

Дай полный и структурированный ответ на основе документации выше.<|eot_id|><|start_header_id|>assistant<|end_header_id|>

"""
        return prompt
    
    def _generate_with_retry_enhanced(self, prompt: str, model_config: dict) -> str:
        """
        Улучшенная система retry с адаптивными параметрами
        """
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                # Для повторных попыток корректируем параметры
                current_config = model_config.copy()
                if attempt > 0:
                    current_config['max_tokens'] += attempt * 200
                    current_config['temperature'] = max(0.1, current_config['temperature'] - attempt * 0.05)
                
                # Отправляем запрос
                api_url = current_config.get('api_url', 'http://127.0.0.1:1234/v1/completions')
                
                request_data = {
                    "model": current_config.get('model_name', 'meta-llama-3.1-8b-instruct'),
                    "prompt": prompt,
                    "max_tokens": current_config['max_tokens'],
                    "temperature": current_config['temperature'],
                    "top_p": current_config.get('top_p', 0.8),
                    "frequency_penalty": current_config.get('frequency_penalty', 0.1),
                    "presence_penalty": current_config.get('presence_penalty', 0.1),
                    "stream": False
                }
                
                stop_sequences = current_config.get('stop', [])
                if stop_sequences:
                    request_data["stop"] = stop_sequences
                
                response = requests.post(api_url, json=request_data, timeout=60)
                
                if response.status_code == 200:
                    result = response.json()
                    raw_answer = result.get('choices', [{}])[0].get('text', '')
                    
                    # Очищаем ответ
                    answer = clean_llm_response(raw_answer)
                    answer = self._post_process_response(answer, "", "")
                    
                    # Проверяем качество
                    if not self._is_response_truncated(answer) and len(answer) > 100:
                        logger.info(f"✅ ENHANCED RESPONSE: {len(answer)} chars, attempt: {attempt + 1}")
                        return answer
                    else:
                        logger.warning(f"⚠️ RETRY NEEDED: Attempt {attempt + 1}, quality insufficient")
                        if attempt == max_retries - 1:
                            return answer  # Возвращаем что есть на последней попытке
                        continue
                else:
                    logger.error(f"❌ LLM API ERROR: {response.status_code}")
                    if attempt == max_retries - 1:
                        return "Ошибка при обращении к языковой модели"
                    continue
                    
            except Exception as e:
                logger.error(f"❌ GENERATION ERROR: {e}")
                if attempt == max_retries - 1:
                    return "Ошибка при генерации ответа"
                continue
        
        return "Не удалось получить качественный ответ"
    
    def process_query_enhanced(self, request: QueryRequest) -> QueryResponse:
        """
        Основной метод обработки запроса с всеми улучшениями
        """
        start_time = time.time()
        self.performance_stats['total_queries'] += 1
        
        try:
            logger.info(f"🚀 ENHANCED QUERY START: '{request.question}'")
            
            # 1. Улучшенное определение фреймворка
            detected_framework, confidence = self.detect_framework_enhanced(
                question=request.question,
                context=request.context,
                project_path=request.project_path
            )
            
            # Используем определенный или указанный фреймворк
            final_framework = request.framework or detected_framework
            
            # 2. Проверяем кэш с учетом фреймворка
            cache_key = self.cache_service.get_cache_key(request.question, final_framework)
            cached_response = self.cache_service.get_cached_response(cache_key)
            
            if cached_response:
                self.performance_stats['cache_hits'] += 1
                cached_response['response_time'] = time.time() - start_time
                logger.info(f"💾 CACHE HIT: Response served from cache")
                return QueryResponse(**cached_response)
            
            # 3. Улучшенный поиск документов
            documents = self.query_documents_enhanced(
                question=request.question,
                framework=final_framework,
                max_results=request.max_results,
                use_hybrid=True
            )
            
            if not documents:
                logger.warning("❌ NO DOCUMENTS: No relevant documents found")
                raise Exception("Релевантные документы не найдены")
            
            # 4. Создаем контекст
            context = "\n\n".join([doc['content'] for doc in documents])
            if request.context:
                context += f"\n\nДополнительный контекст:\n{request.context}"
            
            # 5. Улучшенная генерация ответа
            answer = self.generate_llm_response_enhanced(
                question=request.question,
                context=context,
                framework=final_framework
            )
            
            # 6. Подготавливаем источники
            sources = []
            for doc in documents:
                source_info = {
                    "title": doc['metadata'].get('section_title', 'Document'),
                    "content": doc['content'][:200] + "..." if len(doc['content']) > 200 else doc['content'],
                    "framework": doc['metadata'].get('framework', 'unknown'),
                    "relevance_score": doc.get('relevance_score', 0.0)
                }
                
                # Добавляем информацию о типе поиска
                if 'sources' in doc:
                    source_info['search_types'] = doc['sources']
                
                sources.append(source_info)
            
            # 7. Формируем ответ
            response_time = time.time() - start_time
            
            response_data = {
                "answer": answer,
                "sources": sources,
                "total_docs": len(documents),
                "response_time": response_time,
                "framework_detected": detected_framework,
                "framework_confidence": confidence,
                "session_id": None,
                "session_context_used": False,
                "key_moments_detected": [],
                "performance_info": {
                    "used_hybrid_search": True,
                    "embedding_cache_used": True,
                    "framework_auto_detected": detected_framework is not None
                }
            }
            
            # 8. Сохраняем в кэш
            self.cache_service.set_cached_response(cache_key, response_data)
            
            # 9. Обновляем статистику
            self._update_performance_stats(response_time)
            
            logger.info(f"🎉 ENHANCED QUERY COMPLETE: {response_time:.3f}s")
            
            return QueryResponse(**response_data)
            
        except Exception as e:
            logger.error(f"❌ ENHANCED QUERY ERROR: {e}")
            raise
    
    def _update_performance_stats(self, response_time: float):
        """Обновляет статистику производительности"""
        total_queries = self.performance_stats['total_queries']
        current_avg = self.performance_stats['avg_response_time']
        
        # Вычисляем новое среднее время
        new_avg = ((current_avg * (total_queries - 1)) + response_time) / total_queries
        self.performance_stats['avg_response_time'] = new_avg
    
    def get_enhanced_stats(self) -> Dict[str, Any]:
        """Возвращает расширенную статистику"""
        base_stats = super().get_stats() if hasattr(super(), 'get_stats') else {}
        
        enhanced_stats = {
            **base_stats,
            'performance': self.performance_stats,
            'embedding_cache': self.embedding_cache.get_stats(),
            'hybrid_retriever': self.hybrid_retriever.get_stats(),
            'framework_detector': self.enhanced_framework_detector.get_framework_stats(),
            'cache_hit_rate': (
                self.performance_stats['cache_hits'] / 
                max(self.performance_stats['total_queries'], 1)
            )
        }
        
        return enhanced_stats
    
    def clear_all_caches(self):
        """Очищает все кэши"""
        super().cache_service.clear_cache()
        self.embedding_cache.clear_cache()
        self.hybrid_retriever.clear_cache()
        logger.info("🗑️ Все кэши очищены")
    
    def warmup_system(self):
        """Прогревает систему для лучшей производительности"""
        logger.info("🔥 WARMUP: Прогреваем систему...")
        
        # Прогреваем embedding модель
        warmup_texts = [
            "Laravel model creation",
            "Vue component example", 
            "Filament resource setup",
            "Alpine.js directive usage",
            "Inertia.js routing",
            "Tailwind CSS utilities"
        ]
        
        for text in warmup_texts:
            self._create_embedding_with_cache(text)
        
        # Прогреваем BM25 индексы
        for framework in ['laravel', 'vue', 'filament', 'alpine', 'inertia', 'tailwindcss']:
            try:
                self.hybrid_retriever._get_or_create_bm25(framework)
            except:
                pass  # Игнорируем ошибки для отсутствующих фреймворков
        
        logger.info("✅ WARMUP: Система прогрета и готова к работе")
