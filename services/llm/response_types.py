#!/usr/bin/env python3
"""
Типы ответов LLM и их специфичные артефакты для очистки
"""

from enum import Enum
from typing import List

class ResponseType(Enum):
    """Типы ответов для специализированной очистки"""
    RAG_TECHNICAL = "rag_technical"  # Технические вопросы по документации
    META_PROJECT = "meta_project"    # Мета-вопросы о проекте
    PROMPT_ENHANCEMENT = "prompt_enhancement"  # Улучшение промптов
    GENERAL = "general"              # Общие ответы

class ResponseArtifacts:
    """Константы артефактов для разных типов ответов"""
    
    # Общие артефакты для всех типов ответов
    COMMON = [
        r'Created\s+(Question|Answer|Query|Response).*?```',
        r'^(Human|Assistant|User|AI):\s*',
        r'```+\s*$',
        r'```\s*$',
    ]
    
    # Специфичные для мета-вопросов о проекте
    META_PROJECT = [
        r'===\s*(КОНТЕКСТ ПРОЕКТА|ТЕКУЩИЙ СТАТУС|ВОПРОС|ИНСТРУКЦИИ)\s*===.*?(?=\n\n|$)',
        r'\[\s*(Контекст проекта|Активный контекст|Вопрос пользователя|Инструкции)\s*\].*?(?=\n\n|$)',
        r'^ОТВЕТ:\s*',
        r'===\s*ОТВЕТ\s*===\s*',
        r'===\s*ИНС.*?$',  # Обрезанные инструкции
        r'^---\s*$',       # Разделители
        r'===\s*',         # Любые остаточные === маркеры
        r'Какой.*?\?',     # Вопросы типа "Какой язык используется"
        r'Ответь на вопрос.*?(?=\n\n|$)',  # Инструкции ответа
        r'Python 3\.8\+, JavaScript и TypeScript.*?(?=\n\n|$)',  # Специфичные повторения
        r'FastAPI, MCP Protocol, ChromaDB.*?(?=\n\n|$)',  # Специфичные повторения
    ]
    
    # Специфичные для RAG технических ответов
    RAG_TECHNICAL = [
        r'\[.*?\s+Documentation Context\]',
        r'Document content:.*?(?=\n\n|$)',
        r'Based on the documentation.*?(?=\n\n|$)',
        r'^Context:\s*',
        r'According to the Laravel documentation.*?(?=\n\n|$)',
        r'The documentation states.*?(?=\n\n|$)',
        r'```\s*\n\s*```',  # Пустые блоки кода
        r'Question:\s*.*?\n\nAnswer:\s*',  # Q&A паттерны
        r'---\s*\n\s*---',  # Пустые разделители
    ]
    
    # Специфичные для улучшения промптов
    PROMPT_ENHANCEMENT = [
        r'<\|begin_of_text\|>.*?<\|end_of_text\|>',
        r'<\|start_header_id\|>.*?<\|end_header_id\|>',
        r'<\|eot_id\|>',
        r'Исходный запрос:.*?(?=\n\n|$)',
        r'Улучшенный запрос:.*?(?=\n\n|$)',
        r'Детализированный запрос:.*?(?=\n\n|$)',
        r'```\s*enhancement.*?```',
        r'```\s*original.*?```',
    ]
    
    # Общие повторяющиеся фразы
    REPETITIVE_PHRASES = [
        r'Для получения дополнительной информации.*?(?=\n\n|$)',
        r'Подробнее можно прочитать в документации.*?(?=\n\n|$)',
        r'Дополнительную информацию.*?(?=\n\n|$)',
        r'Более подробную информацию.*?(?=\n\n|$)',
        r'См\. документацию.*?(?=\n\n|$)',
        r'Подробнее.*?в официальной документации.*?(?=\n\n|$)',
        r'\[https?://[^\]]+\]',  # Простые ссылки
    ]
    
    # Артефакты незавершенных ответов
    INCOMPLETE_RESPONSES = [
        r'\.{3,}\s*$',     # Многоточия в конце
        r'\w+\.\.\.\s*$',  # Слово с многоточием
        r'и т\.?\s*д\.?\s*$',  # "и т.д." в конце
        r'etc\.?\s*$',     # "etc." в конце
        r'\w+\s*\.\s*$',   # Незавершенное предложение
    ]

def get_artifacts_for_type(response_type: ResponseType) -> List[str]:
    """Получить список артефактов для конкретного типа ответа"""
    artifacts = ResponseArtifacts.COMMON.copy()
    
    if response_type == ResponseType.META_PROJECT:
        artifacts.extend(ResponseArtifacts.META_PROJECT)
    elif response_type == ResponseType.RAG_TECHNICAL:
        artifacts.extend(ResponseArtifacts.RAG_TECHNICAL)
    elif response_type == ResponseType.PROMPT_ENHANCEMENT:
        artifacts.extend(ResponseArtifacts.PROMPT_ENHANCEMENT)
    
    # Добавляем общие артефакты для всех типов
    artifacts.extend(ResponseArtifacts.REPETITIVE_PHRASES)
    artifacts.extend(ResponseArtifacts.INCOMPLETE_RESPONSES)
    
    return artifacts