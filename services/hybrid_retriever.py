#!/usr/bin/env python3
"""
Гибридный поиск (Dense + Sparse) для улучшения качества RAG
Комбинирует семантический поиск с лексическим для лучших результатов
"""

import logging
import re
from typing import List, Dict, Any, Tuple
from collections import Counter
import math
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)

class BM25Retriever:
    """Простая реализация BM25 для лексического поиска"""
    
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.documents = []
        self.doc_freqs = []
        self.idf = {}
        self.doc_len = []
        self.avgdl = 0
        
    def fit(self, documents: List[str]):
        """Обучает BM25 на корпусе документов"""
        self.documents = documents
        self.doc_len = [len(doc.split()) for doc in documents]
        self.avgdl = sum(self.doc_len) / len(self.doc_len) if self.doc_len else 0
        
        # Подсчитываем частоты терминов в документах
        self.doc_freqs = []
        df = Counter()
        
        for doc in documents:
            words = doc.lower().split()
            word_freq = Counter(words)
            self.doc_freqs.append(word_freq)
            
            # Подсчитываем document frequency для каждого слова
            for word in set(words):
                df[word] += 1
        
        # Вычисляем IDF для каждого термина
        num_docs = len(documents)
        for word, freq in df.items():
            self.idf[word] = math.log((num_docs - freq + 0.5) / (freq + 0.5))
    
    def search(self, query: str, top_k: int = 10) -> List[Tuple[int, float]]:
        """Выполняет BM25 поиск"""
        if not self.documents:
            return []
            
        query_words = query.lower().split()
        scores = []
        
        for doc_idx, doc_freq in enumerate(self.doc_freqs):
            score = 0
            doc_len = self.doc_len[doc_idx]
            
            for word in query_words:
                if word in doc_freq:
                    tf = doc_freq[word]
                    idf = self.idf.get(word, 0)
                    
                    # BM25 формула
                    numerator = tf * (self.k1 + 1)
                    denominator = tf + self.k1 * (1 - self.b + self.b * (doc_len / self.avgdl))
                    score += idf * (numerator / denominator)
            
            scores.append((doc_idx, score))
        
        # Сортируем по убыванию скора
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

class HybridRetriever:
    """
    Гибридный поиск, комбинирующий семантический и лексический поиск
    """
    
    def __init__(self, embedder, collection, config: Dict[str, Any]):
        self.embedder = embedder
        self.collection = collection
        self.config = config
        self.bm25_retrievers = {}  # Кэш BM25 для каждого фреймворка
        self.framework_documents = {}  # Кэш документов по фреймворкам
        
    def _get_or_create_bm25(self, framework: str = None) -> BM25Retriever:
        """Получает или создает BM25 ретривер для фреймворка"""
        cache_key = framework or "all"
        
        if cache_key not in self.bm25_retrievers:
            # Получаем документы для фреймворка
            where_filter = {"framework": framework} if framework else None
            
            try:
                results = self.collection.get(
                    where=where_filter,
                    include=['documents', 'metadatas']
                )
                
                if results['documents']:
                    documents = results['documents']
                    metadatas = results['metadatas']
                    
                    # Сохраняем документы и метаданные
                    self.framework_documents[cache_key] = {
                        'documents': documents,
                        'metadatas': metadatas
                    }
                    
                    # Создаем и обучаем BM25
                    bm25 = BM25Retriever()
                    bm25.fit(documents)
                    self.bm25_retrievers[cache_key] = bm25
                    
                    logger.info(f"Создан BM25 индекс для {framework or 'всех фреймворков'}: {len(documents)} документов")
                else:
                    logger.warning(f"Нет документов для создания BM25 индекса: {framework}")
                    return None
                    
            except Exception as e:
                logger.error(f"Ошибка создания BM25 индекса: {e}")
                return None
        
        return self.bm25_retrievers.get(cache_key)
    
    def _semantic_search(self, query: str, framework: str = None, max_results: int = 10) -> List[Dict]:
        """Семантический поиск через ChromaDB"""
        try:
            query_embedding = self.embedder.encode([query])
            
            where_filter = {"framework": framework} if framework else None
            
            results = self.collection.query(
                query_embeddings=query_embedding,
                n_results=max_results,
                where=where_filter
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
                        'semantic_score': 1 - distance,
                        'rank': i + 1,
                        'source': 'semantic'
                    })
            
            return documents
            
        except Exception as e:
            logger.error(f"Ошибка семантического поиска: {e}")
            return []
    
    def _lexical_search(self, query: str, framework: str = None, max_results: int = 10) -> List[Dict]:
        """Лексический поиск через BM25"""
        try:
            bm25 = self._get_or_create_bm25(framework)
            if not bm25:
                return []
            
            cache_key = framework or "all"
            framework_data = self.framework_documents.get(cache_key, {})
            
            if not framework_data:
                return []
            
            # Выполняем BM25 поиск
            bm25_results = bm25.search(query, max_results)
            
            documents = []
            for doc_idx, bm25_score in bm25_results:
                if doc_idx < len(framework_data['documents']):
                    documents.append({
                        'content': framework_data['documents'][doc_idx],
                        'metadata': framework_data['metadatas'][doc_idx],
                        'lexical_score': bm25_score,
                        'rank': len(documents) + 1,
                        'source': 'lexical'
                    })
            
            return documents
            
        except Exception as e:
            logger.error(f"Ошибка лексического поиска: {e}")
            return []
    
    def _normalize_scores(self, documents: List[Dict], score_key: str) -> List[Dict]:
        """Нормализует скоры в диапазон [0, 1]"""
        if not documents:
            return documents
        
        scores = [doc.get(score_key, 0) for doc in documents]
        min_score = min(scores)
        max_score = max(scores)
        
        if max_score == min_score:
            # Все скоры одинаковые
            for doc in documents:
                doc[f'normalized_{score_key}'] = 1.0
        else:
            for doc in documents:
                original_score = doc.get(score_key, 0)
                normalized = (original_score - min_score) / (max_score - min_score)
                doc[f'normalized_{score_key}'] = normalized
        
        return documents
    
    def _combine_results(self, semantic_results: List[Dict], lexical_results: List[Dict], 
                        alpha: float = 0.7) -> List[Dict]:
        """
        Комбинирует результаты семантического и лексического поиска
        alpha: вес семантического поиска (0.7 = 70% семантический, 30% лексический)
        """
        # Нормализуем скоры
        semantic_results = self._normalize_scores(semantic_results, 'semantic_score')
        lexical_results = self._normalize_scores(lexical_results, 'lexical_score')
        
        # Создаем словарь для быстрого поиска по содержимому
        combined_docs = {}
        
        # Добавляем семантические результаты
        for doc in semantic_results:
            content_hash = hash(doc['content'])
            combined_docs[content_hash] = {
                **doc,
                'normalized_semantic_score': doc.get('normalized_semantic_score', 0),
                'normalized_lexical_score': 0,
                'sources': ['semantic']
            }
        
        # Добавляем лексические результаты
        for doc in lexical_results:
            content_hash = hash(doc['content'])
            if content_hash in combined_docs:
                # Документ уже есть, обновляем лексический скор
                combined_docs[content_hash]['normalized_lexical_score'] = doc.get('normalized_lexical_score', 0)
                combined_docs[content_hash]['sources'].append('lexical')
            else:
                # Новый документ только из лексического поиска
                combined_docs[content_hash] = {
                    **doc,
                    'normalized_semantic_score': 0,
                    'normalized_lexical_score': doc.get('normalized_lexical_score', 0),
                    'sources': ['lexical']
                }
        
        # Вычисляем гибридный скор
        final_results = []
        for doc in combined_docs.values():
            semantic_score = doc.get('normalized_semantic_score', 0)
            lexical_score = doc.get('normalized_lexical_score', 0)
            
            # Гибридный скор: alpha * semantic + (1-alpha) * lexical
            hybrid_score = alpha * semantic_score + (1 - alpha) * lexical_score
            
            # Бонус за присутствие в обоих типах поиска
            if len(doc['sources']) > 1:
                hybrid_score *= 1.1  # 10% бонус
            
            doc['hybrid_score'] = hybrid_score
            doc['relevance_score'] = hybrid_score  # Для совместимости
            final_results.append(doc)
        
        # Сортируем по гибридному скору
        final_results.sort(key=lambda x: x['hybrid_score'], reverse=True)
        
        return final_results
    
    def search(self, query: str, framework: str = None, max_results: int = 5, 
               alpha: float = 0.7) -> List[Dict]:
        """
        Основной метод гибридного поиска
        
        Args:
            query: Поисковый запрос
            framework: Фильтр по фреймворку
            max_results: Максимальное количество результатов
            alpha: Вес семантического поиска (0.7 = 70% семантический, 30% лексический)
        
        Returns:
            Список документов с гибридными скорами
        """
        logger.info(f"🔍 HYBRID SEARCH: query='{query}', framework={framework}, alpha={alpha}")
        
        # Увеличиваем количество результатов для каждого типа поиска
        search_limit = max_results * 2
        
        # Выполняем семантический поиск
        semantic_results = self._semantic_search(query, framework, search_limit)
        logger.info(f"📊 SEMANTIC: найдено {len(semantic_results)} документов")
        
        # Выполняем лексический поиск
        lexical_results = self._lexical_search(query, framework, search_limit)
        logger.info(f"📊 LEXICAL: найдено {len(lexical_results)} документов")
        
        # Комбинируем результаты
        combined_results = self._combine_results(semantic_results, lexical_results, alpha)
        logger.info(f"📊 COMBINED: итого {len(combined_results)} уникальных документов")
        
        # Возвращаем топ результатов
        final_results = combined_results[:max_results]
        
        # Логируем топ результаты
        for i, doc in enumerate(final_results[:3], 1):
            sources = ', '.join(doc.get('sources', []))
            logger.info(f"📄 TOP {i}: hybrid_score={doc['hybrid_score']:.3f}, sources=[{sources}]")
        
        return final_results
    
    def clear_cache(self):
        """Очищает кэш BM25 индексов"""
        self.bm25_retrievers.clear()
        self.framework_documents.clear()
        logger.info("🗑️ Кэш гибридного поиска очищен")
    
    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику гибридного поиска"""
        return {
            'bm25_indexes': list(self.bm25_retrievers.keys()),
            'cached_frameworks': len(self.bm25_retrievers),
            'total_cached_documents': sum(
                len(data.get('documents', [])) 
                for data in self.framework_documents.values()
            )
        }
