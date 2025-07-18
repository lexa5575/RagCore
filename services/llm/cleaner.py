#!/usr/bin/env python3
"""
Модуль для очистки ответов LLM от артефактов генерации
Рефакторированная версия с модульной архитектурой
"""

import re
import logging
from typing import Optional, Dict, Any

from .response_types import ResponseType, get_artifacts_for_type

logger = logging.getLogger(__name__)

class LLMResponseCleaner:
    """Класс для очистки ответов LLM с поддержкой разных типов"""
    
    def __init__(self):
        """Инициализация очистителя ответов"""
        self.stats = {
            'total_cleaned': 0,
            'by_type': {t.value: 0 for t in ResponseType}
        }
    
    def clean_response(self, response: str, response_type: ResponseType = ResponseType.GENERAL,
                      metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Основной метод для очистки ответа LLM
        
        Args:
            response: Исходный ответ от LLM
            response_type: Тип ответа для специализированной очистки
            metadata: Дополнительные метаданные для контекста
        
        Returns:
            Очищенный ответ
        """
        if not response or not response.strip():
            return ""
        
        original_length = len(response)
        logger.debug(f"Начинаем очистку ответа типа {response_type.value}, исходная длина: {original_length}")
        
        # Получаем артефакты для конкретного типа
        artifacts = get_artifacts_for_type(response_type)
        
        # Применяем очистку от артефактов
        cleaned = self._apply_artifact_cleaning(response, artifacts)
        
        # Применяем специализированную очистку по типу
        if response_type == ResponseType.META_PROJECT:
            cleaned = self._clean_meta_project_response(cleaned)
        elif response_type == ResponseType.RAG_TECHNICAL:
            cleaned = self._clean_rag_technical_response(cleaned)
        elif response_type == ResponseType.PROMPT_ENHANCEMENT:
            cleaned = self._clean_prompt_enhancement_response(cleaned)
        else:
            cleaned = self._clean_general_response(cleaned)
        
        # Применяем финальную обработку
        cleaned = self._apply_final_processing(cleaned)
        
        # Обновляем статистику
        self.stats['total_cleaned'] += 1
        self.stats['by_type'][response_type.value] += 1
        
        logger.debug(f"Очистка завершена, новая длина: {len(cleaned)}")
        return cleaned
    
    def _apply_artifact_cleaning(self, response: str, artifacts: list) -> str:
        """Применяем очистку от артефактов"""
        for pattern in artifacts:
            try:
                response = re.sub(pattern, '', response, flags=re.DOTALL | re.IGNORECASE | re.MULTILINE)
            except re.error as e:
                logger.warning(f"Ошибка в регулярном выражении '{pattern}': {e}")
                continue
        return response
    
    def _clean_meta_project_response(self, response: str) -> str:
        """Специализированная очистка для мета-вопросов о проекте"""
        logger.debug("Применяем очистку для мета-вопросов о проекте")
        
        # Удаляем повторяющиеся строки (особенно важно для мета-вопросов)
        response = self._remove_duplicate_lines(response)
        
        # Ограничиваем длину для мета-вопросов
        response = self._limit_response_length(response, max_length=1500)
        
        return response
    
    def _clean_rag_technical_response(self, response: str) -> str:
        """Специализированная очистка для RAG технических ответов"""
        logger.debug("Применяем очистку для RAG технических ответов")
        
        # Удаляем повторяющиеся блоки вопросов и ответов
        response = self._remove_repeated_qa_blocks(response)
        
        # Очищаем повторяющиеся блоки кода
        response = self._remove_duplicate_code_blocks(response)
        
        # Исправляем обрывы на середине предложений
        response = self._fix_sentence_breaks(response)
        
        return response
    
    def _clean_prompt_enhancement_response(self, response: str) -> str:
        """Специализированная очистка для улучшения промптов"""
        logger.debug("Применяем очистку для улучшения промптов")
        
        # Специфичная очистка для улучшения промптов
        enhancement_artifacts = [
            r'Enhanced prompt:.*?(?=\n\n|$)',
            r'Improvements:.*?(?=\n\n|$)',
            r'Added context:.*?(?=\n\n|$)',
        ]
        
        for pattern in enhancement_artifacts:
            response = re.sub(pattern, '', response, flags=re.DOTALL | re.IGNORECASE)
        
        return response
    
    def _clean_general_response(self, response: str) -> str:
        """Общая очистка для любых ответов"""
        logger.debug("Применяем общую очистку")
        return response
    
    def _apply_final_processing(self, response: str) -> str:
        """Финальная обработка ответа"""
        
        # Обрезаем пробелы в начале и конце
        response = response.strip()
        
        # Удаляем лишние переносы строк
        response = re.sub(r'\n{3,}', '\n\n', response)
        
        # Удаляем пробелы в конце строк
        response = re.sub(r' +$', '', response, flags=re.MULTILINE)
        
        # Удаляем лишние пустые строки в конце
        while response.endswith('\n\n\n'):
            response = response[:-1]
        
        # Исправляем неправильные переносы строк в коде
        response = self._fix_code_formatting(response)
        
        # Если ответ пустой, возвращаем заглушку
        if not response:
            response = "Извините, не удалось сформировать ответ."
        
        return response
    
    def _remove_duplicate_lines(self, text: str) -> str:
        """Удаление повторяющихся строк"""
        lines = text.split('\n')
        seen = set()
        result = []
        
        for line in lines:
            line_stripped = line.strip()
            if line_stripped and line_stripped not in seen:
                seen.add(line_stripped)
                result.append(line)
            elif not line_stripped:  # Пустые строки оставляем
                result.append(line)
        
        return '\n'.join(result)
    
    def _limit_response_length(self, text: str, max_length: int = 1500) -> str:
        """Ограничение длины ответа"""
        if len(text) <= max_length:
            return text
        
        # Обрезаем по границе предложения
        truncated = text[:max_length]
        last_sentence_end = max(
            truncated.rfind('.'),
            truncated.rfind('!'),
            truncated.rfind('?')
        )
        
        if last_sentence_end > max_length * 0.7:  # Если нашли границу не слишком близко к началу
            return truncated[:last_sentence_end + 1]
        else:
            return truncated + "..."
    
    def _remove_repeated_qa_blocks(self, text: str) -> str:
        """Удаление повторяющихся блоков вопросов и ответов"""
        # Паттерн для блоков Q&A
        qa_pattern = r'(Question:.*?Answer:.*?)(?=\n\n|Question:|$)'
        blocks = re.findall(qa_pattern, text, re.DOTALL | re.IGNORECASE)
        
        if len(blocks) <= 1:
            return text
        
        # Удаляем дубликаты, оставляя только первый
        seen_blocks = set()
        unique_blocks = []
        
        for block in blocks:
            block_normalized = re.sub(r'\s+', ' ', block.strip().lower())
            if block_normalized not in seen_blocks:
                seen_blocks.add(block_normalized)
                unique_blocks.append(block)
        
        # Заменяем в тексте
        if unique_blocks:
            text = re.sub(qa_pattern, '', text, flags=re.DOTALL | re.IGNORECASE)
            text = text + '\n\n' + '\n\n'.join(unique_blocks)
        
        return text
    
    def _remove_duplicate_code_blocks(self, text: str) -> str:
        """Удаление дублирующихся блоков кода"""
        # Паттерн для блоков кода
        code_pattern = r'```[^`]*?```'
        code_blocks = re.findall(code_pattern, text, re.DOTALL)
        
        if len(code_blocks) <= 1:
            return text
        
        # Удаляем дубликаты
        seen_blocks = set()
        for block in code_blocks:
            block_normalized = re.sub(r'\s+', ' ', block.strip())
            if block_normalized in seen_blocks:
                text = text.replace(block, '', 1)
            else:
                seen_blocks.add(block_normalized)
        
        return text
    
    def _fix_sentence_breaks(self, text: str) -> str:
        """Исправление обрывов предложений"""
        # Удаляем обрывы в середине предложений
        text = re.sub(r'(\w+)\s*\.\s*$', r'\1.', text, flags=re.MULTILINE)
        
        # Исправляем незавершенные предложения
        incomplete_patterns = [
            r'\.{3,}\s*$',     # Многоточия в конце
            r'\w+\.\.\.\s*$',  # Слово с многоточием
            r'и т\.?\s*д\.?\s*$',  # "и т.д." в конце
            r'etc\.?\s*$',     # "etc." в конце
        ]
        
        for pattern in incomplete_patterns:
            text = re.sub(pattern, '.', text, flags=re.MULTILINE)
        
        return text
    
    def _fix_code_formatting(self, text: str) -> str:
        """Исправление форматирования кода"""
        # Исправляем разорванные блоки кода
        text = re.sub(r'```\s*```', '```\ncode\n```', text)
        
        # Исправляем блоки кода без языка
        text = re.sub(r'```\s*\n', '```\n', text)
        
        return text
    
    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику очистки"""
        return self.stats.copy()
    
    def reset_stats(self):
        """Сброс статистики"""
        self.stats = {
            'total_cleaned': 0,
            'by_type': {t.value: 0 for t in ResponseType}
        }


# Глобальный экземпляр для использования в проекте
_response_cleaner = None

def get_response_cleaner() -> LLMResponseCleaner:
    """Получение глобального экземпляра очистителя ответов"""
    global _response_cleaner
    if _response_cleaner is None:
        _response_cleaner = LLMResponseCleaner()
    return _response_cleaner

def clean_llm_response(response: str, response_type=None) -> str:
    """
    Простая функция очистки ответа - убираем только лишние пробелы
    """
    if not response:
        return ""
    
    # Только базовая очистка
    response = response.strip()
    
    # Убираем лишние переносы строк
    response = re.sub(r'\n{3,}', '\n\n', response)
    
    return response