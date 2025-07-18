#!/usr/bin/env python3
"""
Современный сервис разделения текста для RAG 2024
Реализует семантическое чанкинг с учетом контекста и перекрытий
"""

import re
import logging
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

@dataclass
class ChunkMetadata:
    """Метаданные для чанка"""
    chunk_id: str
    source_file: str
    framework: str
    section_title: str
    chunk_index: int
    total_chunks: int
    overlap_start: int
    overlap_end: int
    content_length: int
    
class TextSplitter(ABC):
    """Базовый класс для разделения текста"""
    
    def __init__(self, chunk_size: int = 1000, overlap_size: int = 200):
        self.chunk_size = chunk_size
        self.overlap_size = overlap_size
    
    @abstractmethod
    def split_text(self, text: str, metadata: Dict) -> List[Dict]:
        """Разделить текст на чанки"""
        pass

class SemanticTextSplitter(TextSplitter):
    """
    Семантическое разделение текста с учетом границ предложений,
    заголовков и блоков кода. Основано на лучших практиках RAG 2024.
    """
    
    def __init__(self, chunk_size: int = 1000, overlap_size: int = 200, 
                 min_chunk_size: int = 100):
        super().__init__(chunk_size, overlap_size)
        self.min_chunk_size = min_chunk_size
        
        # Приоритеты для разделения (чем выше, тем лучше)
        self.split_priorities = {
            'h1': 100,  # # Заголовок 1 уровня  
            'h2': 90,   # ## Заголовок 2 уровня
            'h3': 80,   # ### Заголовок 3 уровня
            'h4': 70,   # #### Заголовок 4 уровня
            'code_block': 60,  # ```код```
            'paragraph': 50,   # Двойной перенос строки
            'sentence': 40,    # Конец предложения
            'comma': 10,       # Запятая (последний вариант)
        }
    
    def split_text(self, text: str, metadata: Dict) -> List[Dict]:
        """
        Семантическое разделение текста на чанки с учетом структуры документа
        """
        logger.info(f"Начинаем семантическое разделение текста длиной {len(text)} символов")
        
        if len(text) <= self.chunk_size:
            return [self._create_chunk(text, metadata, 0, 1)]
        
        # Находим все потенциальные точки разделения
        split_points = self._find_split_points(text)
        
        # Создаем чанки с учетом семантических границ
        chunks = self._create_semantic_chunks(text, split_points, metadata)
        
        logger.info(f"Создано {len(chunks)} семантических чанков")
        return chunks
    
    def _find_split_points(self, text: str) -> List[Tuple[int, int, str]]:
        """
        Находит все возможные точки разделения с приоритетами
        Возвращает список (позиция, приоритет, тип)
        """
        split_points = []
        
        # Заголовки разных уровней
        for level in range(1, 5):
            pattern = rf'^#{{{level}}}\s+(.+)$'
            for match in re.finditer(pattern, text, re.MULTILINE):
                split_points.append((
                    match.start(), 
                    self.split_priorities[f'h{level}'], 
                    f'h{level}'
                ))
        
        # Блоки кода
        for match in re.finditer(r'^```[\s\S]*?^```$', text, re.MULTILINE):
            split_points.append((
                match.end(), 
                self.split_priorities['code_block'], 
                'code_block'
            ))
        
        # Параграфы (двойной перенос строки)
        for match in re.finditer(r'\n\s*\n', text):
            split_points.append((
                match.end(), 
                self.split_priorities['paragraph'], 
                'paragraph'
            ))
        
        # Концы предложений
        for match in re.finditer(r'[.!?]\s+(?=[A-ZА-Я])', text):
            split_points.append((
                match.end(), 
                self.split_priorities['sentence'], 
                'sentence'
            ))
        
        # Запятые (последний вариант)
        for match in re.finditer(r',\s+', text):
            split_points.append((
                match.end(), 
                self.split_priorities['comma'], 
                'comma'
            ))
        
        # Сортируем по позиции
        split_points.sort(key=lambda x: x[0])
        
        logger.debug(f"Найдено {len(split_points)} потенциальных точек разделения")
        return split_points
    
    def _create_semantic_chunks(self, text: str, split_points: List[Tuple[int, int, str]], 
                              metadata: Dict) -> List[Dict]:
        """
        Создает чанки с учетом семантических границ и перекрытий
        """
        chunks = []
        current_start = 0
        text_length = len(text)
        
        while current_start < text_length:
            # Ищем оптимальную точку разделения для чанка
            ideal_end = current_start + self.chunk_size
            
            if ideal_end >= text_length:
                # Последний чанк
                chunk_text = text[current_start:]
                if len(chunk_text.strip()) >= self.min_chunk_size:
                    chunks.append(self._create_chunk(
                        chunk_text, metadata, len(chunks), len(chunks) + 1
                    ))
                break
            
            # Находим лучшую точку разделения рядом с идеальной позицией
            best_split = self._find_best_split_point(
                split_points, current_start, ideal_end
            )
            
            # Определяем начало следующего чанка с учетом перекрытия
            chunk_end = best_split if best_split else ideal_end
            chunk_text = text[current_start:chunk_end]
            
            if len(chunk_text.strip()) >= self.min_chunk_size:
                chunks.append(self._create_chunk(
                    chunk_text, metadata, len(chunks), -1  # total_chunks заполним позже
                ))
            
            # Следующий чанк начинается с учетом перекрытия
            next_start = max(current_start + 1, chunk_end - self.overlap_size)
            current_start = next_start
        
        # Обновляем total_chunks для всех чанков
        total_chunks = len(chunks)
        for chunk in chunks:
            chunk['metadata']['total_chunks'] = total_chunks
        
        return chunks
    
    def _find_best_split_point(self, split_points: List[Tuple[int, int, str]], 
                             start: int, ideal_end: int) -> Optional[int]:
        """
        Находит лучшую точку разделения рядом с идеальной позицией
        """
        # Ищем точки разделения в окне вокруг идеальной позиции
        window_start = max(start + self.min_chunk_size, ideal_end - 200)
        window_end = ideal_end + 200
        
        candidates = [
            (pos, priority, split_type) 
            for pos, priority, split_type in split_points
            if window_start <= pos <= window_end
        ]
        
        if not candidates:
            return ideal_end
        
        # Выбираем точку с наивысшим приоритетом, ближайшую к идеальной позиции
        best_candidate = max(candidates, key=lambda x: (
            x[1],  # Приоритет
            -abs(x[0] - ideal_end)  # Близость к идеальной позиции (отрицательное расстояние)
        ))
        
        return best_candidate[0]
    
    def _create_chunk(self, text: str, metadata: Dict, chunk_index: int, 
                     total_chunks: int) -> Dict:
        """
        Создает словарь чанка с полными метаданными
        """
        # Извлекаем заголовок раздела из начала текста
        section_title = self._extract_section_title(text)
        
        chunk_metadata = ChunkMetadata(
            chunk_id=f"{metadata.get('source_file', 'unknown')}_{chunk_index}",
            source_file=metadata.get('source_file', 'unknown'),
            framework=metadata.get('framework', 'unknown'),
            section_title=section_title,
            chunk_index=chunk_index,
            total_chunks=total_chunks,
            overlap_start=0 if chunk_index == 0 else self.overlap_size,
            overlap_end=0 if chunk_index == total_chunks - 1 else self.overlap_size,
            content_length=len(text.strip())
        )
        
        return {
            'content': text.strip(),
            'metadata': {
                'chunk_id': chunk_metadata.chunk_id,
                'source_file': chunk_metadata.source_file,
                'framework': chunk_metadata.framework,
                'section_title': chunk_metadata.section_title,
                'chunk_index': chunk_metadata.chunk_index,
                'total_chunks': chunk_metadata.total_chunks,
                'overlap_start': chunk_metadata.overlap_start,
                'overlap_end': chunk_metadata.overlap_end,
                'content_length': chunk_metadata.content_length,
                'chunk_type': 'semantic'
            }
        }
    
    def _extract_section_title(self, text: str) -> str:
        """
        Извлекает заголовок раздела из начала текста
        """
        lines = text.strip().split('\n')
        
        for line in lines[:5]:  # Ищем в первых 5 строках
            line = line.strip()
            if line.startswith('#'):
                # Убираем # символы и возвращаем заголовок
                return re.sub(r'^#+\s*', '', line).strip()
        
        # Если заголовок не найден, берем первые слова
        first_line = lines[0].strip() if lines else ''
        words = first_line.split()[:8]  # Первые 8 слов
        return ' '.join(words) if words else 'Untitled Section'

class MarkdownAwareTextSplitter(SemanticTextSplitter):
    """
    Специализированный сплиттер для Markdown документации
    с пониманием специфических элементов Laravel/PHP
    """
    
    def __init__(self, chunk_size: int = 800, overlap_size: int = 150):
        super().__init__(chunk_size, overlap_size)
        
        # Добавляем специфичные для документации приоритеты
        self.split_priorities.update({
            'code_php': 85,      # PHP код блоки
            'code_shell': 83,    # Shell команды  
            'note_block': 75,    # > [!NOTE] блоки
            'list_item': 35,     # Элементы списков
        })
    
    def _find_split_points(self, text: str) -> List[Tuple[int, int, str]]:
        """
        Расширенный поиск точек разделения с учетом Markdown специфики
        """
        split_points = super()._find_split_points(text)
        
        # PHP код блоки
        for match in re.finditer(r'^```php[\s\S]*?^```$', text, re.MULTILINE):
            split_points.append((
                match.end(), 
                self.split_priorities['code_php'], 
                'code_php'
            ))
        
        # Shell команды
        for match in re.finditer(r'^```shell[\s\S]*?^```$', text, re.MULTILINE):
            split_points.append((
                match.end(), 
                self.split_priorities['code_shell'], 
                'code_shell'
            ))
        
        # Блоки примечаний
        for match in re.finditer(r'^>\s*\[!(?:NOTE|WARNING|TIP)\][\s\S]*?(?=\n\n|\n[^>]|$)', 
                                text, re.MULTILINE):
            split_points.append((
                match.end(), 
                self.split_priorities['note_block'], 
                'note_block'
            ))
        
        # Элементы списков
        for match in re.finditer(r'^[\s]*[-*+]\s+.+$', text, re.MULTILINE):
            split_points.append((
                match.end(), 
                self.split_priorities['list_item'], 
                'list_item'
            ))
        
        split_points.sort(key=lambda x: x[0])
        return split_points
    
    def preprocess_markdown(self, text: str) -> str:
        """
        Предварительная обработка Markdown для лучшего чанкинга
        """
        # Убираем ссылки на версии Laravel
        text = re.sub(r'/docs/\{\{version\}\}/', '/docs/', text)
        
        # Нормализуем пробелы и переносы строк
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Убираем HTML-якоря
        text = re.sub(r'<a name="[^"]*"></a>', '', text)
        
        return text.strip()

def get_text_splitter(framework: str = 'laravel', **kwargs) -> TextSplitter:
    """
    Фабричная функция для создания подходящего сплиттера
    """
    if framework in ['laravel', 'vue', 'filament']:
        return MarkdownAwareTextSplitter(**kwargs)
    else:
        return SemanticTextSplitter(**kwargs)