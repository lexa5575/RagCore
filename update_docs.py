#!/usr/bin/env python3
"""
Простой и мощный скрипт для автоматической индексации документации
🚀 Один скрипт - вся автоматизация!

Возможности:
- Автоматическое сканирование папки documentation/
- Умное определение фреймворков по именам папок
- Конвертация HTML → Markdown
- Обновление config.yaml
- Полная индексация в RAG базу данных
"""

import os
import sys
import subprocess
import yaml
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SimpleDocumentationManager:
    """Простой менеджер документации"""
    
    def __init__(self, documentation_path: str = 'documentation', config_path: str = 'config.yaml'):
        """Инициализация менеджера"""
        self.documentation_path = Path(documentation_path)
        self.config_path = config_path
        self.stats = {
            'start_time': datetime.now(),
            'frameworks_found': 0,
            'frameworks_indexed': 0,
            'total_chunks': 0,
            'errors': []
        }
        
        logger.info("🚀 Simple Documentation Manager initialized")
        logger.info(f"📁 Documentation folder: {self.documentation_path.absolute()}")
    
    def scan_documentation_folder(self) -> Dict[str, Dict]:
        """Сканирует папку documentation и находит фреймворки"""
        logger.info("🔍 Scanning documentation folder...")
        
        if not self.documentation_path.exists():
            logger.error(f"❌ Folder {self.documentation_path} not found!")
            return {}
        
        frameworks = {}
        
        # Сканируем все подпапки
        for folder in self.documentation_path.iterdir():
            if folder.is_dir() and not folder.name.startswith('.'):
                logger.info(f"📁 Found folder: {folder.name}")
                
                # Подсчитываем markdown файлы
                md_files = list(folder.rglob('*.md'))
                html_files = list(folder.rglob('*.html'))
                
                if len(md_files) > 0 or len(html_files) > 0:
                    # Определяем имя фреймворка
                    framework_name = self._extract_framework_name(folder.name)
                    
                    frameworks[framework_name] = {
                        'name': self._create_display_name(framework_name),
                        'description': f"{self._create_display_name(framework_name)} Documentation",
                        'path': f"./documentation/{folder.name}",
                        'type': 'markdown',
                        'enabled': True,
                        'md_files': len(md_files),
                        'html_files': len(html_files),
                        'total_files': len(md_files) + len(html_files)
                    }
                    
                    logger.info(f"✅ {framework_name}: {len(md_files)} MD + {len(html_files)} HTML files")
                else:
                    logger.info(f"⚠️  {folder.name}: no MD/HTML files - skipping")
        
        self.stats['frameworks_found'] = len(frameworks)
        logger.info(f"🎉 Found {len(frameworks)} frameworks")
        
        return frameworks
    
    def _extract_framework_name(self, folder_name: str) -> str:
        """Извлекает имя фреймворка из имени папки"""
        # Убираем суффиксы
        name = folder_name.lower()
        name = name.replace('_docs', '').replace('-docs', '')
        name = name.replace('_documentation', '').replace('-documentation', '')
        name = name.replace('_doc', '').replace('-doc', '')
        
        return name
    
    def _create_display_name(self, framework_name: str) -> str:
        """Создает красивое отображаемое имя"""
        # Специальные случаи
        special_names = {
            'vue': 'Vue.js',
            'tailwindcss': 'Tailwind CSS',
            'alpine': 'Alpine.js',
            'filament': 'Filament',
            'laravel': 'Laravel',
            'react': 'React',
            'nextjs': 'Next.js',
            'nuxt': 'Nuxt.js',
            'inertia': 'Inertia.js'
        }
        
        if framework_name in special_names:
            return special_names[framework_name]
        
        # Общий случай - делаем первую букву заглавной
        return framework_name.replace('_', ' ').replace('-', ' ').title()
    
    def convert_html_to_markdown(self, frameworks: Dict[str, Dict]) -> bool:
        """Конвертирует HTML файлы в Markdown"""
        logger.info("🔄 Converting HTML → Markdown...")
        
        html_converter_path = Path("universal_html_to_markdown.py")
        if not html_converter_path.exists():
            logger.warning("⚠️  universal_html_to_markdown.py not found - skipping HTML conversion")
            return True
        
        converted_any = False
        
        for framework_name, info in frameworks.items():
            if info['html_files'] > 0:
                logger.info(f"🔄 Converting HTML for {framework_name}...")
                
                try:
                    # Запускаем конвертер HTML
                    cmd = [
                        sys.executable,
                        str(html_converter_path),
                        "--input-dir", info['path'],
                        "--output-dir", info['path'],
                        "--recursive"
                    ]
                    
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                    
                    if result.returncode == 0:
                        logger.info(f"✅ HTML converted for {framework_name}")
                        converted_any = True
                    else:
                        logger.error(f"❌ HTML conversion error for {framework_name}: {result.stderr}")
                        self.stats['errors'].append(f"HTML conversion error for {framework_name}")
                        
                except Exception as e:
                    logger.error(f"❌ Critical HTML conversion error for {framework_name}: {e}")
                    self.stats['errors'].append(f"HTML conversion critical error for {framework_name}: {e}")
        
        if converted_any:
            logger.info("✅ HTML conversion completed")
        else:
            logger.info("ℹ️  No HTML files found for conversion")
        
        return True
    
    def update_config_yaml(self, frameworks: Dict[str, Dict]) -> bool:
        """Обновляет config.yaml с найденными фреймворками"""
        logger.info("📝 Updating config.yaml...")
        
        try:
            # Создаем бэкап
            self._backup_config()
            
            # Загружаем существующий конфиг
            config_file = Path(self.config_path)
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f) or {}
            else:
                config = {}
            
            # Убеждаемся что есть секция frameworks
            if 'frameworks' not in config:
                config['frameworks'] = {}
            
            # Проверяем, что frameworks не None
            if config['frameworks'] is None:
                config['frameworks'] = {}
            
            # Сохраняем существующие настройки пользователя
            existing_frameworks = config['frameworks'].copy()
            
            # Добавляем/обновляем фреймворки
            updated_count = 0
            for framework_name, info in frameworks.items():
                if framework_name not in existing_frameworks:
                    # Новый фреймворк
                    config['frameworks'][framework_name] = {
                        'name': info['name'],
                        'description': info['description'],
                        'path': info['path'],
                        'type': info['type'],
                        'enabled': info['enabled']
                    }
                    updated_count += 1
                    logger.info(f"➕ Added new framework: {info['name']}")
                else:
                    # Update path if changed
                    if existing_frameworks[framework_name].get('path') != info['path']:
                        config['frameworks'][framework_name]['path'] = info['path']
                        updated_count += 1
                        logger.info(f"🔄 Updated path for: {info['name']}")
            
            # Save updated config
            with open(config_file, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
            
            logger.info(f"✅ Config.yaml updated! Changes: {updated_count}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Config.yaml update error: {e}")
            self.stats['errors'].append(f"Config update error: {e}")
            return False
    
    def _backup_config(self):
        """Создает бэкап конфигурации"""
        config_file = Path(self.config_path)
        if config_file.exists():
            backup_name = f"config.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}.yaml"
            backup_path = config_file.parent / backup_name
            
            shutil.copy2(config_file, backup_path)
            logger.info(f"💾 Configuration backup created: {backup_name}")
    
    def index_frameworks(self, frameworks: Dict[str, Dict]) -> bool:
        """Индексирует все фреймворки в RAG базу данных"""
        logger.info("🗄️  Indexing frameworks into RAG database...")
        
        indexer_path = Path("universal_document_indexer.py")
        if not indexer_path.exists():
            logger.error("❌ universal_document_indexer.py not found!")
            return False
        
        indexed_count = 0
        total_chunks = 0
        
        for framework_name, info in frameworks.items():
            logger.info(f"🔄 Indexing {framework_name} ({info['total_files']} files)...")
            
            try:
                # Запускаем индексатор
                cmd = [
                    sys.executable,
                    str(indexer_path),
                    "--framework", framework_name,
                    "--mode", "full"
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
                
                if result.returncode == 0:
                    # Extract chunks count from output
                    chunks = self._extract_chunks_count(result.stdout)
                    total_chunks += chunks
                    indexed_count += 1
                    
                    logger.info(f"✅ {framework_name} indexed! Chunks: {chunks}")
                else:
                    logger.error(f"❌ Indexing error for {framework_name}: {result.stderr}")
                    self.stats['errors'].append(f"Indexing error for {framework_name}")
                    
            except subprocess.TimeoutExpired:
                logger.error(f"❌ Indexing timeout for {framework_name}")
                self.stats['errors'].append(f"Indexing timeout for {framework_name}")
            except Exception as e:
                logger.error(f"❌ Critical indexing error for {framework_name}: {e}")
                self.stats['errors'].append(f"Indexing critical error for {framework_name}: {e}")
        
        self.stats['frameworks_indexed'] = indexed_count
        self.stats['total_chunks'] = total_chunks
        
        logger.info(f"🎯 Indexing completed! Frameworks: {indexed_count}/{len(frameworks)}, chunks: {total_chunks}")
        return indexed_count > 0
    
    def _extract_chunks_count(self, output: str) -> int:
        """Извлекает количество чанков из вывода индексатора"""
        import re
        
        # Search for pattern "chunks: NUMBER"
        match = re.search(r'chunks:\s*(\d+)', output)
        if match:
            return int(match.group(1))
        
        # Alternative pattern
        match = re.search(r'(\d+)\s+semantic chunks', output)
        if match:
            return int(match.group(1))
        
        return 0
    
    def generate_final_report(self):
        """Генерирует финальный отчет"""
        logger.info("📊 FINAL REPORT")
        logger.info("=" * 60)
        
        duration = datetime.now() - self.stats['start_time']
        
        # Main statistics
        logger.info(f"⏱️  Execution time: {duration}")
        logger.info(f"🔍 Frameworks found: {self.stats['frameworks_found']}")
        logger.info(f"🗄️  Indexed: {self.stats['frameworks_indexed']}")
        logger.info(f"📄 Total chunks: {self.stats['total_chunks']}")
        
        # Errors
        if self.stats['errors']:
            logger.info(f"\n⚠️  Errors ({len(self.stats['errors'])}):")
            for error in self.stats['errors']:
                logger.info(f"   • {error}")
        
        # Recommendations
        logger.info("\n💡 Recommendations:")
        if self.stats['frameworks_indexed'] > 0:
            logger.info("   • Restart RAG server to apply changes")
            logger.info("   • Test functionality through MCP tools")
        
        if self.stats['errors']:
            logger.info("   • Check logs to resolve errors")
        
        logger.info("\n🎉 Automatic synchronization completed!")
    
    def run_full_sync(self) -> bool:
        """Запускает полную синхронизацию"""
        logger.info("🎯 STARTING FULL AUTOMATIC SYNCHRONIZATION")
        logger.info("=" * 60)
        
        try:
            # Stage 1: Scanning
            frameworks = self.scan_documentation_folder()
            if not frameworks:
                logger.error("❌ No frameworks found!")
                return False
            
            # Stage 2: HTML Conversion
            if not self.convert_html_to_markdown(frameworks):
                logger.warning("⚠️  HTML conversion errors")
            
            # Stage 3: Configuration Update
            if not self.update_config_yaml(frameworks):
                logger.error("❌ Configuration update error")
                return False
            
            # Stage 4: Indexing
            if not self.index_frameworks(frameworks):
                logger.error("❌ Indexing error")
                return False
            
            # Stage 5: Final Report
            self.generate_final_report()
            
            logger.info("🎉 FULL SYNCHRONIZATION COMPLETED SUCCESSFULLY!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Critical error: {e}")
            self.stats['errors'].append(str(e))
            return False

def main():
    """Основная функция"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="🚀 Simple and powerful script for automatic documentation indexing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Usage examples:
  python3 update_docs.py                    # Full automatic synchronization
  python3 update_docs.py --scan             # Scan only
  python3 update_docs.py --documentation-path ./docs  # Different folder
        """
    )
    
    parser.add_argument('--scan', action='store_true',
                       help='Scan only without indexing')
    parser.add_argument('--documentation-path', default='documentation',
                       help='Path to documentation folder')
    parser.add_argument('--config', default='config.yaml',
                       help='Path to configuration file')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose output')
    
    args = parser.parse_args()
    
    # Настройка уровня логирования
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Создаем менеджер
    manager = SimpleDocumentationManager(args.documentation_path, args.config)
    
    try:
        if args.scan:
            # Scan only
            frameworks = manager.scan_documentation_folder()
            
            if frameworks:
                print("\n🔍 **FOUND FRAMEWORKS:**\n")
                for name, info in frameworks.items():
                    print(f"✅ **{info['name']}** ({name})")
                    print(f"   📁 Path: {info['path']}")
                    print(f"   📄 Files: {info['total_files']} ({info['md_files']} MD + {info['html_files']} HTML)")
                    print()
                
                print(f"📊 **TOTAL:** {len(frameworks)} frameworks found")
            else:
                print("❌ No frameworks found")
            
            return 0
        else:
            # Full synchronization
            success = manager.run_full_sync()
            return 0 if success else 1
    
    except KeyboardInterrupt:
        logger.info("\n⏹️  Operation interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        return 1

if __name__ == '__main__':
    exit(main())
