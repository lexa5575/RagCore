#!/usr/bin/env python3
"""
Кэширование embeddings для ускорения повторных запросов
"""

import hashlib
import pickle
import logging
from typing import Optional, Dict, Any
from pathlib import Path
import numpy as np

logger = logging.getLogger(__name__)

class EmbeddingCache:
    """Кэш для embeddings с персистентным хранением"""
    
    def __init__(self, cache_dir: str = "./embedding_cache", max_size: int = 10000):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.max_size = max_size
        self.memory_cache = {}
        self.cache_stats = {"hits": 0, "misses": 0, "disk_hits": 0}
        
    def _get_cache_key(self, text: str) -> str:
        """Генерирует ключ кэша для текста"""
        return hashlib.md5(text.encode('utf-8')).hexdigest()
    
    def _get_cache_file(self, cache_key: str) -> Path:
        """Возвращает путь к файлу кэша"""
        return self.cache_dir / f"{cache_key}.pkl"
    
    def get_embedding(self, text: str) -> Optional[np.ndarray]:
        """Получает embedding из кэша"""
        cache_key = self._get_cache_key(text)
        
        # Проверяем memory cache
        if cache_key in self.memory_cache:
            self.cache_stats["hits"] += 1
            return self.memory_cache[cache_key]
        
        # Проверяем disk cache
        cache_file = self._get_cache_file(cache_key)
        if cache_file.exists():
            try:
                with open(cache_file, 'rb') as f:
                    embedding = pickle.load(f)
                    self.memory_cache[cache_key] = embedding
                    self.cache_stats["disk_hits"] += 1
                    return embedding
            except Exception as e:
                logger.warning(f"Ошибка чтения кэша {cache_file}: {e}")
        
        self.cache_stats["misses"] += 1
        return None
    
    def set_embedding(self, text: str, embedding: np.ndarray):
        """Сохраняет embedding в кэш"""
        cache_key = self._get_cache_key(text)
        
        # Сохраняем в memory cache
        if len(self.memory_cache) >= self.max_size:
            # Удаляем старые записи (простая FIFO стратегия)
            oldest_key = next(iter(self.memory_cache))
            del self.memory_cache[oldest_key]
        
        self.memory_cache[cache_key] = embedding
        
        # Сохраняем на диск
        cache_file = self._get_cache_file(cache_key)
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump(embedding, f)
        except Exception as e:
            logger.warning(f"Ошибка записи кэша {cache_file}: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику кэша"""
        total_requests = sum(self.cache_stats.values())
        hit_rate = (self.cache_stats["hits"] + self.cache_stats["disk_hits"]) / max(total_requests, 1)
        
        return {
            **self.cache_stats,
            "memory_cache_size": len(self.memory_cache),
            "disk_cache_files": len(list(self.cache_dir.glob("*.pkl"))),
            "hit_rate": hit_rate
        }
    
    def clear_cache(self):
        """Очищает весь кэш"""
        self.memory_cache.clear()
        for cache_file in self.cache_dir.glob("*.pkl"):
            cache_file.unlink()
        self.cache_stats = {"hits": 0, "misses": 0, "disk_hits": 0}
