#!/usr/bin/env python3
"""
Universal Document Indexer for RAG Systems
Универсальный индексатор документов для RAG систем

Основан на лучших практиках RAG 2024:
- Инкрементальная индексация (Delta indexing)
- Многовекторное индексирование (Multi-vector indexing)
- Контекстное обогащение чанков (Contextual chunk enrichment)
- Семантическое чанкование (Semantic chunking)
- Версионирование документов (Document versioning)
- Фреймворк-агностичный подход (Framework agnostic)
"""

import os
import sys
import logging
import yaml
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum

import chromadb
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

# Добавляем корневую папку в путь для импорта
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.text_splitter import get_text_splitter

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class IndexingMode(Enum):
    """Режимы индексации"""
    FULL = "full"           # Полная переиндексация
    INCREMENTAL = "incremental"  # Инкрементальная индексация
    DELTA = "delta"         # Только изменения
    FRAMEWORK_ONLY = "framework_only"  # Только определенный фреймворк

class DocumentType(Enum):
    """Типы документов для обработки"""
    MARKDOWN = "markdown"
    HTML = "html"
    TEXT = "text"
    VITEPRESS = "vitepress"
    DOCUSAURUS = "docusaurus"
    GITBOOK = "gitbook"

@dataclass
class DocumentMetadata:
    """Метаданные документа для версионирования"""
    file_path: str
    framework: str
    document_type: DocumentType
    file_hash: str
    last_modified: str
    created_at: str
    file_size: int
    version: int = 1
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь"""
        data = asdict(self)
        data['document_type'] = self.document_type.value
        return data

@dataclass
class ChunkMetadata:
    """Расширенные метаданные чанка"""
    chunk_id: str
    document_id: str
    framework: str
    source_file: str
    section_title: str
    chunk_index: int
    chunk_type: str
    context_window: str
    parent_sections: List[str]
    semantic_labels: List[str]
    confidence_score: float
    created_at: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь"""
        return asdict(self)

class UniversalDocumentIndexer:
    """
    Универсальный индексатор документов для RAG систем
    
    Поддерживает:
    - Все типы фреймворков из config.yaml
    - Инкрементальную индексацию
    - Версионирование документов
    - Контекстное обогащение чанков
    - Семантическое чанкование
    """
    
    def __init__(self, config_path: str = 'config.yaml'):
        """Инициализация индексатора"""
        self.config = self._load_config(config_path)
        self.document_metadata_cache = {}
        self.processed_documents = set()
        
        # Инициализация ChromaDB
        self.client = chromadb.PersistentClient(
            path=self.config['database']['path']
        )
        
        # Инициализация модели embeddings
        self.embedder = SentenceTransformer(
            self.config['embeddings']['model']
        )
        
        # Кэш для text_splitter'ов разных фреймворков
        self.text_splitters = {}
        
        logger.info("✅ Universal Document Indexer initialized")
        
    def _load_config(self, config_path: str) -> Dict:
        """Загружает конфигурацию"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                
            # Валидация конфигурации
            required_sections = ['database', 'embeddings', 'frameworks']
            for section in required_sections:
                if section not in config:
                    raise ValueError(f"Отсутствует секция {section} в конфигурации")
                    
            return config
            
        except Exception as e:
            logger.error(f"Ошибка загрузки конфигурации: {e}")
            raise
    
    def _get_text_splitter(self, framework: str):
        """Получает text_splitter для конкретного фреймворка"""
        if framework not in self.text_splitters:
            # Адаптивный размер чанка в зависимости от фреймворка
            chunk_sizes = {
                'laravel': 800,
                'vue': 600,
                'filament': 700,
                'alpine': 500,
                'inertia': 600,
                'tailwindcss': 600
            }
            
            overlap_sizes = {
                'laravel': 150,
                'vue': 100,
                'filament': 120,
                'alpine': 80,
                'inertia': 100,
                'tailwindcss': 100
            }
            
            chunk_size = chunk_sizes.get(framework, 700)
            overlap_size = overlap_sizes.get(framework, 120)
            
            self.text_splitters[framework] = get_text_splitter(
                framework=framework,
                chunk_size=chunk_size,
                overlap_size=overlap_size
            )
            
        return self.text_splitters[framework]
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """Вычисляет хеш файла для определения изменений"""
        try:
            with open(file_path, 'rb') as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
            return file_hash
        except Exception as e:
            logger.warning(f"Не удалось вычислить хеш для {file_path}: {e}")
            return ""
    
    def _get_document_metadata(self, file_path: Path, framework: str) -> DocumentMetadata:
        """Создает метаданные документа"""
        file_stat = file_path.stat()
        file_hash = self._calculate_file_hash(file_path)
        
        # Определяем тип документа
        framework_config = self.config['frameworks'].get(framework, {})
        doc_type = DocumentType(framework_config.get('type', 'markdown'))
        
        return DocumentMetadata(
            file_path=str(file_path),
            framework=framework,
            document_type=doc_type,
            file_hash=file_hash,
            last_modified=datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
            created_at=datetime.now().isoformat(),
            file_size=file_stat.st_size
        )
    
    def _should_process_document(self, file_path: Path, framework: str) -> bool:
        """Определяет, нужно ли обрабатывать документ (для инкрементальной индексации)"""
        current_hash = self._calculate_file_hash(file_path)
        doc_key = f"{framework}:{str(file_path)}"
        
        if doc_key in self.document_metadata_cache:
            cached_hash = self.document_metadata_cache[doc_key].get('file_hash')
            if cached_hash == current_hash:
                logger.debug(f"Документ {file_path.name} не изменился, пропускаем")
                return False
        
        return True
    
    def _find_framework_documents(self, framework: str) -> List[Path]:
        """Находит все документы для конкретного фреймворка"""
        framework_config = self.config['frameworks'].get(framework, {})
        if not framework_config.get('enabled', True):
            logger.info(f"Фреймворк {framework} отключен, пропускаем")
            return []
        
        docs_path = Path(framework_config['path'])
        if not docs_path.exists():
            logger.warning(f"Папка документации не найдена: {docs_path}")
            return []
        
        # Определяем расширения файлов в зависимости от типа документации
        doc_type = framework_config.get('type', 'markdown')
        
        extensions = {
            'markdown': ['*.md', '*.markdown'],
            'vitepress': ['*.md', '*.vue'],
            'docusaurus': ['*.md', '*.mdx'],
            'gitbook': ['*.md'],
            'html': ['*.html', '*.htm'],
            'text': ['*.txt']
        }
        
        files = []
        for ext in extensions.get(doc_type, ['*.md']):
            files.extend(docs_path.rglob(ext))
        
        # Фильтруем файлы по exclude_patterns
        exclude_patterns = self.config.get('auto_scan', {}).get('exclude_patterns', [])
        filtered_files = []
        
        for file_path in files:
            should_exclude = False
            for pattern in exclude_patterns:
                if pattern in str(file_path):
                    should_exclude = True
                    break
            
            if not should_exclude:
                filtered_files.append(file_path)
        
        return filtered_files
    
    def _process_document(self, file_path: Path, framework: str) -> List[Dict]:
        """Обрабатывает один документ"""
        try:
            # Читаем файл
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if not content.strip():
                logger.warning(f"Файл {file_path.name} пустой")
                return []
            
            # Получаем text_splitter для фреймворка
            text_splitter = self._get_text_splitter(framework)
            
            # Предварительная обработка контента
            if hasattr(text_splitter, 'preprocess_markdown'):
                content = text_splitter.preprocess_markdown(content)
            
            # Создаем метаданные документа
            doc_metadata = self._get_document_metadata(file_path, framework)
            
            # Базовые метаданные для чанкинга
            base_metadata = {
                'document_id': f"{framework}:{file_path.stem}",
                'framework': framework,
                'source_file': file_path.stem,
                'file_path': str(file_path),
                'document_type': doc_metadata.document_type.value,
                'file_hash': doc_metadata.file_hash,
                'last_modified': doc_metadata.last_modified,
                'created_at': doc_metadata.created_at
            }
            
            # Семантическое разделение на чанки
            chunks = text_splitter.split_text(content, base_metadata)
            
            # Контекстное обогащение чанков
            enriched_chunks = self._enrich_chunks_with_context(chunks, content, framework)
            
            logger.debug(f"Обработан {file_path.name}: {len(enriched_chunks)} чанков")
            
            return enriched_chunks
            
        except Exception as e:
            logger.error(f"Ошибка при обработке файла {file_path}: {e}")
            return []
    
    def _enrich_chunks_with_context(self, chunks: List[Dict], full_content: str, framework: str) -> List[Dict]:
        """
        Контекстное обогащение чанков (Context-enriched chunking)
        Добавляет контекстную информацию согласно лучшим практикам RAG 2024
        """
        enriched_chunks = []
        
        for i, chunk in enumerate(chunks):
            # Базовая информация о чанке
            enriched_chunk = chunk.copy()
            
            # Добавляем индекс чанка
            enriched_chunk['metadata']['chunk_index'] = i
            
            # Добавляем контекст соседних чанков (window-based context)
            context_window = self._create_context_window(chunks, i, window_size=2)
            enriched_chunk['metadata']['context_window'] = context_window
            
            # Добавляем семантические метки
            semantic_labels = self._generate_semantic_labels(chunk['content'], framework)
            enriched_chunk['metadata']['semantic_labels'] = semantic_labels
            
            # Добавляем информацию о родительских секциях
            parent_sections = self._extract_parent_sections(chunk['content'])
            enriched_chunk['metadata']['parent_sections'] = parent_sections
            
            # Добавляем оценку уверенности
            confidence_score = self._calculate_confidence_score(chunk['content'])
            enriched_chunk['metadata']['confidence_score'] = confidence_score
            
            # Добавляем тип чанка
            chunk_type = self._classify_chunk_type(chunk['content'])
            enriched_chunk['metadata']['chunk_type'] = chunk_type
            
            enriched_chunks.append(enriched_chunk)
        
        return enriched_chunks
    
    def _create_context_window(self, chunks: List[Dict], current_index: int, window_size: int = 2) -> str:
        """Создает контекстное окно для чанка"""
        context_parts = []
        
        # Предыдущие чанки
        start_idx = max(0, current_index - window_size)
        for i in range(start_idx, current_index):
            context_parts.append(f"Previous: {chunks[i]['content'][:100]}...")
        
        # Следующие чанки
        end_idx = min(len(chunks), current_index + window_size + 1)
        for i in range(current_index + 1, end_idx):
            context_parts.append(f"Next: {chunks[i]['content'][:100]}...")
        
        return " | ".join(context_parts)
    
    def _generate_semantic_labels(self, content: str, framework: str) -> List[str]:
        """Генерирует семантические метки для чанка"""
        labels = []
        
        # Фреймворк-специфичные метки
        framework_keywords = {
            'laravel': ['eloquent', 'blade', 'artisan', 'migration', 'model', 'controller', 'route'],
            'vue': ['component', 'directive', 'reactive', 'composition', 'template', 'props', 'emit'],
            'filament': ['resource', 'form', 'table', 'action', 'widget', 'page', 'relation'],
            'alpine': ['data', 'show', 'if', 'for', 'model', 'click', 'init'],
            'inertia': ['visit', 'form', 'link', 'router', 'props', 'page', 'component'],
            'tailwindcss': ['utility', 'responsive', 'hover', 'focus', 'dark', 'variant', 'class']
        }
        
        content_lower = content.lower()
        
        # Добавляем метки для фреймворка
        for keyword in framework_keywords.get(framework, []):
            if keyword in content_lower:
                labels.append(keyword)
        
        # Общие метки
        if 'example' in content_lower or 'код' in content_lower:
            labels.append('code_example')
        
        if 'api' in content_lower:
            labels.append('api_reference')
        
        if 'tutorial' in content_lower or 'guide' in content_lower:
            labels.append('tutorial')
        
        if 'configuration' in content_lower or 'config' in content_lower:
            labels.append('configuration')
        
        return labels
    
    def _extract_parent_sections(self, content: str) -> List[str]:
        """Извлекает информацию о родительских секциях"""
        sections = []
        
        # Ищем заголовки markdown
        lines = content.split('\n')
        for line in lines:
            if line.strip().startswith('#'):
                # Убираем # и получаем заголовок
                title = line.strip().lstrip('#').strip()
                if title:
                    sections.append(title)
        
        return sections[:3]  # Ограничиваем до 3 секций
    
    def _calculate_confidence_score(self, content: str) -> float:
        """Вычисляет оценку уверенности для чанка"""
        # Простая эвристика для оценки качества чанка
        score = 0.5  # Базовая оценка
        
        # Длина контента
        if 50 <= len(content) <= 1000:
            score += 0.2
        
        # Наличие структуры
        if '```' in content:  # Блоки кода
            score += 0.15
        
        if content.count('\n') > 2:  # Многострочный контент
            score += 0.1
        
        # Наличие специальных маркеров
        if any(marker in content.lower() for marker in ['example', 'note', 'important', 'warning']):
            score += 0.05
        
        return min(1.0, score)
    
    def _classify_chunk_type(self, content: str) -> str:
        """Классифицирует тип чанка"""
        content_lower = content.lower()
        
        if '```' in content:
            return 'code_block'
        elif content_lower.startswith('# '):
            return 'header'
        elif 'example' in content_lower:
            return 'example'
        elif 'note' in content_lower or 'important' in content_lower:
            return 'note'
        elif 'api' in content_lower or 'method' in content_lower:
            return 'api_reference'
        else:
            return 'general'
    
    def _add_chunks_to_collection(self, collection, chunks: List[Dict], framework: str):
        """Добавляет чанки в ChromaDB коллекцию с улучшенными метаданными"""
        if not chunks:
            return
        
        # Подготавливаем данные для ChromaDB
        documents = []
        metadatas = []
        ids = []
        
        for chunk in chunks:
            documents.append(chunk['content'])
            # Убеждаемся, что все метаданные - строки или числа
            metadata = self._prepare_metadata_for_chromadb(chunk['metadata'])
            metadatas.append(metadata)
            ids.append(chunk['metadata']['chunk_id'])
        
        # Создаем embeddings
        logger.debug(f"Создаем embeddings для {len(documents)} чанков {framework}...")
        embeddings = self.embedder.encode(documents, show_progress_bar=False).tolist()
        
        # Добавляем в коллекцию
        collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids,
            embeddings=embeddings
        )
    
    def _prepare_metadata_for_chromadb(self, metadata: Dict) -> Dict:
        """Подготавливает метаданные для ChromaDB (только строки и числа)"""
        prepared = {}
        
        for key, value in metadata.items():
            if isinstance(value, (str, int, float)):
                prepared[key] = value
            elif isinstance(value, list):
                # Преобразуем списки в строки
                prepared[key] = ', '.join(str(item) for item in value)
            elif isinstance(value, dict):
                # Преобразуем словари в JSON строки
                prepared[key] = json.dumps(value)
            else:
                prepared[key] = str(value)
        
        return prepared
    
    def clear_framework_data(self, framework: str):
        """Очищает данные конкретного фреймворка"""
        logger.info(f"🗑️  Очищаем данные фреймворка {framework}...")
        
        try:
            collection = self.client.get_collection(
                self.config['database']['collection_name']
            )
            
            # Получаем все документы фреймворка
            framework_docs = collection.get(
                where={"framework": framework},
                include=['ids']
            )
            
            if framework_docs['ids']:
                logger.info(f"Найдено {len(framework_docs['ids'])} документов {framework}")
                collection.delete(ids=framework_docs['ids'])
                logger.info(f"✅ Данные фреймворка {framework} удалены")
            else:
                logger.info(f"Данных фреймворка {framework} не найдено")
                
        except Exception as e:
            logger.error(f"Ошибка при очистке данных {framework}: {e}")
    
    def clear_all_data(self):
        """Очищает все данные"""
        logger.info("🗑️  Очищаем все данные...")
        
        try:
            # Удаляем коллекцию
            self.client.delete_collection(
                self.config['database']['collection_name']
            )
            
            # Создаем новую коллекцию
            self.client.create_collection(
                self.config['database']['collection_name']
            )
            
            logger.info("✅ Все данные очищены")
            
        except Exception as e:
            logger.error(f"Ошибка при очистке всех данных: {e}")
    
    def process_framework(self, framework: str, mode: IndexingMode = IndexingMode.FULL):
        """Обрабатывает документацию конкретного фреймворка"""
        logger.info(f"📚 Обрабатываем фреймворк {framework} в режиме {mode.value}")
        
        # Находим все документы фреймворка
        documents = self._find_framework_documents(framework)
        if not documents:
            logger.warning(f"Документы для фреймворка {framework} не найдены")
            return
        
        logger.info(f"Найдено {len(documents)} файлов для фреймворка {framework}")
        
        # Получаем коллекцию
        try:
            collection = self.client.get_collection(
                self.config['database']['collection_name']
            )
        except:
            collection = self.client.create_collection(
                self.config['database']['collection_name']
            )
        
        # Обрабатываем документы
        total_chunks = 0
        processed_files = 0
        
        for doc_path in tqdm(documents, desc=f"Обработка {framework}"):
            try:
                # Проверяем, нужно ли обрабатывать документ
                if mode == IndexingMode.INCREMENTAL and not self._should_process_document(doc_path, framework):
                    continue
                
                chunks = self._process_document(doc_path, framework)
                if chunks:
                    self._add_chunks_to_collection(collection, chunks, framework)
                    total_chunks += len(chunks)
                    processed_files += 1
                    logger.debug(f"✅ {doc_path.name}: создано {len(chunks)} чанков")
                else:
                    logger.warning(f"⚠️  {doc_path.name}: чанки не созданы")
                    
            except Exception as e:
                logger.error(f"❌ Ошибка при обработке {doc_path.name}: {e}")
        
        logger.info(f"🎉 Фреймворк {framework} обработан! Файлов: {processed_files}, чанков: {total_chunks}")
    
    def process_all_frameworks(self, mode: IndexingMode = IndexingMode.FULL):
        """Обрабатывает все включенные фреймворки"""
        logger.info(f"🚀 Начинаем обработку всех фреймворков в режиме {mode.value}")
        
        if mode == IndexingMode.FULL:
            self.clear_all_data()
        
        # Получаем список активных фреймворков
        active_frameworks = [
            name for name, config in self.config['frameworks'].items()
            if config.get('enabled', True)
        ]
        
        logger.info(f"Активные фреймворки: {', '.join(active_frameworks)}")
        
        for framework in active_frameworks:
            try:
                if mode == IndexingMode.FULL:
                    # При полной индексации очищаем данные фреймворка
                    self.clear_framework_data(framework)
                
                self.process_framework(framework, mode)
                
            except Exception as e:
                logger.error(f"❌ Ошибка при обработке фреймворка {framework}: {e}")
        
        # Проверяем результаты
        self._verify_indexing_results()
    
    def _verify_indexing_results(self):
        """Проверяет результаты индексации"""
        logger.info("🔍 Проверяем результаты индексации...")
        
        try:
            collection = self.client.get_collection(
                self.config['database']['collection_name']
            )
            
            # Общая статистика
            total_docs = collection.count()
            logger.info(f"📊 Всего документов в коллекции: {total_docs}")
            
            # Статистика по фреймворкам
            framework_stats = {}
            for framework in self.config['frameworks'].keys():
                framework_docs = collection.get(
                    where={"framework": framework},
                    include=['metadatas']
                )
                
                if framework_docs['metadatas']:
                    framework_stats[framework] = len(framework_docs['metadatas'])
            
            logger.info("📋 Статистика по фреймворкам:")
            for framework, count in sorted(framework_stats.items()):
                logger.info(f"   {framework}: {count} документов")
            
            # Проверяем качество данных
            self._check_data_quality(collection)
            
        except Exception as e:
            logger.error(f"Ошибка при проверке результатов: {e}")
    
    def _check_data_quality(self, collection):
        """Проверяет качество индексированных данных"""
        logger.info("🔍 Проверяем качество данных...")
        
        try:
            # Получаем все документы
            all_docs = collection.get(include=['metadatas'])
            
            if not all_docs['metadatas']:
                logger.warning("Нет данных для проверки качества")
                return
            
            # Проверяем метаданные
            metadata_keys = set()
            for metadata in all_docs['metadatas']:
                metadata_keys.update(metadata.keys())
            
            logger.info(f"📊 Ключи метаданных: {', '.join(sorted(metadata_keys))}")
            
            # Проверяем типы чанков
            chunk_types = {}
            for metadata in all_docs['metadatas']:
                chunk_type = metadata.get('chunk_type', 'unknown')
                chunk_types[chunk_type] = chunk_types.get(chunk_type, 0) + 1
            
            logger.info("📊 Типы чанков:")
            for chunk_type, count in sorted(chunk_types.items()):
                logger.info(f"   {chunk_type}: {count}")
            
            # Проверяем среднюю оценку уверенности
            confidence_scores = []
            for metadata in all_docs['metadatas']:
                try:
                    score = float(metadata.get('confidence_score', 0))
                    confidence_scores.append(score)
                except (ValueError, TypeError):
                    pass
            
            if confidence_scores:
                avg_confidence = sum(confidence_scores) / len(confidence_scores)
                logger.info(f"📊 Средняя оценка уверенности: {avg_confidence:.3f}")
            
        except Exception as e:
            logger.error(f"Ошибка при проверке качества данных: {e}")
    
    def test_search_quality(self, framework: str = None):
        """Тестирует качество поиска после индексации"""
        logger.info("🧪 Тестируем качество поиска...")
        
        try:
            collection = self.client.get_collection(
                self.config['database']['collection_name']
            )
            
            # Фреймворк-специфичные тестовые запросы
            test_queries = {
                'laravel': [
                    "Как создать миграцию в Laravel?",
                    "php artisan make:migration",
                    "Laravel Eloquent модели",
                    "Blade шаблоны",
                    "Laravel routing"
                ],
                'vue': [
                    "Vue composition API",
                    "Vue компоненты",
                    "реактивность в Vue",
                    "Vue директивы",
                    "props и emit"
                ],
                'filament': [
                    "Filament ресурсы",
                    "Filament формы",
                    "Filament таблицы",
                    "Filament действия",
                    "Filament виджеты"
                ]
            }
            
            # Если фреймворк не указан, тестируем все
            frameworks_to_test = [framework] if framework else list(test_queries.keys())
            
            for test_framework in frameworks_to_test:
                if test_framework not in test_queries:
                    continue
                    
                logger.info(f"🔍 Тестируем фреймворк {test_framework}")
                
                for query in test_queries[test_framework]:
                    self._test_single_query(collection, query, test_framework)
                    
                logger.info("")
                
        except Exception as e:
            logger.error(f"Ошибка при тестировании поиска: {e}")
    
    def _test_single_query(self, collection, query: str, framework: str):
        """Тестирует один поисковый запрос"""
        try:
            # Создаем embedding для запроса
            query_embedding = self.embedder.encode([query]).tolist()
            
            # Поиск в коллекции
            results = collection.query(
                query_embeddings=query_embedding,
                n_results=3,
                where={"framework": framework},
                include=['metadatas', 'documents', 'distances']
            )
            
            if results['documents'][0]:
                logger.info(f"✅ '{query}' -> {len(results['documents'][0])} результатов")
                
                for i, (doc, meta, distance) in enumerate(zip(
                    results['documents'][0], 
                    results['metadatas'][0], 
                    results['distances'][0]
                )):
                    relevance = 1 - distance
                    section_title = meta.get('section_title', 'No title')
                    chunk_type = meta.get('chunk_type', 'unknown')
                    
                    logger.info(f"   {i+1}. {section_title} ({chunk_type}) - {relevance:.3f}")
                    logger.info(f"      {doc[:80]}...")
            else:
                logger.warning(f"❌ Результаты не найдены для: '{query}'")
                
        except Exception as e:
            logger.error(f"Ошибка при тестировании запроса '{query}': {e}")

def main():
    """Основная функция"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Универсальный индексатор документов для RAG систем")
    parser.add_argument('--mode', choices=['full', 'incremental', 'delta'], 
                       default='full', help='Режим индексации')
    parser.add_argument('--framework', type=str, help='Обработать только указанный фреймворк')
    parser.add_argument('--test', action='store_true', help='Запустить тесты качества поиска')
    parser.add_argument('--clear', action='store_true', help='Очистить все данные')
    parser.add_argument('--verify', action='store_true', help='Проверить результаты индексации')
    
    args = parser.parse_args()
    
    logger.info("🚀 Запуск универсального индексатора документов...")
    
    try:
        indexer = UniversalDocumentIndexer()
        
        if args.clear:
            indexer.clear_all_data()
            logger.info("✅ Данные очищены")
            return 0
        
        if args.verify:
            indexer._verify_indexing_results()
            return 0
        
        if args.test:
            indexer.test_search_quality(args.framework)
            return 0
        
        # Определяем режим индексации
        mode = IndexingMode(args.mode)
        
        # Обрабатываем документы
        if args.framework:
            # Обрабатываем только указанный фреймворк
            indexer.process_framework(args.framework, mode)
        else:
            # Обрабатываем все фреймворки
            indexer.process_all_frameworks(mode)
        
        # Тестируем качество поиска
        indexer.test_search_quality(args.framework)
        
        logger.info("🎉 Индексация завершена успешно!")
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        return 1
    
    return 0

if __name__ == '__main__':
    exit(main())
