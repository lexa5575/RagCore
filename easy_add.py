#!/usr/bin/env python3
"""
🚀 EasyAdd - Магическая кнопка для добавления документации в RAG систему
Автоопределение типа документации, автодобавление в конфиг, одна команда для всего!

Использование:
    python easy_add.py inertia_docs                 # Добавить папку
    python easy_add.py                              # Интерактивный режим  
    python easy_add.py list                         # Список фреймворков
    python easy_add.py remove vue                   # Удалить фреймворк
    python easy_add.py stats                        # Статистика
    python easy_add.py server                       # Запустить сервер
"""

import os
import sys
import json
import yaml
import subprocess
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

@dataclass
class FrameworkInfo:
    """Информация об обнаруженном фреймворке"""
    name: str
    type: str
    description: str
    path: str
    confidence: float
    settings: Dict[str, Any]

class SmartDetector:
    """Умное автоопределение типов документации и фреймворков"""
    
    # Паттерны для определения типа документации
    DOC_TYPE_PATTERNS = {
        'vitepress': {
            'files': ['.vitepress', 'src/.vitepress', 'docs/.vitepress'],
            'package_indicators': ['vitepress'],
            'confidence': 0.9
        },
        'docusaurus': {
            'files': ['docusaurus.config.js', 'docusaurus.config.ts', 'sidebars.js'],
            'package_indicators': ['@docusaurus/core'],
            'confidence': 0.9
        },
        'gitbook': {
            'files': ['SUMMARY.md', '.gitbook.yaml'],
            'confidence': 0.8
        },
        'sphinx': {
            'files': ['conf.py', 'source/conf.py'],
            'confidence': 0.8
        },
        'mkdocs': {
            'files': ['mkdocs.yml', 'mkdocs.yaml'],
            'confidence': 0.8
        },
        'markdown': {
            'files': ['README.md', 'readme.md'],
            'confidence': 0.3  # базовый fallback
        }
    }
    
    # Паттерны для определения фреймворков
    FRAMEWORK_PATTERNS = {
        'vue': {
            'keywords': ['vue', 'composition api', 'reactive', 'single file component'],
            'files': ['vue.config.js', 'vite.config.js'],
            'package_indicators': ['vue', '@vue/'],
            'extensions': ['.vue'],
            'confidence_boost': 0.3
        },
        'react': {
            'keywords': ['react', 'jsx', 'hooks', 'component'],
            'files': ['package.json'],
            'package_indicators': ['react', 'react-dom'],
            'extensions': ['.jsx', '.tsx'],
            'confidence_boost': 0.3
        },
        'laravel': {
            'keywords': ['laravel', 'eloquent', 'artisan', 'blade'],
            'files': ['composer.json', 'artisan'],
            'package_indicators': ['laravel/framework'],
            'extensions': ['.php'],
            'confidence_boost': 0.4
        },
        'django': {
            'keywords': ['django', 'models', 'views', 'templates'],
            'files': ['manage.py', 'settings.py'],
            'confidence_boost': 0.4
        },
        'angular': {
            'keywords': ['angular', 'directive', 'service', 'component'],
            'files': ['angular.json'],
            'package_indicators': ['@angular/core'],
            'confidence_boost': 0.3
        },
        'svelte': {
            'keywords': ['svelte', 'reactive', 'compiler'],
            'files': ['svelte.config.js'],
            'package_indicators': ['svelte'],
            'extensions': ['.svelte'],
            'confidence_boost': 0.3
        },
        'inertia': {
            'keywords': ['inertia', 'spa', 'server-side routing', 'single-page', 'modern single-page'],
            'files': ['inertia.php'],
            'package_indicators': ['inertiajs', '@inertiajs'],
            'confidence_boost': 0.5
        }
    }
    
    def detect_documentation_type(self, path: Path) -> Tuple[str, float]:
        """Определяет тип системы документации"""
        best_type = 'markdown'
        best_confidence = 0.0
        
        # Проверяем package.json если есть
        package_json = path / 'package.json'
        if package_json.exists():
            try:
                with open(package_json, 'r', encoding='utf-8') as f:
                    package_data = json.load(f)
                    dependencies = {**package_data.get('dependencies', {}), 
                                  **package_data.get('devDependencies', {})}
                    
                    for doc_type, patterns in self.DOC_TYPE_PATTERNS.items():
                        if 'package_indicators' in patterns:
                            for indicator in patterns['package_indicators']:
                                for dep in dependencies:
                                    if indicator in dep:
                                        confidence = patterns['confidence']
                                        if confidence > best_confidence:
                                            best_type = doc_type
                                            best_confidence = confidence
            except:
                pass
        
        # Проверяем файлы-индикаторы
        for doc_type, patterns in self.DOC_TYPE_PATTERNS.items():
            for file_pattern in patterns.get('files', []):
                if (path / file_pattern).exists():
                    confidence = patterns['confidence']
                    if confidence > best_confidence:
                        best_type = doc_type
                        best_confidence = confidence
        
        return best_type, best_confidence
    
    def detect_framework(self, path: Path) -> Tuple[str, float, str]:
        """Определяет фреймворк и возвращает (name, confidence, description)"""
        scores = {}
        
        # Сканируем файлы в папке
        files = list(path.rglob('*'))[:1000]  # Ограничиваем для производительности
        
        # Анализируем по расширениям
        extensions = set(f.suffix.lower() for f in files if f.is_file())
        
        # Анализируем по именам файлов
        filenames = set(f.name.lower() for f in files if f.is_file())
        
        # Анализируем содержимое README и других текстовых файлов
        content_keywords = []
        readme_content = ""
        for readme_file in ['README.md', 'readme.md', 'README.txt']:
            readme_path = path / readme_file
            if readme_path.exists():
                try:
                    with open(readme_path, 'r', encoding='utf-8') as f:
                        readme_content = f.read().lower()
                        content_keywords.extend(readme_content.split())
                        break
                except:
                    continue
        
        # Проверяем package.json для Node.js проектов
        package_indicators = []
        package_json = path / 'package.json'
        if package_json.exists():
            try:
                with open(package_json, 'r', encoding='utf-8') as f:
                    package_data = json.load(f)
                    dependencies = {**package_data.get('dependencies', {}), 
                                  **package_data.get('devDependencies', {})}
                    package_indicators = list(dependencies.keys())
            except:
                pass
        
        # Специальная проверка для Inertia.js в README
        inertia_in_readme = "inertia.js" in readme_content or "inertiajs" in readme_content
        
        # Подсчитываем баллы для каждого фреймворка
        for framework, patterns in self.FRAMEWORK_PATTERNS.items():
            score = 0.0
            
            # Бонус для Inertia.js если упоминается в README
            if framework == 'inertia' and inertia_in_readme:
                score += 0.8  # Высокий приоритет
            
            # Проверяем ключевые слова в содержимом
            for keyword in patterns.get('keywords', []):
                if keyword in readme_content:
                    score += 0.3 if framework == 'inertia' else 0.2
            
            # Проверяем индикаторы в package.json
            for indicator in patterns.get('package_indicators', []):
                if any(indicator in pkg for pkg in package_indicators):
                    score += 0.4 if framework == 'inertia' else 0.3
            
            # Проверяем расширения файлов (меньший вес для React/Vue в Inertia проекте)
            for ext in patterns.get('extensions', []):
                if ext in extensions:
                    boost = patterns.get('confidence_boost', 0.2)
                    if inertia_in_readme and framework in ['react', 'vue']:
                        boost *= 0.3  # Снижаем вес для React/Vue если это Inertia проект
                    score += boost
            
            # Проверяем специфичные файлы
            for file_pattern in patterns.get('files', []):
                if file_pattern in filenames:
                    score += 0.2
            
            scores[framework] = score
        
        # Находим лучший результат
        if not scores or max(scores.values()) < 0.1:
            # Если ничего не обнаружено, пытаемся угадать по имени папки
            folder_name = path.name.lower()
            for framework in self.FRAMEWORK_PATTERNS:
                if framework in folder_name:
                    return framework.title(), 0.5, f"{framework.title()} (определено по имени папки)"
            
            return "Unknown", 0.0, "Неизвестный фреймворк"
        
        best_framework = max(scores, key=scores.get)
        confidence = scores[best_framework]
        
        # Генерируем описание
        descriptions = {
            'vue': 'Vue.js - Progressive JavaScript Framework',
            'react': 'React - JavaScript library for building user interfaces',
            'laravel': 'Laravel - PHP Framework for Web Artisans',
            'django': 'Django - High-level Python Web framework',
            'angular': 'Angular - Platform for building mobile and desktop web applications',
            'svelte': 'Svelte - Cybernetically enhanced web apps',
            'inertia': 'Inertia.js - Build single-page apps without building an API'
        }
        
        description = descriptions.get(best_framework, f"{best_framework.title()} framework")
        
        return best_framework.title(), confidence, description
    
    def detect_framework_info(self, path: Path) -> FrameworkInfo:
        """Полное определение информации о фреймворке"""
        if not path.exists():
            raise ValueError(f"Путь {path} не существует")
        
        doc_type, doc_confidence = self.detect_documentation_type(path)
        framework_name, fw_confidence, description = self.detect_framework(path)
        
        # Генерируем настройки на основе определенного типа
        settings = self._generate_settings(doc_type, framework_name.lower(), path)
        
        return FrameworkInfo(
            name=framework_name,
            type=doc_type,
            description=description,
            path=str(path),
            confidence=max(doc_confidence, fw_confidence),
            settings=settings
        )
    
    def _generate_settings(self, doc_type: str, framework: str, path: Path) -> Dict[str, Any]:
        """Генерирует настройки конфигурации на основе типа документации"""
        
        base_settings = {
            'enabled': True,
            'prefix': framework,
            'file_patterns': ['*.md'],
            'exclude_patterns': ['**/node_modules/**', '**/.git/**'],
            'chunk_settings': {
                'max_size': 2000,
                'overlap': 200
            },
            'content_cleaning': {
                'remove_frontmatter': True,
                'remove_html_tags': True,
                'remove_code_blocks': False
            }
        }
        
        # Специфичные настройки для разных типов документации
        if doc_type == 'vitepress':
            base_settings.update({
                'path': str(path / 'src') if (path / 'src').exists() else str(path),
                'content_cleaning': {
                    **base_settings['content_cleaning'],
                    'remove_vue_components': True,
                    'remove_script_tags': True,
                    'remove_style_tags': True
                }
            })
        elif doc_type == 'docusaurus':
            base_settings.update({
                'path': str(path / 'docs') if (path / 'docs').exists() else str(path),
                'file_patterns': ['*.md', '*.mdx']
            })
        else:
            base_settings['path'] = str(path)
        
        return base_settings

class EasyAddManager:
    """Основной менеджер для простого добавления документации"""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.detector = SmartDetector()
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Загружает конфигурацию"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            print(f"❌ Конфигурационный файл {self.config_path} не найден")
            sys.exit(1)
    
    def _save_config(self):
        """Сохраняет конфигурацию"""
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(self.config, f, default_flow_style=False, allow_unicode=True, indent=2)
    
    def add_framework_easy(self, folder_path: str, auto_start_server: bool = False) -> bool:
        """Автоматическое добавление фреймворка одной командой"""
        try:
            path = Path(folder_path).resolve()
            
            print(f"🔍 Анализируем папку: {path}")
            
            # Автоопределение
            framework_info = self.detector.detect_framework_info(path)
            
            print(f"🎯 Обнаружен: {framework_info.name} ({framework_info.type})")
            print(f"📝 Описание: {framework_info.description}")
            print(f"🎪 Уверенность: {framework_info.confidence:.1%}")
            
            # Генерируем уникальный ключ
            framework_key = framework_info.name.lower().replace(' ', '_').replace('.', '')
            
            # Проверяем, не существует ли уже
            if self.config and framework_key in self.config.get('frameworks', {}):
                response = input(f"⚠️ Фреймворк '{framework_key}' уже существует. Перезаписать? [y/N]: ")
                if response.lower() != 'y':
                    print("❌ Отменено")
                    return False
            
            # Добавляем в конфиг
            if not self.config:
                self.config = {}
            if 'frameworks' not in self.config:
                self.config['frameworks'] = {}
            
            self.config['frameworks'][framework_key] = {
                'name': framework_info.name,
                'description': framework_info.description,
                **framework_info.settings
            }
            
            # Сохраняем конфиг
            self._save_config()
            print(f"✅ Конфигурация обновлена")
            
            # Обрабатываем документацию
            print(f"🚀 Обрабатываем документацию...")
            result = subprocess.run([
                sys.executable, 'docs_manager.py', 'add', '--framework', framework_key
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"✅ Документация добавлена в базу данных")
                
                # Запускаем сервер если нужно
                if auto_start_server:
                    print(f"🌐 Запускаем сервер...")
                    self.start_server()
                else:
                    print(f"💡 Для запуска сервера выполните: python rag_server.py")
                    print(f"🧪 Для тестирования выполните: python test_system.py")
                
                return True
            else:
                print(f"❌ Ошибка при обработке документации:")
                print(result.stderr)
                return False
                
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            return False
    
    def interactive_mode(self):
        """Интерактивный режим добавления"""
        print("🎉 Интерактивное добавление документации в RAG систему")
        print("=" * 60)
        
        # Запрашиваем путь
        while True:
            folder_path = input("📁 Путь к папке с документацией: ").strip()
            if not folder_path:
                print("❌ Путь не может быть пустым")
                continue
            
            path = Path(folder_path)
            if not path.exists():
                print(f"❌ Папка {path} не существует")
                continue
            
            break
        
        # Автоопределение
        try:
            framework_info = self.detector.detect_framework_info(path)
            
            print(f"\n🔍 Автоопределение:")
            print(f"  📦 Фреймворк: {framework_info.name}")
            print(f"  📚 Тип документации: {framework_info.type}")
            print(f"  📝 Описание: {framework_info.description}")
            print(f"  🎯 Уверенность: {framework_info.confidence:.1%}")
            
            # Подтверждение
            response = input(f"\n✅ Всё правильно? [Y/n]: ").strip().lower()
            if response == 'n':
                framework_info.name = input(f"📦 Введите название фреймворка: ").strip() or framework_info.name
                framework_info.description = input(f"📝 Введите описание: ").strip() or framework_info.description
            
            # Запуск сервера
            auto_server = input(f"\n🌐 Запустить сервер после добавления? [y/N]: ").strip().lower() == 'y'
            
            # Выполняем добавление
            success = self.add_framework_easy(str(path), auto_server)
            
            if success:
                print(f"\n🎉 Готово! Фреймворк '{framework_info.name}' добавлен в RAG систему")
            else:
                print(f"\n❌ Что-то пошло не так")
                
        except Exception as e:
            print(f"❌ Ошибка: {e}")
    
    def list_frameworks(self):
        """Список всех фреймворков"""
        frameworks = self.config.get('frameworks', {})
        
        if not frameworks:
            print("📭 Нет добавленных фреймворков")
            return
        
        print("📚 Установленные фреймворки:")
        print("=" * 60)
        
        for key, config in frameworks.items():
            status = "✅" if config.get('enabled', True) else "⏸️"
            name = config.get('name', key)
            description = config.get('description', 'Без описания')
            path = config.get('path', 'Неизвестно')
            
            print(f"{status} {name}")
            print(f"   📝 {description}")
            print(f"   📁 {path}")
            print(f"   🔑 Ключ: {key}")
            print()
    
    def remove_framework(self, framework_key: str):
        """Удаление фреймворка"""
        frameworks = self.config.get('frameworks', {})
        
        if framework_key not in frameworks:
            print(f"❌ Фреймворк '{framework_key}' не найден")
            self.list_frameworks()
            return
        
        framework_name = frameworks[framework_key].get('name', framework_key)
        
        response = input(f"⚠️ Удалить фреймворк '{framework_name}'? [y/N]: ")
        if response.lower() != 'y':
            print("❌ Отменено")
            return
        
        del self.config['frameworks'][framework_key]
        self._save_config()
        
        print(f"✅ Фреймворк '{framework_name}' удален из конфигурации")
        print("💡 Для полного удаления из базы данных выполните: python docs_manager.py rebuild")
    
    def show_stats(self):
        """Показать статистику"""
        try:
            result = subprocess.run([
                sys.executable, 'docs_manager.py', 'stats'
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                print(result.stdout)
            else:
                print("❌ Ошибка получения статистики")
                print(result.stderr)
        except Exception as e:
            print(f"❌ Ошибка: {e}")
    
    def scan_for_frameworks(self, scan_path: str = ".") -> List[Path]:
        """Автосканирование папок на наличие документации"""
        print(f"🔍 Сканируем папки в {Path(scan_path).resolve()}...")
        
        found_folders = []
        scan_dir = Path(scan_path)
        
        # Получаем настройки из конфига
        auto_scan_config = self.config.get('auto_scan', {})
        exclude_patterns = auto_scan_config.get('exclude_patterns', [
            'node_modules', '.git', '.venv', 'venv', '__pycache__',
            '.next', '.nuxt', 'dist', 'build', '.cache', 'coverage'
        ])
        
        doc_indicators = auto_scan_config.get('doc_indicators', [
            'README.md', 'readme.md', 'docs', 'documentation', 'guide',
            '.vitepress', 'docusaurus.config.js', 'mkdocs.yml'
        ])
        
        min_md_files = auto_scan_config.get('min_md_files', 1)  # Снижаем требования
        
        for item in scan_dir.iterdir():
            if not item.is_dir():
                continue
                
            # Пропускаем исключенные папки
            if any(exclude in item.name.lower() for exclude in exclude_patterns):
                continue
                
            # Проверяем наличие индикаторов документации
            has_docs = False
            
            # Проверяем индикаторы
            for indicator in doc_indicators:
                if (item / indicator).exists():
                    has_docs = True
                    break
            
            # Подсчитываем файлы документации
            md_files = list(item.rglob('*.md'))
            rst_files = list(item.rglob('*.rst'))
            txt_files = list(item.rglob('*.txt'))
            html_files = list(item.rglob('*.html'))
            
            total_doc_files = len(md_files) + len(rst_files) + len(txt_files) + len(html_files)
            
            # Проверяем минимальное количество файлов
            if not has_docs and total_doc_files >= min_md_files:
                has_docs = True
            
            # Показываем детали сканирования
            if has_docs:
                print(f"   ✅ {item.name} - найдено файлов документации: {total_doc_files}")
                found_folders.append(item)
            elif total_doc_files > 0:
                print(f"   ⏭️ {item.name} - пропускаем (файлов: {total_doc_files}, минимум: {min_md_files})")
        
        print(f"\n📂 Найдено потенциальных папок с документацией: {len(found_folders)}")
        for folder in found_folders:
            print(f"   📁 {folder.name}")
        
        return found_folders
    
    def update_existing_frameworks(self) -> int:
        """Обновляет существующие фреймворки"""
        updated_count = 0
        frameworks = self.config.get('frameworks', {})
        
        if not frameworks:
            print("📭 Нет фреймворков для обновления")
            return 0
        
        print(f"🔄 Обновляем {len(frameworks)} существующих фреймворков...")
        
        for framework_key, framework_config in frameworks.items():
            if not framework_config.get('enabled', True):
                continue
                
            path = Path(framework_config.get('path', ''))
            if not path.exists():
                print(f"⚠️ Папка {framework_config['name']} не найдена: {path}")
                continue
            
            print(f"🔄 Обновляем {framework_config['name']}...")
            result = subprocess.run([
                sys.executable, 'docs_manager.py', 'add', '--framework', framework_key
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                updated_count += 1
                print(f"✅ {framework_config['name']} обновлен")
            else:
                print(f"❌ Ошибка обновления {framework_config['name']}")
        
        return updated_count
    
    def smart_sync(self, scan_path: str = ".") -> Dict[str, int]:
        """Умная синхронизация: добавляет новые + обновляет существующие"""
        results = {"new": 0, "updated": 0, "errors": 0}
        
        print("🧠 Запускаем умную синхронизацию...")
        
        # 1. Обновляем существующие
        results["updated"] = self.update_existing_frameworks()
        
        # 2. Ищем новые папки
        found_folders = self.scan_for_frameworks(scan_path)
        existing_paths = set()
        
        for framework_config in self.config.get('frameworks', {}).values():
            if 'path' in framework_config:
                existing_paths.add(str(Path(framework_config['path']).resolve()))
        
        # 3. Добавляем новые фреймворки
        new_folders = []
        for folder in found_folders:
            if str(folder.resolve()) not in existing_paths:
                new_folders.append(folder)
        
        if new_folders:
            print(f"\n🆕 Найдено {len(new_folders)} новых папок с документацией:")
            for folder in new_folders:
                print(f"   📁 {folder.name}")
            
            print(f"\n➕ Автоматически добавляем все новые фреймворки...")
            
            for folder in new_folders:
                try:
                    print(f"\n🚀 Добавляем {folder.name}...")
                    
                    # Получаем статистику ДО добавления
                    initial_stats = self._get_database_stats()
                    initial_count = initial_stats.get('total_documents', 0)
                    
                    success = self.add_framework_easy(str(folder), auto_start_server=False)
                    
                    if success:
                        # Получаем статистику ПОСЛЕ добавления
                        final_stats = self._get_database_stats()
                        final_count = final_stats.get('total_documents', 0)
                        added_chunks = final_count - initial_count
                        
                        print(f"✅ {folder.name} добавлен - создано {added_chunks} чанков")
                        results["new"] += 1
                        results["chunks_added"] = results.get("chunks_added", 0) + added_chunks
                    else:
                        results["errors"] += 1
                except Exception as e:
                    print(f"❌ Ошибка добавления {folder.name}: {e}")
                    results["errors"] += 1
        else:
            print("🔍 Новых фреймворков не найдено")
            results["chunks_added"] = 0
        
        return results
    
    def _get_database_stats(self) -> Dict[str, Any]:
        """Получает текущую статистику базы данных"""
        try:
            result = subprocess.run([
                sys.executable, 'docs_manager.py', 'stats'
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                # Парсим вывод для получения количества документов
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if 'Всего документов:' in line:
                        count = int(line.split(':')[1].strip())
                        return {"total_documents": count}
            return {"total_documents": 0}
        except:
            return {"total_documents": 0}
    
    def auto_mode(self, scan_path: str = ".") -> bool:
        """Полностью автоматический режим: всё в одной команде"""
        print("🤖 АВТОМАТИЧЕСКИЙ РЕЖИМ")
        print("=" * 50)
        print("🔥 Делаем ВСЁ автоматически:")
        print("   1. Сканируем папки")
        print("   2. Находим документацию")
        print("   3. Добавляем новые фреймворки")
        print("   4. Обновляем существующие")
        print("   5. Запускаем сервер")
        print("=" * 50)
        
        try:
            # Получаем начальную статистику
            initial_stats = self._get_database_stats()
            initial_total = initial_stats.get('total_documents', 0)
            
            # Умная синхронизация
            results = self.smart_sync(scan_path)
            
            # Получаем финальную статистику
            final_stats = self._get_database_stats()
            final_total = final_stats.get('total_documents', 0)
            
            # Показываем детальные результаты
            print(f"\n" + "="*60)
            print(f"📊 РЕЗУЛЬТАТЫ АВТОМАТИЧЕСКОЙ СИНХРОНИЗАЦИИ")
            print(f"="*60)
            print(f"🆕 Новых папок найдено: {results['new']}")
            print(f"🔄 Фреймворков обновлено: {results['updated']}")
            
            chunks_added = results.get('chunks_added', 0)
            if chunks_added > 0:
                print(f"📦 Документов добавлено: {chunks_added}")
            
            print(f"📚 Общее количество документов в базе: {final_total}")
            print(f"📈 Прирост документов: +{final_total - initial_total}")
            
            if results['errors'] > 0:
                print(f"❌ Ошибок: {results['errors']}")
            
            # Показываем итоговую информацию о фреймворках
            total_frameworks = len(self.config.get('frameworks', {}))
            print(f"\n🎯 Всего фреймворков в системе: {total_frameworks}")
            
            framework_names = list(self.config.get('frameworks', {}).keys())
            if framework_names:
                print(f"📋 Доступные фреймворки: {', '.join(framework_names)}")
            
            # Запускаем сервер
            if total_frameworks > 0:
                print(f"\n🎉 RAG система готова к работе!")
                print(f"🌐 Запускаем сервер на http://localhost:8000...")
                print("="*60)
                self.start_server()
                return True
            else:
                print("❌ Не найдено ни одного фреймворка для добавления")
                return False
        
        except Exception as e:
            print(f"❌ Ошибка автоматического режима: {e}")
            return False
    
    def start_server(self):
        """Запуск сервера"""
        try:
            print("🌐 Запускаем RAG сервер...")
            print("🔗 Сервер будет доступен на http://localhost:8000")
            print("⏹️ Для остановки нажмите Ctrl+C")
            
            subprocess.run([sys.executable, 'rag_server.py'])
        except KeyboardInterrupt:
            print("\n🛑 Сервер остановлен")
        except Exception as e:
            print(f"❌ Ошибка запуска сервера: {e}")

def main():
    """Главная функция"""
    parser = argparse.ArgumentParser(
        description="🚀 EasyAdd - Магическая автоматизация RAG системы",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
🔥 НОВЫЕ СУПЕР-КОМАНДЫ:
  python easy_add.py --auto                       # АВТОМАТИЧЕСКИЙ РЕЖИМ: делает всё сам!
  python easy_add.py --scan-all                   # Сканирует все папки и показывает найденное
  python easy_add.py --smart-sync                 # Умная синхронизация: новые + обновления
  python easy_add.py --update-all                 # Обновить все существующие фреймворки

📝 Классические команды:
  python easy_add.py inertia_docs                 # Добавить папку inertia_docs
  python easy_add.py                              # Интерактивный режим
  python easy_add.py list                         # Список фреймворков  
  python easy_add.py remove vue                   # Удалить фреймворк
  python easy_add.py stats                        # Статистика БД
  python easy_add.py server                       # Запустить сервер
        """
    )
    
    parser.add_argument('action', nargs='?', 
                       help='Действие: путь к папке, list, remove, stats, server, или команды автоматизации')
    parser.add_argument('target', nargs='?', 
                       help='Цель действия (например, имя фреймворка для remove)')
    parser.add_argument('--config', default='config.yaml',
                       help='Путь к конфигурационному файлу')
    parser.add_argument('--auto-server', action='store_true',
                       help='Автоматически запустить сервер после добавления')
    
    # Новые флаги автоматизации
    parser.add_argument('--auto', action='store_true',
                       help='🤖 АВТОМАТИЧЕСКИЙ РЕЖИМ: сканирует, добавляет, обновляет, запускает сервер')
    parser.add_argument('--scan-all', action='store_true',
                       help='🔍 Сканировать все папки и показать найденную документацию')
    parser.add_argument('--smart-sync', action='store_true',
                       help='🧠 Умная синхронизация: добавить новые + обновить существующие')
    parser.add_argument('--update-all', action='store_true',
                       help='🔄 Обновить все существующие фреймворки')
    parser.add_argument('--scan-path', default='.',
                       help='Путь для сканирования (по умолчанию текущая папка)')
    
    args = parser.parse_args()
    
    manager = EasyAddManager(args.config)
    
    # Новые режимы автоматизации
    if args.auto:
        manager.auto_mode(args.scan_path)
        return
    
    elif args.scan_all:
        found_folders = manager.scan_for_frameworks(args.scan_path)
        if found_folders:
            print(f"\n🎯 Найдено {len(found_folders)} папок с документацией")
            print("📋 Для добавления используйте: python easy_add.py --auto")
        else:
            print("🔍 Документация не найдена")
        return
    
    elif args.smart_sync:
        results = manager.smart_sync(args.scan_path)
        print(f"\n🎉 Синхронизация завершена!")
        print(f"🆕 Новых: {results['new']}, 🔄 Обновлено: {results['updated']}")
        if results.get('chunks_added', 0) > 0:
            print(f"📦 Чанков добавлено: {results['chunks_added']}")
        if results['new'] + results['updated'] > 0:
            print("🌐 Автоматически запускаем сервер...")
            manager.start_server()
        return
    
    elif args.update_all:
        updated = manager.update_existing_frameworks()
        print(f"✅ Обновлено фреймворков: {updated}")
        return
    
    # Классические команды
    if not args.action:
        # Интерактивный режим
        manager.interactive_mode()
    
    elif args.action == 'list':
        manager.list_frameworks()
    
    elif args.action == 'remove':
        if not args.target:
            print("❌ Укажите имя фреймворка для удаления")
            manager.list_frameworks()
        else:
            manager.remove_framework(args.target)
    
    elif args.action == 'stats':
        manager.show_stats()
    
    elif args.action == 'server':
        manager.start_server()
    
    else:
        # Предполагаем, что это путь к папке
        folder_path = args.action
        manager.add_framework_easy(folder_path, args.auto_server)

if __name__ == "__main__":
    main()
