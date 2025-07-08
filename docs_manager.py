#!/usr/bin/env python3
"""
Универсальный менеджер документации для RAG системы
Поддерживает множественные фреймворки через конфигурацию
"""

import os
import sys
import json
import yaml
import re
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import chromadb
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

@dataclass
class ChunkInfo:
    """Информация о чанке документации"""
    source: str
    heading: str
    content: str
    full_text: str
    framework: str
    metadata: Dict[str, Any]

class DocumentParser:
    """Базовый класс для парсинга документации"""
    
    def __init__(self, framework_config: Dict[str, Any]):
        self.config = framework_config
        self.framework = framework_config.get('prefix', 'unknown')
        
    def clean_content(self, content: str) -> str:
        """Очистка контента согласно настройкам"""
        cleaning = self.config.get('content_cleaning', {})
        
        # Удаляем frontmatter
        if cleaning.get('remove_frontmatter', True):
            content = re.sub(r'^---.*?---\s*', '', content, flags=re.DOTALL)
        
        # Удаляем Vue-специфичные элементы
        if cleaning.get('remove_vue_components', False):
            content = re.sub(r'<script.*?</script>', '', content, flags=re.DOTALL)
            content = re.sub(r'<style.*?</style>', '', content, flags=re.DOTALL)
            content = re.sub(r':::.*?:::', '', content, flags=re.DOTALL)
        
        # Удаляем HTML теги
        if cleaning.get('remove_html_tags', True):
            content = re.sub(r'<[^>]+>', '', content)
        
        # Удаляем script и style теги отдельно
        if cleaning.get('remove_script_tags', False):
            content = re.sub(r'<script.*?</script>', '', content, flags=re.DOTALL)
        if cleaning.get('remove_style_tags', False):
            content = re.sub(r'<style.*?</style>', '', content, flags=re.DOTALL)
            
        # Очищаем лишние пробелы
        content = re.sub(r'\n\s*\n', '\n\n', content)
        content = content.strip()
        
        return content
    
    def split_by_headers(self, content: str, source_file: str) -> List[ChunkInfo]:
        """Разбивает контент на чанки по заголовкам с улучшенной логикой"""
        chunks = []
        
        # Очищаем контент
        clean_text = self.clean_content(content)
        
        # Получаем настройки чанкинга
        chunk_settings = self.config.get('chunk_settings', {})
        min_chunk_size = chunk_settings.get('min_size', 200)  # Минимальный размер чанка
        max_chunk_size = chunk_settings.get('max_size', 2000)  # Максимальный размер чанка
        
        # Разбиваем по заголовкам (# ## ### ####)
        sections = re.split(r'\n(#{1,4}\s+.*?)\n', clean_text)
        
        current_heading = "Введение"
        current_content = ""
        accumulated_content = ""
        accumulated_heading = ""
        
        for i, section in enumerate(sections):
            if i == 0:
                # Первая секция до первого заголовка
                current_content = section.strip()
                continue
                
            if re.match(r'^#{1,4}\s+', section):
                # Это заголовок
                content_size = len(current_content.strip())
                
                if content_size > 0:
                    # Если контент слишком маленький, накапливаем его
                    if content_size < min_chunk_size:
                        if accumulated_content:
                            accumulated_content += f"\n\n{current_heading}\n{current_content.strip()}"
                        else:
                            accumulated_content = current_content.strip()
                            accumulated_heading = current_heading
                    else:
                        # Контент достаточного размера
                        if accumulated_content:
                            # Добавляем накопленный контент к текущему
                            full_content = f"{accumulated_content}\n\n{current_heading}\n{current_content.strip()}"
                            full_heading = f"{accumulated_heading} + {current_heading}"
                            
                            chunks.append(ChunkInfo(
                                source=source_file,
                                heading=full_heading,
                                content=full_content,
                                full_text=f"{full_heading}\n{full_content}",
                                framework=self.framework,
                                metadata={
                                    "type": self.config.get('type', 'markdown'),
                                    "size": len(full_content)
                                }
                            ))
                            accumulated_content = ""
                            accumulated_heading = ""
                        else:
                            # Просто добавляем текущий чанк
                            chunks.append(ChunkInfo(
                                source=source_file,
                                heading=current_heading,
                                content=current_content.strip(),
                                full_text=f"{current_heading}\n{current_content.strip()}",
                                framework=self.framework,
                                metadata={
                                    "type": self.config.get('type', 'markdown'),
                                    "size": content_size
                                }
                            ))
                
                # Обновляем текущий заголовок
                current_heading = section.strip()
                current_content = ""
            else:
                # Это контент для текущего заголовка
                current_content += "\n" + section
        
        # Обрабатываем последний чанк
        content_size = len(current_content.strip())
        if content_size > 0:
            if accumulated_content or content_size < min_chunk_size:
                # Добавляем к накопленному
                final_content = accumulated_content
                final_heading = accumulated_heading
                
                if current_content.strip():
                    if final_content:
                        final_content += f"\n\n{current_heading}\n{current_content.strip()}"
                        final_heading += f" + {current_heading}"
                    else:
                        final_content = current_content.strip()
                        final_heading = current_heading
                
                if len(final_content) >= min_chunk_size:
                    chunks.append(ChunkInfo(
                        source=source_file,
                        heading=final_heading,
                        content=final_content,
                        full_text=f"{final_heading}\n{final_content}",
                        framework=self.framework,
                        metadata={
                            "type": self.config.get('type', 'markdown'),
                            "size": len(final_content)
                        }
                    ))
            else:
                # Добавляем как отдельный чанк
                chunks.append(ChunkInfo(
                    source=source_file,
                    heading=current_heading,
                    content=current_content.strip(),
                    full_text=f"{current_heading}\n{current_content.strip()}",
                    framework=self.framework,
                    metadata={
                        "type": self.config.get('type', 'markdown'),
                        "size": content_size
                    }
                ))
        
        # Разбиваем слишком большие чанки
        final_chunks = []
        for chunk in chunks:
            if chunk.metadata['size'] > max_chunk_size:
                # Разбиваем большой чанк на части
                content_parts = chunk.content.split('\n\n')
                current_part = ""
                part_num = 1
                
                for part in content_parts:
                    if len(current_part) + len(part) > max_chunk_size and current_part:
                        final_chunks.append(ChunkInfo(
                            source=chunk.source,
                            heading=f"{chunk.heading} (часть {part_num})",
                            content=current_part.strip(),
                            full_text=f"{chunk.heading} (часть {part_num})\n{current_part.strip()}",
                            framework=chunk.framework,
                            metadata={
                                "type": chunk.metadata['type'],
                                "size": len(current_part.strip())
                            }
                        ))
                        current_part = part
                        part_num += 1
                    else:
                        current_part += "\n\n" + part if current_part else part
                
                if current_part:
                    final_chunks.append(ChunkInfo(
                        source=chunk.source,
                        heading=f"{chunk.heading} (часть {part_num})" if part_num > 1 else chunk.heading,
                        content=current_part.strip(),
                        full_text=f"{chunk.heading} (часть {part_num})\n{current_part.strip()}" if part_num > 1 else chunk.full_text,
                        framework=chunk.framework,
                        metadata={
                            "type": chunk.metadata['type'],
                            "size": len(current_part.strip())
                        }
                    ))
            else:
                final_chunks.append(chunk)
        
        return final_chunks

class DocumentationManager:
    """Основной менеджер документации"""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.config = self._load_config()
        self.embedder = None
        self.client = None
        self.collection = None
        
    def _load_config(self) -> Dict[str, Any]:
        """Загружает конфигурацию"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            print(f"❌ Конфигурационный файл {self.config_path} не найден")
            sys.exit(1)
        except yaml.YAMLError as e:
            print(f"❌ Ошибка в конфигурационном файле: {e}")
            sys.exit(1)
    
    def init_database(self):
        """Инициализация базы данных"""
        db_config = self.config['database']
        self.client = chromadb.PersistentClient(path=db_config['path'])
        
        try:
            self.collection = self.client.get_collection(db_config['collection_name'])
            print(f"✅ Подключились к существующей коллекции: {self.collection.count()} документов")
        except:
            self.collection = self.client.create_collection(db_config['collection_name'])
            print("✅ Создана новая коллекция")
    
    def init_embedder(self):
        """Инициализация модели эмбеддингов"""
        model_name = self.config['embeddings']['model']
        print(f"🤖 Инициализируем модель эмбеддингов: {model_name}")
        self.embedder = SentenceTransformer(model_name)
    
    def get_framework_files(self, framework_name: str) -> List[Path]:
        """Получает список файлов для обработки"""
        framework_config = self.config['frameworks'][framework_name]
        
        if not framework_config.get('enabled', True):
            print(f"⏭️ Фреймворк {framework_name} отключен")
            return []
        
        base_path = Path(framework_config['path'])
        if not base_path.exists():
            print(f"❌ Путь {base_path} не существует для {framework_name}")
            return []
        
        files = []
        patterns = framework_config.get('file_patterns', ['*.md'])
        exclude_patterns = framework_config.get('exclude_patterns', [])
        
        for pattern in patterns:
            for file_path in base_path.rglob(pattern):
                # Проверяем исключения
                should_exclude = False
                for exclude_pattern in exclude_patterns:
                    if file_path.match(exclude_pattern):
                        should_exclude = True
                        break
                
                if not should_exclude and file_path.is_file():
                    files.append(file_path)
        
        return files
    
    def process_framework(self, framework_name: str) -> List[ChunkInfo]:
        """Обрабатывает документацию одного фреймворка"""
        framework_config = self.config['frameworks'][framework_name]
        parser = DocumentParser(framework_config)
        
        files = self.get_framework_files(framework_name)
        print(f"📂 Найдено файлов для {framework_name}: {len(files)}")
        
        all_chunks = []
        base_path = Path(framework_config['path'])
        
        for file_path in tqdm(files, desc=f"Обработка {framework_name}"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Пропускаем слишком короткие файлы
                if len(content.strip()) < 100:
                    continue
                
                # Получаем относительный путь
                relative_path = file_path.relative_to(base_path)
                source_name = f"{framework_config['prefix']}/{relative_path}"
                
                # Парсим файл
                chunks = parser.split_by_headers(content, str(source_name))
                all_chunks.extend(chunks)
                
            except Exception as e:
                print(f"❌ Ошибка при обработке {file_path}: {e}")
                continue
        
        print(f"✅ Создано чанков для {framework_name}: {len(all_chunks)}")
        return all_chunks
    
    def add_chunks_to_db(self, chunks: List[ChunkInfo]):
        """Добавляет чанки в базу данных"""
        if not chunks:
            return
        
        current_count = self.collection.count()
        framework = chunks[0].framework
        
        print(f"💾 Добавляем {len(chunks)} чанков {framework} в базу данных...")
        
        for i, chunk in tqdm(enumerate(chunks), total=len(chunks), desc=f"Добавление {framework}"):
            try:
                embedding = self.embedder.encode(chunk.full_text).tolist()
                
                # Уникальный ID
                chunk_id = f"{framework}-chunk-{current_count + i}"
                
                self.collection.add(
                    ids=[chunk_id],
                    documents=[chunk.full_text],
                    metadatas=[{
                        "source": chunk.source,
                        "heading": chunk.heading,
                        "framework": chunk.framework,
                        "type": chunk.metadata.get("type", "markdown"),
                        "size": chunk.metadata.get("size", 0)
                    }],
                    embeddings=[embedding]
                )
                
            except Exception as e:
                print(f"❌ Ошибка при добавлении чанка {i}: {e}")
                continue
    
    def process_all_frameworks(self):
        """Обрабатывает все включенные фреймворки"""
        self.init_database()
        self.init_embedder()
        
        initial_count = self.collection.count()
        
        for framework_name, framework_config in self.config['frameworks'].items():
            if framework_config.get('enabled', True):
                print(f"\n🚀 Обработка {framework_config['name']}...")
                chunks = self.process_framework(framework_name)
                self.add_chunks_to_db(chunks)
        
        final_count = self.collection.count()
        added_count = final_count - initial_count
        
        print(f"\n✅ Обработка завершена!")
        print(f"📊 Добавлено документов: {added_count}")
        print(f"📚 Общее количество: {final_count}")
    
    def rebuild_database(self):
        """Полная перестройка базы данных"""
        print("🔄 Начинаем полную перестройка базы данных...")
        
        # Удаляем старую коллекцию
        db_config = self.config['database']
        try:
            self.client = chromadb.PersistentClient(path=db_config['path'])
            self.client.delete_collection(db_config['collection_name'])
            print("🗑️ Старая коллекция удалена")
        except:
            pass
        
        # Создаем новую
        self.collection = self.client.create_collection(db_config['collection_name'])
        print("🆕 Создана новая коллекция")
        
        # Обрабатываем все фреймворки
        self.process_all_frameworks()
    
    def get_stats(self):
        """Получает статистику базы данных"""
        if not self.collection:
            self.init_database()
        
        total_docs = self.collection.count()
        
        # Получаем образцы для анализа
        sample_size = min(1000, total_docs)
        sample_results = self.collection.get(limit=sample_size)
        
        # Подсчитываем по фреймворкам
        framework_counts = {}
        for metadata in sample_results["metadatas"]:
            framework = metadata.get("framework", "unknown")
            framework_counts[framework] = framework_counts.get(framework, 0) + 1
        
        # Экстраполируем на всю базу
        estimated_counts = {}
        for fw, count in framework_counts.items():
            estimated_counts[fw] = int((count / sample_size) * total_docs)
        
        return {
            "total_documents": total_docs,
            "frameworks": estimated_counts,
            "sample_size": sample_size
        }

def main():
    parser = argparse.ArgumentParser(description="Менеджер документации RAG системы")
    parser.add_argument("command", choices=["add", "rebuild", "stats"], 
                       help="Команда для выполнения")
    parser.add_argument("--config", default="config.yaml", 
                       help="Путь к конфигурационному файлу")
    parser.add_argument("--framework", 
                       help="Обработать только указанный фреймворк")
    
    args = parser.parse_args()
    
    manager = DocumentationManager(args.config)
    
    if args.command == "add":
        if args.framework:
            # Обработка одного фреймворка
            manager.init_database()
            manager.init_embedder()
            chunks = manager.process_framework(args.framework)
            manager.add_chunks_to_db(chunks)
        else:
            # Обработка всех фреймворков
            manager.process_all_frameworks()
    
    elif args.command == "rebuild":
        manager.rebuild_database()
    
    elif args.command == "stats":
        stats = manager.get_stats()
        print("\n📊 Статистика базы данных:")
        print(f"Всего документов: {stats['total_documents']}")
        print("По фреймворкам:")
        for framework, count in stats['frameworks'].items():
            print(f"  {framework.upper()}: {count}")

if __name__ == "__main__":
    main()
