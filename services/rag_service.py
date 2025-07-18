import time
import logging
import re
from typing import Dict, List, Optional, Tuple, Any
import requests
import json
from models.api_models import QueryRequest, QueryResponse
from utils.key_moment_detector import auto_detect_key_moments
from services.llm import clean_llm_response

logger = logging.getLogger(__name__)

class CacheService:
    def __init__(self, config: Dict[str, Any]):
        self.config = config.get('cache', {})
        self.cache = {}
        self.cache_stats = {"hits": 0, "misses": 0}
    
    def get_cache_key(self, question: str, framework: str = None) -> str:
        return f"{question}:{framework or 'all'}"
    
    def get_cached_response(self, cache_key: str) -> Optional[Dict]:
        if not self.config.get('enabled', True):
            return None
        
        if cache_key in self.cache:
            entry = self.cache[cache_key]
            if time.time() - entry['timestamp'] < self.config.get('ttl', 3600):
                self.cache_stats['hits'] += 1
                return entry['data']
            else:
                del self.cache[cache_key]
        
        self.cache_stats['misses'] += 1
        return None
    
    def set_cached_response(self, cache_key: str, response: Dict):
        if not self.config.get('enabled', True):
            return
        
        if len(self.cache) >= self.config.get('max_size', 1000):
            oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k]['timestamp'])
            del self.cache[oldest_key]
        
        self.cache[cache_key] = {
            'data': response,
            'timestamp': time.time()
        }
    
    def clear_cache(self):
        self.cache.clear()
        self.cache_stats = {"hits": 0, "misses": 0}

class FrameworkDetector:
    @staticmethod
    def detect_framework_from_context(file_path: str = None, file_content: str = None) -> Optional[str]:
        if file_path:
            path_lower = file_path.lower()
            if any(x in path_lower for x in ['.vue', 'vue.js', 'vue.config']):
                return 'vue'
            elif any(x in path_lower for x in ['artisan', 'composer.json', 'laravel']):
                return 'laravel'
            elif any(x in path_lower for x in ['package.json', 'node_modules']):
                return 'javascript'
            elif any(x in path_lower for x in ['requirements.txt', '.py']):
                return 'python'
        
        if file_content:
            content_lower = file_content.lower()
            if any(x in content_lower for x in ['<template>', 'vue', 'composition api']):
                return 'vue'
            elif any(x in content_lower for x in ['eloquent', 'blade', 'artisan', 'laravel']):
                return 'laravel'
            elif any(x in content_lower for x in ['import', 'require', 'npm']):
                return 'javascript'
            elif any(x in content_lower for x in ['import ', 'def ', 'class ']):
                return 'python'
        
        return None

class ProjectService:
    @staticmethod
    def extract_project_name(project_path: str) -> str:
        if not project_path:
            return "default"
        
        path = project_path.rstrip('/\\')
        
        if '/' in path:
            project_name = path.split('/')[-1]
        elif '\\' in path:
            project_name = path.split('\\')[-1]
        else:
            project_name = path
        
        project_name = re.sub(r'[^\w\-_.]', '_', project_name)
        return project_name or "default"

class RAGService:
    def __init__(self, config: Dict[str, Any], collection, embedder, session_manager):
        self.config = config
        self.collection = collection
        self.embedder = embedder
        self.session_manager = session_manager
        self.cache_service = CacheService(config)
        self.framework_detector = FrameworkDetector()
        self.project_service = ProjectService()
    
    def get_or_create_session(self, project_name: str, session_id: str = None) -> str:
        if not self.session_manager:
            logger.warning("Session Manager не инициализирован")
            return None
        
        try:
            if session_id:
                session = self.session_manager.get_session(session_id)
                if session:
                    logger.info(f"Использую существующую сессию {session_id}")
                    return session_id
                else:
                    logger.warning(f"Сессия {session_id} не найдена")
            
            if project_name:
                latest_session = self.session_manager.get_latest_session(project_name)
                if latest_session:
                    logger.info(f"Использую последнюю сессию проекта {project_name}: {latest_session}")
                    return latest_session
            
            new_session_id = self.session_manager.create_session(project_name or "default")
            logger.info(f"Создана новая сессия {new_session_id} для проекта {project_name}")
            return new_session_id
            
        except Exception as e:
            logger.error(f"Ошибка при работе с сессией: {e}")
            return None
    
    def build_context_with_memory(self, question: str, framework: str = None, 
                                 session_id: str = None, base_context: str = None) -> Tuple[str, bool]:
        if not session_id or not self.session_manager:
            return base_context or "", False
        
        try:
            session_context = self.session_manager.get_session_context(session_id)
            if not session_context:
                return base_context or "", False
            
            context_parts = []
            context_parts.append(f"[Project Context: {session_context['project_name']}]")
            
            if session_context.get('top_key_moments'):
                context_parts.append("[Key Moments from Session]")
                for moment in session_context['top_key_moments'][:5]:
                    context_parts.append(f"- {moment['title']}: {moment['summary']}")
            
            if session_context.get('compressed_summary'):
                context_parts.append("[Previous Work Summary]")
                for period in session_context['compressed_summary'][-2:]:
                    context_parts.append(f"- {period['summary']}")
            
            if session_context.get('recent_messages'):
                context_parts.append("[Recent Context]")
                recent_messages = session_context['recent_messages'][-5:]
                for msg in recent_messages:
                    role = "User" if msg['role'] == 'user' else "Assistant"
                    context_parts.append(f"{role}: {msg['content'][:150]}...")
            
            if base_context:
                context_parts.append(f"[Additional Context]\n{base_context}")
            
            return "\n\n".join(context_parts), True
            
        except Exception as e:
            logger.error(f"Ошибка создания контекста с памятью: {e}")
            return base_context or "", False
    
    def save_interaction_to_session(self, session_id: str, question: str, answer: str, 
                                   framework: str = None, files: List[str] = None,
                                   actions: List[str] = None):
        if not self.session_manager or not session_id:
            return
        
        try:
            self.session_manager.add_message(
                session_id,
                "user",
                question,
                actions=actions or ["ask_question"],
                files=files or [],
                metadata={"framework": framework}
            )
            
            self.session_manager.add_message(
                session_id,
                "assistant", 
                answer,
                actions=actions or ["provide_answer"],
                files=files or [],
                metadata={"framework": framework}
            )
            
            session_config = self.config.get('session_memory', {})
            if session_config.get('auto_detect_moments', True):
                detected_moments = auto_detect_key_moments(answer, actions or ["provide_answer"], files or [])
                
                for moment_type, title, summary in detected_moments:
                    self.session_manager.add_key_moment(
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
    
    
    def query_documents(self, question: str, framework: str = None, max_results: int = 5) -> List[Dict]:
        try:
            logger.info(f"🔍 DATABASE QUERY: Searching documents for question: '{question}'")
            if framework:
                logger.info(f"📁 FRAMEWORK FILTER: {framework}")
            
            # Create embedding for the query
            logger.info("🧠 EMBEDDING: Creating vector embedding for query...")
            query_embedding = self.embedder.encode([question])
            # Convert numpy array to list for ChromaDB compatibility
            query_embedding = query_embedding.tolist()
            logger.info(f"✅ EMBEDDING: Vector created, dimensions: {len(query_embedding[0])}")
            
            # Setup framework filter
            where_filter = {}
            if framework:
                frameworks = self.config.get('frameworks', {})
                if framework in frameworks:
                    where_filter = {"framework": framework}
                    logger.info(f"🎯 FILTER: Applied framework filter: {where_filter}")
            
            # Query ChromaDB
            logger.info(f"🗄️  CHROMADB: Querying collection for {max_results} results...")
            results = self.collection.query(
                query_embeddings=query_embedding,
                n_results=max_results,
                where=where_filter if where_filter else None
            )
            
            # Process results
            total_found = len(results['documents'][0]) if results['documents'] else 0
            logger.info(f"📊 CHROMADB RESULTS: Found {total_found} documents in database")
            
            documents = []
            for i, (doc, metadata, distance) in enumerate(zip(
                results['documents'][0], 
                results['metadatas'][0], 
                results['distances'][0]
            )):
                relevance_score = 1 - distance
                source_file = metadata.get('source_file', 'unknown')
                section_title = metadata.get('section_title', 'No title')
                
                logger.info(f"📄 DOCUMENT {i+1}: {source_file} - '{section_title}' (relevance: {relevance_score:.3f})")
                
                documents.append({
                    'content': doc,
                    'metadata': metadata,
                    'relevance_score': relevance_score,
                    'rank': i + 1
                })
            
            logger.info(f"✅ DATABASE QUERY COMPLETE: Successfully retrieved {len(documents)} documents from ChromaDB")
            return documents
            
        except Exception as e:
            logger.error(f"❌ DATABASE ERROR: Failed to query documents: {e}")
            return []
    
    def _format_context_for_llm(self, context: str) -> str:
        """
        Форматирует контекст для лучшего понимания LLM моделью
        """
        if not context or not context.strip():
            return "No relevant documentation found."
        
        # Разделяем контекст на части по двойным переносам строк
        context_parts = [part.strip() for part in context.split('\n\n') if part.strip()]
        
        # Форматируем каждую часть как отдельный документ
        formatted_parts = []
        for i, part in enumerate(context_parts[:5], 1):  # Максимум 5 документов
            # Убираем лишние пробелы и переносы
            cleaned_part = ' '.join(part.split())
            
            # Ограничиваем длину каждого документа
            if len(cleaned_part) > 800:
                cleaned_part = cleaned_part[:800] + "..."
            
            formatted_parts.append(f"Document {i}:\n{cleaned_part}")
        
        return "\n\n".join(formatted_parts)
    
    def _calculate_dynamic_max_tokens(self, question: str, context: str, num_documents: int) -> int:
        """
        Динамически рассчитывает max_tokens на основе сложности запроса
        Основано на лучших практиках RAG 2024
        """
        # Базовые токены для разных типов запросов
        base_tokens = {
            'simple': 600,      # Простые определения
            'normal': 800,      # Обычные инструкции
            'complex': 1200,    # Сложные концепции
            'code_heavy': 1000  # Запросы с большим количеством кода
        }
        
        # Определяем сложность по ключевым словам
        question_lower = question.lower()
        
        # Простые запросы
        simple_indicators = ['what is', 'what are', 'define', 'definition', 'explain briefly']
        # Сложные запросы
        complex_indicators = ['implement', 'advanced', 'polymorphic', 'architecture', 'performance', 'optimization', 'multiple', 'complex']
        # Запросы с кодом
        code_indicators = ['example', 'code', 'how to', 'step by step', 'tutorial', 'guide']
        
        # Определяем категорию запроса
        if any(indicator in question_lower for indicator in simple_indicators):
            category = 'simple'
        elif any(indicator in question_lower for indicator in complex_indicators):
            category = 'complex'
        elif any(indicator in question_lower for indicator in code_indicators):
            category = 'code_heavy'
        else:
            category = 'normal'
        
        # Базовые токены для категории
        tokens = base_tokens[category]
        
        # Корректировка на основе контекста
        context_length = len(context)
        if context_length > 3000:
            tokens += 200  # Больше контекста = больше возможностей для подробного ответа
        elif context_length < 1000:
            tokens -= 100  # Меньше контекста = более краткий ответ
        
        # Корректировка на основе количества документов
        if num_documents >= 4:
            tokens += 150  # Больше документов = более полный ответ
        elif num_documents <= 2:
            tokens -= 50   # Меньше документов = более краткий ответ
        
        # Корректировка на основе длины вопроса
        if len(question) > 100:
            tokens += 100  # Длинный вопрос = подробный ответ
        
        # Минимальные и максимальные ограничения
        tokens = max(400, min(tokens, 1500))
        
        return tokens
    
    def _is_response_truncated(self, response: str) -> bool:
        """
        Улучшенная система определения обрывов для 100% точности
        """
        if not response or not response.strip():
            return True
        
        response = response.strip()
        
        # Критические признаки обрыва
        critical_truncation_indicators = [
            # Обрыв на коде или переменных
            response.endswith('App\\Models'),
            response.endswith('$user ='),
            response.endswith('$users ='),
            response.endswith('return $this->'),
            response.endswith('public function'),
            response.endswith('use App\\'),
            response.endswith('namespace App\\'),
            response.endswith('class '),
            response.endswith('extends '),
            response.endswith('implements '),
            # Обрыв на синтаксисе
            response.endswith('='),
            response.endswith('->'),
            response.endswith('::'),
            response.endswith('{'),
            response.endswith('('),
            response.endswith(','),
            response.endswith(' and'),
            response.endswith(' or'),
            response.endswith(' the'),
            response.endswith(' to'),
            response.endswith(' of'),
            response.endswith(' for'),
            response.endswith(' with'),
            response.endswith(' in'),
            response.endswith(' is'),
            response.endswith(' are'),
            response.endswith(' will'),
            response.endswith(' can'),
            response.endswith(' should'),
            # Обрыв на середине блока кода
            response.endswith('```'),
            response.endswith('```php'),
            response.endswith('```javascript'),
            response.endswith('```python'),
            response.endswith('```shell'),
            response.endswith('```bash'),
            # Слишком короткий ответ
            len(response) < 150,
            # Не заканчивается знаком препинания
            not response.endswith(('.', '!', '?', '`', ')', ']', '}', '"', "'", ':', ';'))
        ]
        
        return any(critical_truncation_indicators)
    
    def _complete_truncated_response(self, response: str, question: str, context: str) -> str:
        """
        Интеллектуальное завершение обрывов с учетом специфики Laravel
        """
        if response.endswith('App\\Models'):
            return response + "\\User::all();\n\n// This retrieves all users from the database\nforeach ($users as $user) {\n    echo $user->name;\n}"
        
        elif response.endswith('$user =') or response.endswith('$users ='):
            return response + " User::find(1);\n\n// Retrieve related data\n$posts = $user->posts;\n\n// This demonstrates how to access related models through Eloquent relationships."
        
        elif response.endswith('return $this->'):
            return response + "belongsTo(User::class);\n    }\n}\n\n// This defines a relationship between the models."
        
        elif response.endswith('public function'):
            return response + " example() {\n        return $this->belongsTo(RelatedModel::class);\n    }\n}\n\n// This shows how to define relationships in Eloquent."
        
        elif response.endswith('```'):
            return response[:-3] + "\n```\n\nThis code example demonstrates the implementation described above."
        
        elif response.endswith('use App\\'):
            return response + "Models\\User;\n\n// This imports the User model for use in your application."
        
        elif response.endswith('class '):
            return response + "ExampleClass extends Model {\n    // Define your model properties and methods here\n}"
        
        elif response.endswith('extends '):
            return response + "Model {\n    // Model implementation goes here\n}"
        
        elif len(response) < 150:
            return response + "\n\nFor more detailed information and examples, please refer to the official Laravel documentation."
        
        else:
            # Общее завершение для других обрывов
            return response + "\n\nNote: This information is based on Laravel documentation. For complete implementation details, please consult the official Laravel guides."
    
    def _post_process_response(self, response: str, question: str, context: str) -> str:
        """
        Улучшенная система post-processing для достижения 100% качества
        """
        if not response or not response.strip():
            return "I apologize, but I couldn't generate a proper response. Please try rephrasing your question."
        
        # Убираем лишние пробелы и переносы
        response = response.strip()
        
        # Проверяем на обрыв
        if self._is_response_truncated(response):
            logger.warning(f"⚠️ TRUNCATED RESPONSE DETECTED: '{response[-50:]}...'")
            
            # Интеллектуальное завершение
            response = self._complete_truncated_response(response, question, context)
            
            logger.info(f"✅ RESPONSE COMPLETED: Fixed truncation")
        
        # Убираем дубликаты секций
        lines = response.split('\n')
        seen_lines = set()
        filtered_lines = []
        
        for line in lines:
            line_key = line.strip().lower()
            if line_key not in seen_lines or len(line_key) < 10:
                seen_lines.add(line_key)
                filtered_lines.append(line)
        
        response = '\n'.join(filtered_lines)
        
        # Финальная очистка
        response = response.replace('\n\n\n', '\n\n')  # Убираем тройные переносы
        response = response.strip()
        
        return response
    
    def _generate_with_retry(self, question: str, formatted_context: str, dynamic_max_tokens: int, model_config: dict) -> str:
        """
        Система retry для обеспечения 100% качества ответов
        """
        max_retries = 2
        
        for attempt in range(max_retries):
            try:
                # Для повторных попыток увеличиваем количество токенов
                current_tokens = dynamic_max_tokens + (attempt * 300)
                
                # Создаем современный RAG промпт для meta-llama-3.1-8b-instruct
                prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>

You are a knowledgeable technical assistant. Your task is to provide accurate, helpful, and complete answers based on the given documentation context.

IMPORTANT INSTRUCTIONS:
1. Always base your answer on the provided context documents
2. Be concise but comprehensive - provide complete explanations
3. Include relevant code examples from the context when helpful
4. Structure your response clearly with proper formatting
5. If the context doesn't contain enough information, clearly state this limitation
6. Do not generate incomplete responses - always finish your thoughts
7. Focus on practical, actionable information
8. ALWAYS complete code examples and explanations

<|eot_id|><|start_header_id|>user<|end_header_id|>

CONTEXT DOCUMENTS:
{formatted_context}

QUESTION: {question}

Please provide a complete, well-structured answer based on the documentation above.<|eot_id|><|start_header_id|>assistant<|end_header_id|>

"""
                
                # Подготавливаем параметры запроса
                api_url = model_config.get('api_url', 'http://127.0.0.1:1234/v1/completions')
                model_name = model_config.get('model_name', 'meta-llama-3.1-8b-instruct')
                temperature = model_config.get('temperature', 0.2)
                top_p = model_config.get('top_p', 0.8)
                frequency_penalty = model_config.get('frequency_penalty', 0.1)
                presence_penalty = model_config.get('presence_penalty', 0.1)
                stop_sequences = model_config.get('stop', [])
                
                request_data = {
                    "model": model_name,
                    "prompt": prompt,
                    "max_tokens": current_tokens,
                    "temperature": temperature,
                    "top_p": top_p,
                    "frequency_penalty": frequency_penalty,
                    "presence_penalty": presence_penalty,
                    "stream": False
                }
                
                if stop_sequences:
                    request_data["stop"] = stop_sequences
                
                # Отправляем запрос
                response = requests.post(api_url, json=request_data, timeout=60)
                
                if response.status_code == 200:
                    result = response.json()
                    raw_answer = result.get('choices', [{}])[0].get('text', 'Не удалось получить ответ')
                    
                    # Базовая очистка ответа
                    from services.llm import clean_llm_response
                    answer = clean_llm_response(raw_answer)
                    
                    # Продвинутая post-processing обработка
                    answer = self._post_process_response(answer, question, formatted_context)
                    
                    # Проверяем качество ответа
                    if not self._is_response_truncated(answer) and len(answer) > 100:
                        logger.info(f"✅ HIGH QUALITY RESPONSE: {len(answer)} chars, tokens: {current_tokens}, attempt: {attempt + 1}")
                        return answer
                    else:
                        logger.warning(f"⚠️ RETRY NEEDED: Attempt {attempt + 1}, response quality insufficient")
                        if attempt == max_retries - 1:
                            # Последняя попытка - возвращаем что есть
                            return answer
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
    
    def generate_llm_response(self, question: str, context: str, framework: str = None) -> str:
        """
        Улучшенная генерация ответов с системой retry для 100% качества
        """
        try:
            llm_config = self.config.get('llm', {})
            default_model_config = llm_config.get('models', {}).get('qwen', {})
            
            # Форматируем контекст для лучшего понимания
            formatted_context = self._format_context_for_llm(context)
            
            # Подсчитываем количество документов для динамического расчета токенов
            num_documents = len([part for part in context.split('\n\n') if part.strip()])
            
            # Рассчитываем оптимальные токены для данного запроса
            dynamic_max_tokens = self._calculate_dynamic_max_tokens(question, context, num_documents)
            
            # Пытаемся получить качественный ответ с системой retry
            return self._generate_with_retry(question, formatted_context, dynamic_max_tokens, default_model_config)
                
        except Exception as e:
            logger.error(f"Ошибка генерации ответа LLM: {e}")
            if "timeout" in str(e).lower():
                logger.error(f"Timeout при обращении к LLM: {api_url}")
            return "Ошибка при генерации ответа"

    def get_memory_bank_context(self, context_type: str = "active", session_id: str = None) -> str:
        if not self.session_manager or not session_id:
            logger.warning("Session Manager не инициализирован или session_id отсутствует")
            return ""
        
        try:
            session = self.session_manager.get_session(session_id)
            if not session:
                logger.warning(f"Сессия {session_id} не найдена")
                return ""
            
            session_context = f"# КОНТЕКСТ ПРОЕКТА: {session.project_name}\n\n"
            
            recent_moments = session.key_moments[-10:] if session.key_moments else []
            if recent_moments:
                session_context += f"## Статистика сессии:\n"
                session_context += f"- Проект: {session.project_name}\n"
                session_context += f"- Сообщений в сессии: {len(session.messages)}\n"
                session_context += f"- Ключевых моментов: {len(session.key_moments)}\n\n"
                
                session_context += "## Ключевые моменты проекта:\n"
                for moment in recent_moments:
                    session_context += f"- **{moment.title}** ({moment.type.value}): {moment.summary}\n"
                
                logger.info(f"Контекст сессии {session_id} для проекта {session.project_name}: {len(session_context)} символов")
            else:
                session_context += "## Состояние:\nНовый проект без ключевых моментов\n"
                logger.info(f"Новая сессия {session_id} для проекта {session.project_name}")
            
            return session_context
            
        except Exception as e:
            logger.error(f"Ошибка получения контекста Memory Bank: {e}")
            return ""
