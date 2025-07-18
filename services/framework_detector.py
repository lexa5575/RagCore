#!/usr/bin/env python3
"""
Улучшенная система автоопределения фреймворков
Использует множественные эвристики для точного определения фреймворка
"""

import re
import logging
from typing import Optional, Dict, List, Tuple
from collections import Counter

logger = logging.getLogger(__name__)

class FrameworkDetector:
    """Улучшенная система автоопределения фреймворков"""
    
    def __init__(self):
        # Ключевые слова для каждого фреймворка с весами
        self.framework_keywords = {
            'laravel': {
                # Высокий приоритет (вес 3)
                'artisan': 3, 'eloquent': 3, 'blade': 3, 'composer': 3,
                'migration': 3, 'middleware': 3, 'route': 3, 'controller': 3,
                'model': 2, 'php': 2, 'namespace': 2, 'use': 2,
                # Средний приоритет (вес 2)
                'app\\': 2, 'illuminate\\': 2, 'database\\': 2, 'config\\': 2,
                'storage\\': 2, 'resources\\': 2, 'public\\': 2,
                # Низкий приоритет (вес 1)
                'laravel': 1, 'framework': 1, 'php framework': 1,
                'web artisan': 1, 'tinker': 1, 'forge': 1, 'vapor': 1
            },
            'vue': {
                # Высокий приоритет
                'vue': 3, 'composition api': 3, 'reactive': 3, 'ref': 3,
                'computed': 3, 'watch': 3, 'onmounted': 3, 'setup': 3,
                '<template>': 3, '<script>': 3, 'v-if': 3, 'v-for': 3,
                # Средний приоритет
                'component': 2, 'props': 2, 'emit': 2, 'slot': 2,
                'directive': 2, 'mixin': 2, 'plugin': 2, 'router': 2,
                # Низкий приоритет
                'javascript': 1, 'typescript': 1, 'npm': 1, 'yarn': 1,
                'vite': 1, 'webpack': 1, 'nuxt': 1
            },
            'filament': {
                # Высокий приоритет
                'filament': 3, 'resource': 3, 'form': 3, 'table': 3,
                'action': 3, 'widget': 3, 'page': 3, 'panel': 3,
                # Средний приоритет
                'livewire': 2, 'alpine': 2, 'tailwind': 2, 'relation': 2,
                'field': 2, 'column': 2, 'filter': 2, 'bulk action': 2,
                # Низкий приоритет
                'admin': 1, 'dashboard': 1, 'crud': 1, 'management': 1
            },
            'alpine': {
                # Высокий приоритет
                'alpine': 3, 'x-data': 3, 'x-show': 3, 'x-if': 3,
                'x-for': 3, 'x-model': 3, 'x-click': 3, 'x-init': 3,
                # Средний приоритет
                'alpine.js': 2, 'alpinejs': 2, 'x-text': 2, 'x-html': 2,
                'x-bind': 2, 'x-on': 2, 'x-ref': 2, 'x-cloak': 2,
                # Низкий приоритет
                'lightweight': 1, 'javascript framework': 1, 'reactive': 1
            },
            'inertia': {
                # Высокий приоритет
                'inertia': 3, 'inertiajs': 3, 'visit': 3, 'router': 3,
                'link': 3, 'form': 3, 'page': 3, 'props': 3,
                # Средний приоритет
                'spa': 2, 'single page': 2, 'adapter': 2, 'middleware': 2,
                'response': 2, 'request': 2, 'redirect': 2,
                # Низкий приоритет
                'modern': 1, 'monolith': 1, 'hybrid': 1
            },
            'tailwindcss': {
                # Высокий приоритет
                'tailwind': 3, 'tailwindcss': 3, 'utility': 3, 'class': 3,
                'responsive': 3, 'hover': 3, 'focus': 3, 'dark': 3,
                # Средний приоритет
                'variant': 2, 'modifier': 2, 'prefix': 2, 'purge': 2,
                'jit': 2, 'config': 2, 'theme': 2, 'plugin': 2,
                # Низкий приоритет
                'css': 1, 'framework': 1, 'styling': 1, 'design': 1
            }
        }
        
        # Паттерны для более точного определения
        self.framework_patterns = {
            'laravel': [
                r'php\s+artisan\s+',
                r'use\s+Illuminate\\',
                r'namespace\s+App\\',
                r'Route::[a-zA-Z]+\(',
                r'Schema::[a-zA-Z]+\(',
                r'Eloquent::[a-zA-Z]+\(',
                r'@extends\s*\(',
                r'@section\s*\(',
                r'{{.*}}',  # Blade syntax
                r'composer\s+require',
                r'artisan\s+make:'
            ],
            'vue': [
                r'<template[^>]*>',
                r'<script[^>]*>',
                r'export\s+default\s*{',
                r'Vue\.component\(',
                r'new\s+Vue\(',
                r'v-[a-zA-Z-]+\s*=',
                r'ref\s*\(',
                r'reactive\s*\(',
                r'computed\s*\(',
                r'onMounted\s*\(',
                r'defineComponent\s*\('
            ],
            'filament': [
                r'Filament\\',
                r'->resource\(',
                r'->form\(',
                r'->table\(',
                r'->action\(',
                r'->widget\(',
                r'->page\(',
                r'Forms\\Components\\',
                r'Tables\\Columns\\',
                r'Tables\\Actions\\'
            ],
            'alpine': [
                r'x-data\s*=',
                r'x-show\s*=',
                r'x-if\s*=',
                r'x-for\s*=',
                r'x-model\s*=',
                r'x-click\s*=',
                r'x-init\s*=',
                r'Alpine\.start\(',
                r'Alpine\.data\('
            ],
            'inertia': [
                r'Inertia\.',
                r'inertia\(',
                r'->inertia\(',
                r'usePage\(',
                r'useForm\(',
                r'router\.visit\(',
                r'router\.get\(',
                r'router\.post\(',
                r'@inertiaHead'
            ],
            'tailwindcss': [
                r'@apply\s+',
                r'@tailwind\s+',
                r'@layer\s+',
                r'@responsive\s+',
                r'@variants\s+',
                r'tailwind\.config\.',
                r'class\s*=\s*["\'][^"\']*(?:bg-|text-|p-|m-|w-|h-)',
                r'className\s*=\s*["\'][^"\']*(?:bg-|text-|p-|m-|w-|h-)'
            ]
        }
        
        # Контекстные подсказки
        self.context_hints = {
            'laravel': ['php', 'backend', 'server', 'api', 'database', 'mvc'],
            'vue': ['frontend', 'spa', 'component', 'reactive', 'ui'],
            'filament': ['admin', 'panel', 'crud', 'management', 'dashboard'],
            'alpine': ['lightweight', 'minimal', 'progressive', 'enhancement'],
            'inertia': ['spa', 'hybrid', 'modern', 'monolith', 'adapter'],
            'tailwindcss': ['css', 'styling', 'utility', 'design', 'responsive']
        }
    
    def detect_framework_from_question(self, question: str) -> Optional[str]:
        """Определяет фреймворк на основе вопроса"""
        question_lower = question.lower()
        framework_scores = {}
        
        # Подсчитываем скоры по ключевым словам
        for framework, keywords in self.framework_keywords.items():
            score = 0
            for keyword, weight in keywords.items():
                if keyword.lower() in question_lower:
                    score += weight
            framework_scores[framework] = score
        
        # Проверяем паттерны
        for framework, patterns in self.framework_patterns.items():
            for pattern in patterns:
                if re.search(pattern, question, re.IGNORECASE):
                    framework_scores[framework] = framework_scores.get(framework, 0) + 5
        
        # Находим фреймворк с максимальным скором
        if framework_scores:
            best_framework = max(framework_scores, key=framework_scores.get)
            best_score = framework_scores[best_framework]
            
            # Минимальный порог для определения
            if best_score >= 2:
                logger.info(f"🎯 FRAMEWORK DETECTED: {best_framework} (score: {best_score})")
                return best_framework
        
        logger.info("🤷 FRAMEWORK: не удалось определить фреймворк")
        return None
    
    def detect_framework_from_context(self, file_path: str = None, 
                                    file_content: str = None) -> Optional[str]:
        """Определяет фреймворк на основе контекста файла"""
        framework_scores = {}
        
        # Анализ пути к файлу
        if file_path:
            path_lower = file_path.lower()
            
            # Прямые индикаторы в пути
            path_indicators = {
                'laravel': ['laravel', 'artisan', 'app/', 'config/', 'database/', 'routes/'],
                'vue': ['vue', '.vue', 'components/', 'pages/', 'nuxt/', 'vite.config'],
                'filament': ['filament', 'admin/', 'panel/', 'resources/'],
                'alpine': ['alpine', 'alpinejs'],
                'inertia': ['inertia', 'inertiajs'],
                'tailwindcss': ['tailwind', 'tailwind.config', 'postcss.config']
            }
            
            for framework, indicators in path_indicators.items():
                for indicator in indicators:
                    if indicator in path_lower:
                        framework_scores[framework] = framework_scores.get(framework, 0) + 3
        
        # Анализ содержимого файла
        if file_content:
            content_lower = file_content.lower()
            
            # Подсчитываем скоры по ключевым словам
            for framework, keywords in self.framework_keywords.items():
                score = 0
                for keyword, weight in keywords.items():
                    count = content_lower.count(keyword.lower())
                    score += count * weight
                framework_scores[framework] = framework_scores.get(framework, 0) + score
            
            # Проверяем паттерны
            for framework, patterns in self.framework_patterns.items():
                for pattern in patterns:
                    matches = len(re.findall(pattern, file_content, re.IGNORECASE))
                    framework_scores[framework] = framework_scores.get(framework, 0) + matches * 5
        
        # Находим фреймворк с максимальным скором
        if framework_scores:
            best_framework = max(framework_scores, key=framework_scores.get)
            best_score = framework_scores[best_framework]
            
            if best_score >= 5:
                logger.info(f"🎯 CONTEXT FRAMEWORK: {best_framework} (score: {best_score})")
                return best_framework
        
        return None
    
    def detect_framework_comprehensive(self, question: str, file_path: str = None, 
                                     file_content: str = None, 
                                     context: str = None) -> Optional[str]:
        """Комплексное определение фреймворка с использованием всех доступных данных"""
        framework_scores = Counter()
        
        # Анализ вопроса
        question_framework = self.detect_framework_from_question(question)
        if question_framework:
            framework_scores[question_framework] += 10
        
        # Анализ контекста файла
        context_framework = self.detect_framework_from_context(file_path, file_content)
        if context_framework:
            framework_scores[context_framework] += 8
        
        # Анализ дополнительного контекста
        if context:
            context_framework = self.detect_framework_from_question(context)
            if context_framework:
                framework_scores[context_framework] += 5
        
        # Дополнительные эвристики
        combined_text = ' '.join(filter(None, [question, file_content, context]))
        if combined_text:
            # Проверяем контекстные подсказки
            for framework, hints in self.context_hints.items():
                for hint in hints:
                    if hint in combined_text.lower():
                        framework_scores[framework] += 1
        
        # Возвращаем фреймворк с максимальным скором
        if framework_scores:
            best_framework = framework_scores.most_common(1)[0][0]
            best_score = framework_scores[best_framework]
            
            if best_score >= 3:
                logger.info(f"🎯 COMPREHENSIVE DETECTION: {best_framework} (score: {best_score})")
                return best_framework
        
        logger.info("🤷 COMPREHENSIVE: не удалось определить фреймворк")
        return None
    
    def get_framework_confidence(self, question: str, detected_framework: str) -> float:
        """Возвращает уверенность в определении фреймворка (0.0 - 1.0)"""
        if not detected_framework:
            return 0.0
        
        question_lower = question.lower()
        framework_keywords = self.framework_keywords.get(detected_framework, {})
        
        # Подсчитываем совпадения
        matches = 0
        total_weight = 0
        
        for keyword, weight in framework_keywords.items():
            if keyword.lower() in question_lower:
                matches += weight
            total_weight += weight
        
        # Проверяем паттерны
        patterns = self.framework_patterns.get(detected_framework, [])
        pattern_matches = 0
        for pattern in patterns:
            if re.search(pattern, question, re.IGNORECASE):
                pattern_matches += 1
        
        # Вычисляем уверенность
        keyword_confidence = matches / max(total_weight, 1) if total_weight > 0 else 0
        pattern_confidence = min(pattern_matches / max(len(patterns), 1), 1.0) if patterns else 0
        
        # Комбинированная уверенность
        confidence = (keyword_confidence * 0.7 + pattern_confidence * 0.3)
        
        return min(confidence, 1.0)
    
    def get_supported_frameworks(self) -> List[str]:
        """Возвращает список поддерживаемых фреймворков"""
        return list(self.framework_keywords.keys())
    
    def get_framework_stats(self) -> Dict[str, Dict[str, int]]:
        """Возвращает статистику по фреймворкам"""
        stats = {}
        for framework, keywords in self.framework_keywords.items():
            stats[framework] = {
                'keywords_count': len(keywords),
                'patterns_count': len(self.framework_patterns.get(framework, [])),
                'context_hints_count': len(self.context_hints.get(framework, []))
            }
        return stats
